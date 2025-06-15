# Example configuration file
# Copy this file to config.py and update with your values
# For deployment, set these as environment variables instead

import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Required: Your Discord bot token
# For local development: Create a .env file with DISCORD_TOKEN=your_token_here
# For deployment: Set DISCORD_TOKEN environment variable
TOKEN = os.getenv('DISCORD_TOKEN')

# Optional: API base URL (defaults to https://elgoose.net/api/v2)
API_BASE_URL = os.getenv('API_BASE_URL', 'https://elgoose.net/api/v2') 