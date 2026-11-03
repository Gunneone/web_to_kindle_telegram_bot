"""
Entry point of the Telegram bot: python src/telegram_bot.py

The bot itself lives in the `bot` package (handlers, texts, delivery pipeline).
"""

from bot.app import main

if __name__ == '__main__':
    main()
