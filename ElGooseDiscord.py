import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import datetime
from typing import Optional
from config import TOKEN, API_BASE_URL
import re
import html  # Add import for HTML entity decoding

# Bot setup with default intents only (no privileged intents needed for slash commands)
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Remove default help command to implement custom one
bot.remove_command('help')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
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
    try:
        # First try to get the setlist directly using the date
        formatted_date = date.replace('-', '')  # Convert YYYY-MM-DD to YYYYMMDD
        print(f"[API] Trying to fetch setlist using date format: {formatted_date}")
        
        # Try the setlists endpoint first
        setlist_data = await fetch_api_data(f"setlists/showdate/{date}.json")
        if setlist_data and isinstance(setlist_data, list):
            # Process the setlist data into sets
            sets = {}
            show_notes = None
            coach_notes = []  # Initialize coach_notes list first
            
            # Extract coach's notes from footnotes first
            note_number = 1
            footnote_map = {}  # Create a mapping of footnotes to numbers
            for song in setlist_data:
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
            for song in setlist_data:
                set_number = song.get('setnumber')
                set_type = song.get('settype', 'Set')
                song_name = song.get('songname', '')
                transition = song.get('transition', '')
                footnote = song.get('footnote', '')
                show_notes = song.get('shownotes')
                
                # Format the song text
                song_text = song_name
                if footnote:
                    song_text += f"[{footnote_map[footnote]}]"
                if transition:
                    # Handle special case for -> transition
                    if transition.strip() == '->':
                        song_text += ' ->'
                    else:
                        song_text += ' >'
                
                # Add to the appropriate set
                set_key = 'Encore' if set_type.lower() == 'encore' or set_type == 'E' or set_type == 'e' else f'Set {set_number}'
                if set_key not in sets:
                    sets[set_key] = []
                sets[set_key].append(song_text)
            
            # Convert sets to list format
            formatted_sets = []
            for set_name, songs in sets.items():
                # Join songs with proper formatting
                formatted_songs = []
                for song in songs:
                    # Clean up any extra spaces
                    song = song.strip()
                    formatted_songs.append(song)
                
                formatted_sets.append({
                    "name": set_name,
                    "songs": ", ".join(formatted_songs)
                })
            
            return {
                "sets": formatted_sets,
                "notes": show_notes,
                "coach_notes": coach_notes if coach_notes else None
            }
            
        # If no setlist data, try the embed endpoint as fallback
        async with aiohttp.ClientSession() as session:
            embed_url = f"https://elgoose.net/api/embed/{formatted_date}.html?headless=1"
            print(f"[API] Trying embed endpoint: {embed_url}")
            async with session.get(embed_url) as response:
                if response.status == 200:
                    text = await response.text()
                    if text and "setlist" in text.lower():
                        # Parse the HTML content
                        text = re.sub(r'<[^>]+>', ' ', text)  # Remove HTML tags
                        text = re.sub(r'\s+', ' ', text)      # Normalize whitespace
                        
                        sets = []
                        
                        # Extract Set 1
                        set1_match = re.search(r'Set 1:(.*?)(?=Set 2:|Encore:|Show Notes:|Coach\'s Notes:|$)', text)
                        if set1_match:
                            sets.append({"name": "Set 1", "songs": set1_match.group(1).strip()})
                        
                        # Extract Set 2
                        set2_match = re.search(r'Set 2:(.*?)(?=Encore:|Show Notes:|Coach\'s Notes:|$)', text)
                        if set2_match:
                            sets.append({"name": "Set 2", "songs": set2_match.group(1).strip()})
                        
                        # Extract Encore
                        encore_match = re.search(r'Encore:(.*?)(?=Show Notes:|Coach\'s Notes:|$)', text)
                        if encore_match:
                            sets.append({"name": "Encore", "songs": encore_match.group(1).strip()})
                        
                        # Extract notes
                        notes_match = re.search(r'Show Notes:(.*?)(?=Coach\'s Notes:|$)', text)
                        coach_notes_match = re.search(r'Coach\'s Notes:(.*?)(?=\[|\(|$)', text)
                        
                        # Extract coach's notes with numbers
                        coach_notes = []
                        if coach_notes_match:
                            coach_text = coach_notes_match.group(1)
                            note_matches = re.finditer(r'\[(\d+)\](.*?)(?=\[\d+\]|$)', coach_text)
                            for match in note_matches:
                                coach_notes.append({
                                    "number": match.group(1),
                                    "text": match.group(2).strip()
                                })
                        
                        return {
                            "sets": sets,
                            "notes": notes_match.group(1).strip() if notes_match else None,
                            "coach_notes": coach_notes if coach_notes else None
                        }
        
        return None

    except Exception as e:
        print(f"[API] Error fetching show details: {str(e)}")
        return None

@bot.tree.command(name="setlist", description="Get setlist for a specific date (YYYY-MM-DD)")
async def setlist(interaction: discord.Interaction, date: str):
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

        # Create the embed with all available information
        show_url = f"https://elgoose.net/setlists/goose-{date}.html"
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

        # Add coach's notes first if available
        if show_data.get('coach_notes'):
            if isinstance(show_data['coach_notes'], list):
                notes = []
                for note in show_data['coach_notes']:
                    if isinstance(note, dict):
                        notes.append(f"    [{note['number']}] {note['text']}")
                if notes:
                    embed.add_field(
                        name="Coach's Notes:",
                        value="\n".join(notes),
                        inline=False
                    )

        # Add show notes if available
        if show_data.get('notes'):
            notes = show_data['notes']
            # Clean up the notes text
            notes = re.sub(r'\s+', ' ', notes).strip()
            embed.add_field(
                name="Show Notes:",
                value=notes,
                inline=False
            )

        # Add footer with timestamp
        updated_at = show_data.get('updated_at', 'Unknown')
        footer_text = f"Last updated: {updated_at}"
        embed.set_footer(text=footer_text, icon_url="https://elgoose.net/favicon.ico")
        
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
        print(f"[Setlist Error] Stack trace:", exc_info=True)
        
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

bot.run(TOKEN)