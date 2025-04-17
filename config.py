import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Discord token from environment variable
TOKEN = os.getenv('DISCORD_TOKEN')

# Get API base URL from environment variable (with fallback)
API_BASE_URL = os.getenv('API_BASE_URL', 'https://elgoose.net/api/v2')

# Validate required environment variables
if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is not set. Please check your .env file.")

# Add this file to .gitignore to prevent it from being tracked by version control
# Create a config.example.py file with this same structure but with a placeholder token
# for other developers to use as a template 