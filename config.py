import os
from dotenv import load_dotenv

# Try to load environment variables from .env file if it exists
load_dotenv()

# Get Discord token from environment variable
TOKEN = os.getenv('DISCORD_TOKEN')

# Get API base URL from environment variable (with fallback)
API_BASE_URL = os.getenv('API_BASE_URL', 'https://elgoose.net/api/v2')

# Validate required environment variables
if not TOKEN:
    print("Warning: DISCORD_TOKEN environment variable is not set.")
    print("Please set the DISCORD_TOKEN environment variable in your deployment environment.")
    print("For local development, create a .env file with DISCORD_TOKEN=your_token_here")
    raise ValueError("DISCORD_TOKEN environment variable is not set")

# Add this file to .gitignore to prevent it from being tracked by version control
# Create a config.example.py file with this same structure but with a placeholder token
# for other developers to use as a template 