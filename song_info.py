import aiohttp
import urllib.parse
import html

API_BASE_URL = "https://elgoose.net/api/v2"

def format_song_name(song_name: str) -> str:
    """
    Formats the song name to title case, with specific exceptions.
    """
    exceptions = ['(satellite)', '(dawn)']
    words = song_name.lower().split()
    formatted_words = [word if word in exceptions else word.capitalize() for word in words]
    return ' '.join(formatted_words)

async def get_song_info(song_name: str) -> dict:
    """
    Fetches and processes song statistics from the ElGoose.net API.

    Args:
        song_name: The name of the song to look up.

    Returns:
        A dictionary containing the song's play count, first play, and last play details.
        Returns None if the song is not found or an error occurs.
    """
    encoded_song_name = urllib.parse.quote_plus(song_name)
    url = f"{API_BASE_URL}/setlists/songname/{encoded_song_name}.json?order_by=showdate&direction=asc"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                # Log error or handle non-200 responses
                return None
            
            data = await response.json()

            if data.get("error") or not data.get("data"):
                return None  # Song not found or API error

            all_plays = data["data"]
            
            # Filter for Goose plays only
            goose_plays = [play for play in all_plays if play.get('artist', '').lower() == 'goose']
            
            if not goose_plays:
                return None # No Goose plays found for this song

            times_played = len(goose_plays)
            
            first_play = goose_plays[0]
            last_play = goose_plays[-1]
            second_last_play = goose_plays[-2] if times_played > 1 else None

            song_info = {
                "song_name": html.unescape(first_play.get("songname", "Unknown Song")),
                "times_played": times_played,
                "first_play": {
                    "date": first_play.get("showdate"),
                    "venue": html.unescape(first_play.get("venuename", "Unknown Venue")),
                    "url": f"https://elgoose.net/setlists/{first_play.get('permalink')}"
                },
                "last_play": {
                    "date": last_play.get("showdate"),
                    "venue": html.unescape(last_play.get("venuename", "Unknown Venue")),
                    "url": f"https://elgoose.net/setlists/{last_play.get('permalink')}"
                },
                "second_last_play": None
            }

            if second_last_play:
                song_info["second_last_play"] = {
                    "date": second_last_play.get("showdate"),
                    "venue": html.unescape(second_last_play.get("venuename", "Unknown Venue")),
                    "url": f"https://elgoose.net/setlists/{second_last_play.get('permalink')}"
                }
            
            return song_info 