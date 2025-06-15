# ElGooseBot

A Discord bot that provides information about Goose concerts and setlists by interfacing with the elgoose.net API.

## Features

- Fetch setlists for specific dates
- View show details including sets, encores, and notes
- Get coach's notes and transitions between songs

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   ```
4. Edit the `.env` file and add your Discord bot token:
   ```
   DISCORD_TOKEN=your_discord_token_here
   ```
5. Run the bot:
   ```bash
   python ElGooseDiscord.py
   ```

## Commands

- `/setlist [date]` - Get the setlist for a specific date (format: YYYY-MM-DD)
- `/help` - Display bot command usage

## Security Notes

- Never commit your `.env` file or `config.py` to version control
- Keep your Discord bot token secure
- The `.env` file is already in `.gitignore` to prevent accidental commits

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 