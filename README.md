# Web to Kindle Telegram Bot

A Telegram bot that allows users to scrape web articles from any website, convert them to Kindle-compatible EPUB files, and send them directly to their Kindle devices via email. Substack articles are specially optimized for the best reading experience.

## 🚀 Try the Deployed Bot

You can try the bot immediately without any setup at: **[@SubstackKindleBot](https://t.me/SubstackKindleBot)**

Or deploy your own instance using the instructions below.

## Quick Start

### Option 1: Use the Deployed Bot (Easiest)
1. Visit [@SubstackKindleBot](https://t.me/SubstackKindleBot) on Telegram
2. Send `/start` to begin
3. Configure your Kindle email with `/config`
4. Send any article URL to convert and receive on your Kindle

### Option 2: Use the CLI Tool (For Developers)
```bash
git clone https://github.com/gunneone/web-to-kindle-telegram-bot.git
cd web-to-kindle-telegram-bot
pip install -r requirements.txt
python cli.py https://your-article-url
```

### Option 3: Deploy Your Own Bot
Follow the full installation instructions below.

## Features

- **Multiple interfaces:** Use via Telegram bot or command-line interface (CLI)
- Web scraper to extract content from any website article, with special optimizations for Substack articles that remove unnecessary elements like buttons and ads.
- Converts extracted content to an EPUB format compatible with Kindle devices.
- Integrates with a Telegram bot for an intuitive user interface.
- Sends the EPUB file to the user's Kindle email address.
- Allows configuration of Kindle email within the bot.
- **Configurable image link preservation:** Toggle whether to preserve clickable links on images (useful for zoom functionality).

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

### 3. **Configure Settings:**

   Use `/settings` to view your current configuration, including:
   - Kindle email address
   - Image link preservation setting

### 4. **Toggle Image Link Preservation:**

   Use `/imagelinks` to toggle whether clickable links on images are preserved in the EPUB. When enabled, you can click on images to zoom or view full resolution versions.

### 5. **Send an Article:**

   Use `/send` followed by any web article URL to send content directly to your Kindle. Alternatively:
   - Send `/send` without an URL, and the bot will prompt you to provide a link.

### 6. **Approve the Sender's Email:**

   Add `EMAIL_FROM` (as set in `.env`) to your approved senders list at [Amazon Kindle Settings](https://www.amazon.com/myk).

---

## How it Works

1. **Scraping Content:**
   - The `web_scraper.py` extracts the main content, title, and author from web articles. For Substack articles, it provides enhanced extraction with removal of unnecessary buttons and ads.

2. **Converting to EPUB:**
   - In `epub_converter.py`, the content is packaged into an EPUB book, embedding metadata like the title, author, and images.

3. **Sending Emails:**
   - The `email_sender.py` sends the generated EPUB to the user's Kindle email via an SMTP server.

4. **Telegram Interface:**
   - Users interact with the bot using straightforward commands to configure their Kindle email, toggle settings, and process articles from any website.

---

## Bot Commands

- `/start` - Initialize the bot and view welcome message
- `/config` - Configure or update your Kindle email address  
- `/settings` - View all current settings (email, image link preservation)
- `/imagelinks` - Toggle image link preservation on/off
- `/cancel` - Cancel current operation

## CLI Usage

For users who prefer command-line tools or want to integrate the functionality into scripts, a CLI tool is available:

### Quick Start with CLI

```bash
# Install dependencies
pip install -r requirements.txt

# Process any web article (basic usage)
python cli.py https://example.com/article-title

# Process article with image links preserved (clickable images) 
python cli.py --preserve-image-links https://example.com/article-title
```

### CLI Features

- **Direct processing:** Convert web articles to EPUB without needing a Telegram bot (supports any website, with special optimizations for Substack)
- **Image link preservation:** Use `--preserve-image-links` flag to keep clickable links on images
- **Batch processing capability:** Can be integrated into scripts for multiple articles
- **Email integration:** Automatically sends EPUB to configured Kindle email

The CLI tool also supports the preserve image links feature:

```bash
# Process article with image links preserved
python cli.py --preserve-image-links https://example.com/article

# Process article with image links removed (default)
python cli.py https://example.com/article
```
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
- **[click](https://pypi.org/project/click/):** Command-line interface framework.
- **[readability-lxml](https://pypi.org/project/readability-lxml/):** Content extraction and readability improvements.
- **[validators](https://pypi.org/project/validators/):** URL and data validation.

Install dependencies via:

```bash
pip install -r requirements.txt
```
---

## Support

For support, please open an issue in the repository.
