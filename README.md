# Web to Kindle Telegram Bot

A Telegram bot that allows users to scrape Substack articles, convert them to Kindle-compatible EPUB files, and send them directly to their Kindle devices via email.

## Features

- Web scraper to extract Substack article content, removing unnecessary elements like buttons and ads.
- Converts extracted content to an EPUB format compatible with Kindle devices.
- Integrates with a Telegram bot for an intuitive user interface.
- Sends the EPUB file to the user's Kindle email address.
- Allows configuration of Kindle email within the bot.

---

## Installation

### Prerequisites

- **Python 3.12 or higher**
- **SMTP server access:** Required to send emails to Kindle devices.
- **Telegram Bot Token:** Obtain from the [Telegram BotFather](https://core.telegram.org/bots#6-botfather).

### Steps

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/gunneone/web-to-kindle-telegram-bot.git
   cd web-to-kindle-telegram-bot
   ```

2. **Set Up the Python Environment:**

   Use `pyenv` to ensure you're using the correct Python version.

   ```bash
   pyenv install 3.12.11
   pyenv local 3.12.11
   pip install -r requirements.txt
   ```

3. **Configuration:**

   Copy the example `.env` file and fill in your configuration.

   ```bash
   cp .env.example .env
   ```

   Populate `.env` with:

   ```dotenv
   # Telegram Bot Token
   TELEGRAM_TOKEN=YOUR:BOT_TOKEN

   # Email configuration
   EMAIL_FROM=your@email.domain
   EMAIL_PASSWORD=your-email-password

   # SMTP configuration
   SMTP_HOST=your_smtp_server
   SMTP_PORT=587
   ```

4. **Run the Bot:**

   Start the bot using:

   ```bash
   python src/telegram_bot.py
   ```

---

## Usage

### 1. **Start the Bot:**

   Use `/start` to initialize the bot and view a welcome message.

### 2. **Configure Kindle Email:**

   Use `/config` to set or update your Kindle email. You will be prompted to input an email address ending in `@kindle.com`.

### 3. **Send an Article:**

   Use `/send` followed by a Substack article URL to send content directly to your Kindle. Alternatively:
   - Send `/send` without an URL, and the bot will prompt you to provide a link.

### 4. **Approve the Sender's Email:**

   Add `EMAIL_FROM` (as set in `.env`) to your approved senders list at [Amazon Kindle Settings](https://www.amazon.com/myk).

---

## How it Works

1. **Scraping Content:**
   - The `web_scraper.py` extracts the main content, title, and author from Substack articles. Unnecessary buttons and ads are removed.

2. **Converting to EPUB:**
   - In `epub_converter.py`, the content is packaged into an EPUB book, embedding metadata like the title, author, and images.

3. **Sending Emails:**
   - The `email_sender.py` sends the generated EPUB to the user's Kindle email via an SMTP server.

4. **Telegram Interface:**
   - Users interact with the bot using straightforward commands to configure their Kindle email and process Substack articles.
---

## EPUB Compatibility Notes

- **Kindle Compatibility:** The EPUB files are optimized for Kindle devices. Some features might not work on other platforms.

---

## Dependencies

The following packages are used in this project:

- **[requests](https://pypi.org/project/requests/):** HTTP requests for web scraping.
- **[beautifulsoup4](https://pypi.org/project/beautifulsoup4/):** HTML parsing for scraping articles.
- **[EbookLib](https://pypi.org/project/EbookLib/):** For creating EPUB files.
- **[python-telegram-bot](https://pypi.org/project/python-telegram-bot/):** Telegram API integration.
- **[python-dotenv](https://pypi.org/project/python-dotenv/):** Managing environment variables.
- **[SQLAlchemy](https://pypi.org/project/SQLAlchemy/):** Database management using SQLite.

Install dependencies via:

```bash
pip install -r requirements.txt
```
---

## Support

For support, please open an issue in the repository.
