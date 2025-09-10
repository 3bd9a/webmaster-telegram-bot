# WebMaster Bot - Website Downloader

A Telegram bot that allows users to download entire websites with full JavaScript support, built with Python and Playwright.

## Features

- Download complete websites with all assets
- Full JavaScript rendering support
- User rate limiting and security features
- Admin panel with user management
- Clean and intuitive interface
- Support for multiple download formats
- Automatic cleanup of temporary files

## Requirements

- Python 3.8+
- Playwright
- python-telegram-bot
- SQLAlchemy
- aiohttp
- BeautifulSoup4
- python-dotenv

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/webmaster-bot.git
cd webmaster-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install
```

4. Create a `.env` file and configure your settings:
```
BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_user_id
```

## Usage

1. Start the bot:
```bash
python main.py
```

2. In Telegram, start a chat with your bot and use the following commands:
   - `/start` - Start using the bot
   - `/download <url>` - Download a website
   - `/help` - Show help message
   - `/stats` - Show your download statistics

## Admin Commands

- `/broadcast <message>` - Send a message to all users
- `/ban <user_id>` - Ban a user
- `/unban <user_id>` - Unban a user
- `/cleanup` - Clean up temporary files
- `/sysinfo` - Show system information

## Project Structure

```
web-bot-main/
├── bot/
│   ├── __init__.py
│   ├── handlers.py  # Command and message handlers
│   └── keyboards.py  # Inline keyboards
├── services/
│   ├── downloader.py  # Website download logic
│   ├── file_manager.py  # File management
│   └── __init__.py
├── utils/
│   ├── helpers.py  # Helper functions
│   ├── logger.py  # Logging configuration
│   └── __init__.py
├── .env.example  # Example environment variables
├── config.py  # Configuration settings
├── database.py  # Database models and setup
├── main.py  # Bot entry point
└── README.md  # Arabic documentation
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Support

For support, please open an issue on the GitHub repository.
