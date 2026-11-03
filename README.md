# Web to Kindle Telegram Bot

A Telegram bot that allows users to scrape web articles from any website, convert them to Kindle-compatible EPUB files, and send them directly to their Kindle devices via email. Substack articles are specially optimized for the best reading experience.

## 🚀 Try the Deployed Bot

You can try the bot immediately without any setup at: **[@SubstackKindleBot](https://t.me/SubstackKindleBot)**

Or deploy your own instance using the instructions below.

## Quick Start

### Option 1: Use the Deployed Bot (Easiest)
1. Visit [@SubstackKindleBot](https://t.me/SubstackKindleBot) on Telegram ([open setup directly](https://t.me/SubstackKindleBot?start=setup))
2. Send `/start` and tap **Set up Kindle** (or **Just send me EPUB files** if you don't use a Kindle)
3. Follow the three steps: Kindle address → approve the sender at Amazon → test book
4. Send any article link, or share it to the bot from your browser

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
- **Medium support:** Medium blocks plain HTTP clients, so the bot retries with browser impersonation and falls back to the author's RSS feed (recent posts only).
- **Paywalled posts:** paid-only Substack and member-only Medium posts are sent as a preview with a notice linking to the full post.
- Real titles, authors, dates and languages from page metadata; lazy-loaded images are kept and converted to Kindle-friendly JPEG/PNG. See [docs/site-compatibility.md](docs/site-compatibility.md) for the tested sites and `tests/site_survey/run.py` to rerun the survey.
- Converts extracted content to an EPUB format compatible with Kindle devices.
- Integrates with a Telegram bot for an intuitive user interface.
- Sends the EPUB file to the user's Kindle email address.
- Allows configuration of Kindle email within the bot.
- **Guided setup:** a three-step wizard with a copy button for the sender address, a link to Amazon's settings and a test book that confirms delivery works.
- **Live progress:** reactions on your message (👀 → ✍ → 👌) and a status message that turns into a result card with buttons (original, EPUB here, resend).
- **Kindle, chat or both:** books go to your Kindle, arrive in the chat as EPUB files (for Kobo, Apple Books, …), or both. A link sent before setup is delivered to the chat right away.
- **Links from anywhere:** plain links, hyperlinked text, photo captions and forwarded posts, up to 10 links per message.
- **History & resend:** `/history` lists your recent books; sending a link again within 30 days asks first.
- **Guest mode:** in any chat, reply to a message with a link and mention the bot; the book is delivered via your private chat with it.
- **English and German:** messages, command menu and bot description follow your Telegram language, or the language picked in `/settings`.
- **Configurable image link preservation:** Toggle whether to preserve clickable links on images (useful for zoom functionality).
- **Automatic file cleanup:** Monitors disk space and automatically deletes old HTML and EPUB files when space is low (below 2GB) to prevent storage issues while keeping recent files for debugging.

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

   # Optional: Telegram chat ID that gets a notice (title + user) per book and error reports
   ADMIN_ID=123456789
   ```

   The bot sets its command menu and description (English and German) itself on startup.
   To allow guest mode (mentioning the bot in chats it isn't a member of), enable it for your bot in
   [@BotFather](https://t.me/BotFather).

4. **Run the Bot:**

   **Option A: Direct Python execution**
   ```bash
   python src/telegram_bot.py
   ```

   **Option B: Using Docker Compose (Recommended for production)**
   ```bash
   docker compose up -d
   ```
   
   This will start both the Telegram bot and the disk monitoring service that automatically manages old files to prevent storage issues.

---

## Usage

### 1. Start and set up

Send `/start`. New users choose between **Set up Kindle** and **Just send me EPUB files**. The Kindle setup
takes three steps:

1. **Kindle address:** send the address of your Kindle (ends in `@kindle.com`, `@free.kindle.com` or `@kindle.cn`).
2. **Approve the sender:** add the bot's sending address (`EMAIL_FROM`) to the *Approved Personal Document
   E-mail List* in your Amazon settings. The bot shows the address with a copy button and links to Amazon.
3. **Test book:** the bot sends a one-page book. If it doesn't arrive, tap **No** for a troubleshooting checklist.

### 2. Send an article

Paste a link, share it to the bot from your browser or app, or forward a post that contains links. Each link
gets a status message that ends as a result card with **Original**, **EPUB here** and **Resend** buttons.
Failed links get a **Retry** button.

### 3. From any chat (guest mode)

Reply to a message that contains a link and mention the bot. The chat gets a short confirmation (no personal
details); the book is delivered and confirmed in your private chat with the bot.

### 4. Settings

`/settings` opens one panel to change the Kindle address, the delivery (Kindle, chat or both), image links,
the language, to send a test book or to delete your data.

---

## How it Works

1. **Scraping Content:**
   - The `web_scraper.py` extracts the main content, title, and author from web articles. For Substack articles, it provides enhanced extraction with removal of unnecessary buttons and ads.

2. **Converting to EPUB:**
   - In `epub_converter.py`, the content is packaged into an EPUB book, embedding metadata like the title, author, and images.

3. **Sending Emails:**
   - The `email_sender.py` sends the generated EPUB to the user's Kindle email via an SMTP server.

4. **Delivery Service:**
   - `src/core/` is shared by every front end: the user and history database (`db.py`), Kindle address checks (`kindle.py`) and the pipeline that fetches, builds, mails and records each book (`pipeline.py`). It doesn't depend on Telegram, so another front end, such as a web app, can reuse it as-is.

5. **Telegram Interface:**
   - `src/bot/` is the Telegram front end on top of `core`. Users interact with the bot using straightforward commands to configure their Kindle email, toggle settings, and process articles from any website.

6. **Automatic File Management:**
   - The `disk_monitor.py` service continuously monitors disk space and automatically removes the oldest HTML and EPUB files when available space falls below 2GB, ensuring the system doesn't run out of storage while preserving recent files for debugging purposes.

---

## Bot Commands

- `/start` - Welcome screen and setup (deep links: `?start=setup`, `?start=settings`, `?start=help`)
- `/settings` - Kindle address, delivery, image links, language, test book, delete data
- `/history` - Your recent books, with a button to send each one again
- `/help` - How to send links and what to check when nothing arrives
- `/privacy` - What the bot stores, and a button to delete your data
- `/send <link>` - Send a link (plain links work without the command)
- `/cancel` - Stop entering a Kindle address

`/config`, `/imagelinks` and `/delete` from earlier versions still work but are no longer in the menu.

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
