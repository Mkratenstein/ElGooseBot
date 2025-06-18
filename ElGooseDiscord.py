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
from exceptions import APIError
from embeds import create_setlist_embed

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

def _process_setlist_data(base_show_data: dict, setlist_data: list) -> dict:
    """Processes raw setlist data and merges it into the base show data."""
    final_show_data = base_show_data.copy()
    if not setlist_data or not isinstance(setlist_data, list):
        return final_show_data

    goose_songs = [s for s in setlist_data if s.get('artist', '').lower() == 'goose']
    if not goose_songs:
        return final_show_data

    sets = {}
    show_notes = None
    coach_notes = []
    footnote_map = {}
    note_number = 1

    for song in goose_songs:
        if footnote := song.get('footnote'):
            if footnote not in footnote_map:
                footnote_map[footnote] = str(note_number)
                coach_notes.append({"number": str(note_number), "text": footnote})
                note_number += 1

    for song in goose_songs:
        set_key = 'Encore' if song.get('settype', '').lower() in ['encore', 'e'] else f"Set {song.get('setnumber')}"
        if set_key not in sets:
            sets[set_key] = ""

        song_text = song.get('songname', '')
        if footnote := song.get('footnote'):
            song_text += f"[{footnote_map.get(footnote, '?')}]"
        
        sets[set_key] += song_text + song.get('transition', '').strip() + " "
        
        if notes := song.get('shownotes'):
            show_notes = notes

    formatted_sets = []
    for name, songs in sets.items():
        cleaned_songs = songs.strip()
        if cleaned_songs.endswith(',') or cleaned_songs.endswith('>'):
            cleaned_songs = cleaned_songs[:-1].strip()
        formatted_sets.append({"name": name, "songs": cleaned_songs})

    final_show_data['sets'] = formatted_sets
    if show_notes:
        final_show_data['notes'] = show_notes
    if coach_notes:
        final_show_data['coach_notes'] = coach_notes
        
    return final_show_data

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
                
                if response.status == 200:
                    try:
                        json_data = await response.json(content_type=None)
                        print(f"[API Response] Parsed JSON: {str(json_data)[:500]}...")
                        
                        if isinstance(json_data, dict) and 'error' in json_data:
                            if json_data['error']:
                                print(f"[API Error] API returned error message: {json_data['error_message']}")
                                # Treat API-reported error as a failure
                                raise APIError(f"API returned error: {json_data['error_message']}")
                            return json_data.get('data')
                        return json_data
                    except Exception as e:
                        print(f"[API Error] JSON parsing failed: {str(e)}")
                        raise APIError("Failed to parse API response.") from e
                else:
                    print(f"[API Error] Non-200 status code: {response.status}")
                    raise APIError(f"API returned status code {response.status}")
        except aiohttp.ClientError as e:
            print(f"[API Error] Network error: {str(e)}")
            raise APIError(f"A network error occurred: {e}") from e
        except Exception as e:
            print(f"[API Error] Unexpected error in fetch_api_data: {str(e)}")
            raise APIError(f"An unexpected error occurred: {e}") from e

async def fetch_show_details(show_id: str, date: str = None) -> dict:
    """Helper function to fetch detailed show information including setlist"""
    try:
        base_show_data_list = await fetch_api_data(f"shows/showdate/{date}.json")
        if not base_show_data_list or not isinstance(base_show_data_list, list):
            return None

        final_show_data = next((show for show in base_show_data_list if show.get('artist', '').lower() == 'goose'), None)
        if not final_show_data:
            return None
    except APIError as e:
        print(f"[ShowDetails] Could not fetch base show data: {e}")
        return None

    try:
        setlist_data = await fetch_api_data(f"setlists/showdate/{date}.json")
        # Process and merge setlist data if available
        return _process_setlist_data(final_show_data, setlist_data)
    except APIError as e:
        print(f"[ShowDetails] Could not fetch setlist details: {e}. Returning base show info.")
        return final_show_data  # Return base data if setlist fails

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
        show_data = await fetch_show_details(None, date)
        
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
        
        # Create embed using the new centralized function
        embed = create_setlist_embed(show_data)
        
        # Send response
        await interaction.followup.send(embed=embed)
        print(f"[Setlist] Response sent successfully")

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
    print("[StopCommand] /stop command received.")
    if not live_setlist_tracker:
        print("[StopCommand] Live setlist tracker is not initialized.")
        await interaction.response.send_message("Live setlist tracker is not initialized.", ephemeral=True)
        return
        
    print("[StopCommand] Calling tracker.stop().")
    response = await live_setlist_tracker.stop()
    print(f"[StopCommand] Received response from tracker: '{response}'")
    await interaction.response.send_message(response, ephemeral=True)
    print("[StopCommand] Sent confirmation message to user.")

bot.run(TOKEN)