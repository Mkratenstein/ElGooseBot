import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import datetime
from typing import Optional
from config import TOKEN
import re
import html  # Add import for HTML entity decoding
import traceback  # Add this at the top
from LiveSetlist import LiveSetlist

# Bot setup with all intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# API base URL
API_BASE_URL = "https://elgoose.net/api/v2"

# Remove default help command to implement custom one
bot.remove_command('help')

CHANNEL_ID = 1384576172922503271
live_setlist_tracker = None

@bot.event
async def on_ready():
    global live_setlist_tracker
    print(f'Logged in as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        live_setlist_tracker = LiveSetlist(bot, CHANNEL_ID, fetch_show_details)
    except Exception as e:
        print(f"Failed to sync commands: {e}")


async def fetch_api_data(endpoint: str) -> dict:
    """Helper function to fetch data from the API with enhanced error handling"""
    async with aiohttp.ClientSession() as session:
        try:
            full_url = f"{API_BASE_URL}/{endpoint}"
            print(f"[API Request] URL: {full_url}")
            
            start_time = datetime.datetime.now()
            async with session.get(full_url) as response:
                end_time = datetime.datetime.now()
                response_time = (end_time - start_time).total_seconds()
                print(f"[API Response] Time: {response_time:.2f}s")
                print(f"[API Response] Status: {response.status}")
                print(f"[API Response] Headers: {dict(response.headers)}")
                
                text_response = await response.text()
                print(f"[API Response] Raw content: {text_response[:1000]}")  # First 1000 chars
                
                if response.status == 200:
                    try:
                        json_data = await response.json(content_type=None)
                        print(f"[API Response] Parsed JSON: {str(json_data)[:500]}...")  # First 500 chars of parsed data
                        
                        # Handle the wrapped response structure
                        if isinstance(json_data, dict) and 'error' in json_data:
                            if json_data['error']:
                                print(f"[API Error] API returned error: {json_data['error_message']}")
                                return None
                            return json_data.get('data')
                        return json_data
                    except Exception as e:
                        print(f"[API Error] JSON parsing failed: {str(e)}")
                        print(f"[API Debug] Content-Type: {response.headers.get('content-type')}")
                        print(f"[API Debug] Response length: {len(text_response)}")
                        return None
                else:
                    print(f"[API Error] Non-200 status code: {response.status}")
                    print(f"[API Error] Response body: {text_response}")
                    return None
        except aiohttp.ClientError as e:
            print(f"[API Error] Network error: {str(e)}")
            return None
        except Exception as e:
            print(f"[API Error] Unexpected error: {str(e)}")
            return None

async def fetch_show_details(show_id: str, date: str = None) -> dict:
    """Helper function to fetch detailed show information including setlist"""
    # First, get the basic show information to confirm a show exists
    base_show_data_list = await fetch_api_data(f"shows/showdate/{date}.json")
    
    if not base_show_data_list or not isinstance(base_show_data_list, list):
        return None  # No show scheduled for this date

    # Filter for the correct Goose show on the specified date
    final_show_data = next((show for show in base_show_data_list if show.get('artist', '').lower() == 'goose' and show.get('showdate') == date), None)

    if not final_show_data:
        return None # No Goose show found for this date
        
    # Now, try to get the setlist details
    setlist_data = await fetch_api_data(f"setlists/showdate/{date}.json")
    
    if setlist_data and isinstance(setlist_data, list):
        # Filter for only Goose songs
        goose_songs = [
            song for song in setlist_data 
            if song.get('artist', '').lower() == 'goose' 
            and song.get('artist_id') == 1
        ]
        
        if goose_songs:
            # Process the setlist data into sets
            sets = {}
            show_notes = None
            coach_notes = []  # Initialize coach_notes list first
            
            # Extract coach's notes from footnotes first
            note_number = 1
            footnote_map = {}  # Create a mapping of footnotes to numbers
            for song in goose_songs:
                if song.get('footnote'):
                    footnote = song.get('footnote')
                    if footnote not in footnote_map:
                        footnote_map[footnote] = str(note_number)
                        coach_notes.append({
                            "number": str(note_number),
                            "text": footnote
                        })
                        note_number += 1
            
            # Now process the songs with the footnote numbers
            for song in goose_songs:
                set_number = song.get('setnumber')
                set_type = song.get('settype', 'Set')
                song_name = song.get('songname', '')
                transition = song.get('transition', '')
                footnote = song.get('footnote', '')
                # Overwrite shownotes from setlist if available, as it's more specific
                if song.get('shownotes'):
                    show_notes = song.get('shownotes')
                
                # Format the song text
                song_text = song_name
                if footnote:
                    song_text += f"[{footnote_map.get(footnote, '?')}]"
                if transition:
                    # Handle special case for -> transition
                    if transition.strip() == '->':
                        song_text += ' ->'
                    else:
                        song_text += ' >'
                
                # Add to the appropriate set
                set_key = 'Encore' if set_type.lower() in ['encore', 'e'] else f'Set {set_number}'
                if set_key not in sets:
                    sets[set_key] = []
                sets[set_key].append(song_text)
            
            # Convert sets to list format
            formatted_sets = []
            for set_name, songs_list in sets.items():
                formatted_songs = [song.strip() for song in songs_list]
                formatted_sets.append({
                    "name": set_name,
                    "songs": ", ".join(formatted_songs)
                })
            
            # Merge the processed setlist data into our main show data object
            final_show_data['sets'] = formatted_sets
            if show_notes:
                final_show_data['notes'] = show_notes
            if coach_notes:
                final_show_data['coach_notes'] = coach_notes
    
    # If setlist_data is empty, we will just return the base show info
    return final_show_data

@bot.tree.command(name="setlist", description="Get setlist for a specific date (YYYY-MM-DD or YYYY/MM/DD)")
async def setlist(interaction: discord.Interaction, date: str):
    """Get setlist for a specific date"""
    try:
        # Validate date format
        parsed_date = datetime.datetime.strptime(date, '%Y-%m-%d')
        print(f"[Setlist] Validated date format: {date}")
        
        # First, defer the response since API calls might take time
        await interaction.response.defer()
        print(f"[Setlist] Response deferred")
        
        print(f"[Setlist] Fetching data for date: {date}")
        
        # Try to get show data first
        show_data = await fetch_api_data(f"shows/showdate/{date}.json")
        if not show_data:
            print(f"[Setlist] No show data found, trying setlists endpoint")
            show_data = await fetch_api_data(f"setlists/showdate/{date}.json")
        
        if not show_data:
            print(f"[Setlist] No data returned from API")
            await interaction.followup.send(
                "Unable to fetch setlist data. This could be due to:\n"
                "• API connection issues\n"
                "• Invalid date format on the server\n"
                "• No setlist available for this date\n"
                "Please try again later or contact support if the issue persists.",
                ephemeral=True
            )
            return
        
        # Handle the array response
        shows = show_data if isinstance(show_data, list) else [show_data]
        print(f"[Setlist] Received {len(shows)} shows")
        
        # Filter for Goose shows on the exact date
        goose_shows = [
            show for show in shows 
            if show.get('artist', '').lower() == 'goose' 
            and show.get('showdate') == date
        ]
        print(f"[Setlist] Found {len(goose_shows)} Goose shows for {date}")
        
        if len(goose_shows) == 0:
            print(f"[Setlist] No Goose shows found for date: {date}")
            await interaction.followup.send(
                f"No Goose shows found for {date}. This date might be:\n"
                "• Before the band's first show\n"
                "• A date with no performance\n"
                "• Not yet added to the database\n\n"
                "Note: The earliest Goose shows in the database are from 2016.",
                ephemeral=True
            )
            return

        # Process the first (or only) Goose show
        show_data = goose_shows[0].copy()  # Make a copy to avoid modifying the original
        print(f"[Setlist] Processing show data with keys: {', '.join(show_data.keys())}")

        # Fetch detailed setlist information
        setlist_data = await fetch_show_details(show_data.get('show_id'), date)
        if setlist_data:
            # Merge the setlist data carefully
            for key, value in setlist_data.items():
                if value is not None:  # Only update if we have a value
                    show_data[key] = value
            print(f"[Setlist] Updated show data with setlist information")

        # Print full show data for debugging
        print(f"[Setlist Debug] Full show data: {show_data}")

        # Create embed
        venue_name = html.unescape(show_data.get('venuename', 'Unknown')).lower().replace(' ', '-').replace(',', '')
        location = show_data.get('location', 'Unknown').lower().replace(' ', '-').replace(',', '')
        show_url = f"https://elgoose.net/setlists/goose-{parsed_date.strftime('%B-%d-%Y').lower()}-{venue_name}-{location}.html"
        embed = discord.Embed(
            title=f"Goose - {parsed_date.strftime('%B %d, %Y')}",
            description=f"**{html.unescape(show_data.get('venuename', 'Unknown'))}**\n{show_data.get('location', 'Unknown')}",
            color=discord.Color.from_rgb(252, 186, 3)  # Goose gold/orange color
        )

        # Add setlist information
        if 'sets' in show_data and show_data['sets']:
            for set_data in show_data['sets']:
                set_name = set_data.get('name', 'Set')
                songs = set_data.get('songs', '')
                if songs:
                    # Clean up formatting
                    songs = re.sub(r'\s+', ' ', songs).strip()
                    
                    # Clean up formatting
                    songs = re.sub(r'\s*,\s*,+\s*', ', ', songs)  # Remove multiple commas
                    songs = re.sub(r',\s*$', '', songs)  # Remove trailing comma
                    songs = re.sub(r'\s*>\s*,', ' >', songs)  # Fix space before > and remove comma
                    songs = re.sub(r'\s*->\s*,', ' ->', songs)  # Fix space before -> and remove comma
                    songs = re.sub(r'\s+', ' ', songs)  # Normalize spaces
                    
                    # Replace any set name variant with 'Encore'
                    if set_name.lower() in ['set e', 'e', 'encore']:
                        set_name = 'Encore'
                    
                    # Format set name with colon
                    set_name = f"{set_name}:"
                    
                    # Add a newline after each set
                    embed.add_field(
                        name=set_name,
                        value=f"{songs}\n",
                        inline=False
                    )
        else:
            embed.add_field(
                name="Note:",
                value="Setlist information is being updated. Please check back later.",
                inline=False
            )

        # Add coach's notes if available
        if show_data.get('coach_notes'):
            coach_notes_text = "\n".join([f"{note['number']}. {note['text']}" for note in show_data['coach_notes']])
            embed.add_field(
                name="Coach's Notes",
                value=coach_notes_text,
                inline=False
            )
        
        # Add clickable URL under Coach's Notes
        embed.add_field(
            name="Full Setlist",
            value=f"[View Full Setlist on elgoose.net]({show_url})",
            inline=False
        )
        
        # Add footer with link to full setlist
        embed.set_footer(text="Click the link above to view the full setlist on elgoose.net")
        embed.url = show_url  # This makes the entire embed clickable
        
        await interaction.followup.send(embed=embed)
        print(f"[Setlist] Successfully sent response for {date}")
        
    except ValueError as e:
        print(f"[Setlist Error] Date format validation failed: {str(e)}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Invalid date format. Please use YYYY-MM-DD format.\n"
                "Example: 2024-03-15",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Invalid date format. Please use YYYY-MM-DD format.\n"
                "Example: 2024-03-15",
                ephemeral=True
            )
    except Exception as e:
        error_msg = (
            "An error occurred while fetching the setlist.\n"
            "The error has been logged for investigation.\n"
            "Please try again later or contact support if the issue persists."
        )
        print(f"[Setlist Error] Unexpected error: {str(e)}")
        print(f"[Setlist Error] Error type: {type(e).__name__}")
        traceback.print_exc()  # This prints the stack trace
        if not interaction.response.is_done():
            await interaction.response.send_message(error_msg, ephemeral=True)
        else:
            await interaction.followup.send(error_msg, ephemeral=True)

@bot.tree.command(name="help", description="Display bot command usage")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="ElGoose Bot Commands",
        description="Here are all available commands:",
        color=discord.Color.blue()
    )

    commands = {
        "/setlist <date>": "Get setlist for a specific date (format: YYYY-MM-DD)",
        "/help": "Display this help message"
    }

    for command, description in commands.items():
        embed.add_field(name=command, value=description, inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="live", description="Start live setlist tracking.")
async def live(interaction: discord.Interaction):
    if not live_setlist_tracker:
        await interaction.response.send_message("Live setlist tracker is not initialized.", ephemeral=True)
        return
    
    response = await live_setlist_tracker.start()
    await interaction.response.send_message(response, ephemeral=True)

@bot.tree.command(name="stop", description="Stop live setlist tracking.")
async def stop(interaction: discord.Interaction):
    if not live_setlist_tracker:
        await interaction.response.send_message("Live setlist tracker is not initialized.", ephemeral=True)
        return
        
    response = await live_setlist_tracker.stop()
    await interaction.response.send_message(response, ephemeral=True)

bot.run(TOKEN)