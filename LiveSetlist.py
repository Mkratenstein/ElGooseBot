import discord
import asyncio
from datetime import datetime, timedelta
import html
import pytz
from exceptions import APIError
from embeds import create_setlist_embed

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
        print(f"[LiveTracker] Stop method called. Current state: is_running={self.is_running}")
        if not self.is_running:
            print("[LiveTracker] Tracker is not active. Nothing to stop.")
            return "Live setlist tracking is not active."

        self.is_running = False
        print("[LiveTracker] Set is_running to False.")
        if self.task:
            print("[LiveTracker] Cancelling tracker task.")
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                print("[LiveTracker] Task successfully cancelled.")
        else:
            print("[LiveTracker] No task found to cancel.")
            
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

        eastern_tz = pytz.timezone('America/New_York')
        show_date = datetime.now(eastern_tz).strftime('%Y-%m-%d')
        end_time = datetime.now(eastern_tz) + timedelta(hours=3.5)
        message = None
        last_show_data = None

        try:
            message = await channel.send(f"Starting live setlist tracking for {show_date}... Waiting for show data.")
            print(f"Successfully started live tracking in channel {self.channel_id}.")
        except discord.Forbidden:
            print(f"Error: No permissions to send messages in channel {self.channel_id}. Check channel-specific permissions.")
            self.is_running = False
            return
        except Exception as e:
            print(f"An unexpected error occurred when sending the initial message: {e}")
            self.is_running = False
            return

        while self.is_running and datetime.now(eastern_tz) < end_time:
            try:
                show_data_result = await self._update_setlist(message, show_date)
                if show_data_result:
                    last_show_data = show_data_result
                await asyncio.sleep(300)  # 5 minutes
            except Exception as e:
                print(f"Error in live setlist update loop: {e}")
                await asyncio.sleep(60) # Wait a minute before retrying

        self.is_running = False
        if message:
            try:
                # If we have show data, edit the embed to remove the 'live' footer.
                if last_show_data:
                    final_embed = create_setlist_embed(last_show_data, is_live=False)
                    await message.edit(embed=final_embed)
                
                # Send a new, separate message to announce the end of tracking.
                await message.channel.send("Live setlist tracking has ended.")
            except Exception as e:
                print(f"Error finalizing live tracking messages: {e}")

    async def _update_setlist(self, message, show_date):
        try:
            show_data = await self.api_fetcher(None, show_date)
            print(f"[LiveTracker] Fetched show_data: {show_data}")

            if not show_data:
                print("[LiveTracker] No show data found. Posting 'No show scheduled' message.")
                await message.edit(content=f"No show scheduled for today ({show_date}). Waiting for data...", embed=None)
                return None

            embed = create_setlist_embed(show_data, is_live=True)
            
            print("[LiveTracker] Embed created. Attempting to edit message.")
            await message.edit(content=None, embed=embed)
            print("[LiveTracker] Message successfully edited.")
            return show_data
            
        except APIError as e:
            print(f"[LiveTracker] An API error occurred: {e}")
            await message.edit(content=f"Could not connect to the elgoose.net API. Retrying in 5 minutes...", embed=None)
            return None
        except Exception as e:
            print(f"[LiveTracker] An unexpected error occurred in _update_setlist: {e}")
            # Optional: Send a more generic error message to Discord
            await message.edit(content="An unexpected error occurred. See logs for details.", embed=None)
            return None 