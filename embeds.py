import discord
import datetime
import html

def create_setlist_embed(show_data: dict, is_live: bool = False) -> discord.Embed:
    """Creates a standardized Discord embed for setlist information."""
    date_str = show_data.get('showdate')
    parsed_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    
    venue_name = html.unescape(show_data.get('venuename', 'Unknown Venue'))
    location = show_data.get('location', 'Unknown Location')
    
    permalink = show_data.get('permalink')
    show_url = f"https://elgoose.net/setlists/{permalink}" if permalink else "https://elgoose.net"

    embed = discord.Embed(
        title=f"Goose - {parsed_date.strftime('%B %d, %Y')}",
        url=show_url,
        description=f"**{venue_name}**\n{location}",
        color=discord.Color.from_rgb(252, 186, 3)
    )

    for set_info in show_data.get('sets', []):
        embed.add_field(name=f"**{set_info['name']}:**", value=set_info['songs'] or "TBA", inline=False)
    
    if show_data.get('notes'):
        embed.add_field(name="Show Notes:", value=show_data['notes'], inline=False)
    
    if show_data.get('coach_notes'):
        notes = "\n".join([f"[{n['number']}] {n['text']}" for n in show_data['coach_notes']])
        embed.add_field(name="Coach's Notes:", value=notes, inline=False)

    if is_live:
        embed.set_footer(text="Live setlist tracking. Updates every 5 minutes.")
    
    return embed 

def create_song_embed(song_data: dict) -> discord.Embed:
    """Creates a standardized Discord embed for song statistics."""
    
    first_play_info = song_data['first_play']
    last_play_info = song_data['last_play']

    embed = discord.Embed(
        title=f"Song Stats: {song_data['song_name']}",
        color=discord.Color.from_rgb(252, 186, 3)
    )

    embed.add_field(name="Total Times Played", value=str(song_data['times_played']), inline=False)
    
    embed.add_field(
        name="First Time Played", 
        value=(
            f"**Date:** {first_play_info['date']}\n"
            f"**Venue:** [{first_play_info['venue']}]({first_play_info['url']})"
        ), 
        inline=True
    )
    
    embed.add_field(
        name="Last Time Played", 
        value=(
            f"**Date:** {last_play_info['date']}\n"
            f"**Venue:** [{last_play_info['venue']}]({last_play_info['url']})"
        ), 
        inline=True
    )
    
    return embed 