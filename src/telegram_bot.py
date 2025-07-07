import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from web_scraper import get_substack_content

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
EMAIL = 0

# Store user emails
user_emails = {}

# Load environment variables
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Hi! Use /config to set up your Kindle email. Afterwards use /send to process a Substack article.')


async def config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the email collection process."""
    user_id = update.effective_user.id
    current_email = user_emails.get(user_id)
    message = 'Please enter your Kindle email address:'
    if current_email:
        message = f'Your current Kindle email is: {current_email}\nEnter a new email to update:'
    await update.message.reply_text(message)
    return EMAIL


async def process_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the received email and provide further instructions."""
    email = update.message.text
    if not email.endswith('@kindle.com'):
        await update.message.reply_text('Please provide a valid Kindle email address (ending with @kindle.com)')
        return EMAIL
    user_id = update.effective_user.id
    user_emails[user_id] = email
    await update.message.reply_text(
        f'Thank you! Now please add to_kindle@gunneone.de to your approved sender list in your Kindle settings.'
    )
    return ConversationHandler.END


async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /send command."""
    await update.message.reply_text('Please provide the Substack article link:')


async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the Substack link."""
    url = update.message.text
    try:
        content = get_substack_content(url)
        await update.message.reply_text('Content retrieved successfully!')
    except Exception as e:
        await update.message.reply_text(f'Error: {str(e)}')


def main():
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Add conversation handler for email collection
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('config', config)],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_email)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("send", send))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_link))

    # Start the bot
    application.run_polling()


if __name__ == '__main__':
    main()
