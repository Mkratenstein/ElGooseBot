import discord
import asyncio
from datetime import datetime, timedelta
import html

class LiveSetlist:
    def __init__(self, bot, channel_id, api_fetcher):
        self.bot = bot
        self.channel_id = channel_id
        self.api_fetcher = api_fetcher
        self.is_running = False
        self.task = None

    async def start(self):
        if self.is_running:
            return "Live setlist tracking is already in progress."

        self.is_running = True
        self.task = asyncio.create_task(self._run_tracker())
        return "Live setlist tracking has started."

    async def stop(self):
        if not self.is_running:
            return "Live setlist tracking is not active."

        self.is_running = False
        if self.task:
            self.task.cancel()
        return "Live setlist tracking has been stopped."

    async def _run_tracker(self):
        try:
            channel = await self.bot.fetch_channel(self.channel_id)
        except discord.NotFound:
            print(f"Error: Channel {self.channel_id} not found. Make sure the ID is correct and the bot is in the server.")
            self.is_running = False
            return
        except discord.Forbidden:
            print(f"Error: No permissions to fetch channel {self.channel_id}. Check the bot's role permissions.")
            self.is_running = False
            return
        except Exception as e:
            print(f"An unexpected error occurred when fetching channel: {e}")
            self.is_running = False
            return

        end_time = datetime.now() + timedelta(hours=3.5)
        message = None

        try:
            message = await channel.send("Starting live setlist tracking... Waiting for show data.")
            print(f"Successfully started live tracking in channel {self.channel_id}.")
        except discord.Forbidden:
            print(f"Error: No permissions to send messages in channel {self.channel_id}. Check channel-specific permissions.")
            self.is_running = False
            return
        except Exception as e:
            print(f"An unexpected error occurred when sending the initial message: {e}")
            self.is_running = False
            return

        while self.is_running and datetime.now() < end_time:
            try:
                await self._update_setlist(message)
                await asyncio.sleep(300)  # 5 minutes
            except Exception as e:
                print(f"Error in live setlist update loop: {e}")
                await asyncio.sleep(60) # Wait a minute before retrying

        self.is_running = False
        if message:
            try:
                await message.edit(content="Live setlist tracking has ended.", embed=None)
            except Exception as e:
                print(f"Error editing final message: {e}")

    async def _update_setlist(self, message):
        today = datetime.now().strftime('%Y-%m-%d')
        show_data = await self.api_fetcher(None, today)

        if not show_data:
            await message.edit(content=f"No show scheduled for today ({today}). Waiting for data...", embed=None)
            return

        embed = self._create_embed(show_data, today)
        await message.edit(content=None, embed=embed)

    def _create_embed(self, show_data, date):
        parsed_date = datetime.strptime(date, '%Y-%m-%d')
        venue_name = html.unescape(show_data.get('venuename', 'Unknown'))
        location = show_data.get('location', 'Unknown')
        
        show_url = f"https://elgoose.net/setlists/goose-{parsed_date.strftime('%B-%d-%Y').lower()}-{venue_name.lower().replace(' ', '-')}-{location.lower().replace(' ', '-')}.html"

        embed = discord.Embed(
            title=f"Goose - {parsed_date.strftime('%B %d, %Y')}",
            description=f"**{venue_name}**\n{location}",
            color=discord.Color.from_rgb(252, 186, 3)
        )

        for set_info in show_data.get('sets', []):
            embed.add_field(name=set_info['name'], value=set_info['songs'], inline=False)
        
        if show_data.get('notes'):
            embed.add_field(name="Show Notes", value=show_data['notes'], inline=False)
        
        if show_data.get('coach_notes'):
            notes = "\n".join([f"{n['number']}. {n['text']}" for n in show_data['coach_notes']])
            embed.add_field(name="Coach's Notes", value=notes, inline=False)

        embed.add_field(name="Full Setlist", value=f"[View on elgoose.net]({show_url})", inline=False)
        embed.set_footer(text="Live setlist tracking. Updates every 5 minutes.")
        return embed 