import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
import validators

from src.email_sender import send_email
from src.web_scraper import get_website_content
from src.epub_converter import convert_to_epub
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker,declarative_base

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add at the top of the file with other states
EMAIL = 0

# Database setup
Base = declarative_base()
engine = create_engine('sqlite:///users.db')
Session = sessionmaker(bind=engine)


class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    kindle_email = Column(String)
    last_book_received_date = Column(String)


# Load environment variables
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    logger.info(f"User {update.effective_user.id} started the bot")
    await update.message.reply_text(
        'Hi! Use /config to set up your Kindle email. Afterwards just send me any article link to process.')


async def config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the email collection process."""
    user_id = update.effective_user.id
    logger.debug(f"User {user_id} started email configuration")
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    message = 'Please enter your Kindle email address:'
    if user and user.kindle_email:
        message = f'Your current Kindle email is: {user.kindle_email}\nEnter a new email to update:'
        logger.debug(f"User {user_id} has existing email: {user.kindle_email}")
    session.close()
    await update.message.reply_text(message)
    logger.debug(f"User {user_id} entering EMAIL state")
    return EMAIL

async def is_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if the input is a URL."""
    text = update.message.text
    user_id = update.effective_user.id
    if validators.url(text):
        logger.debug(f"Received URL instead of email from user {user_id}")
        return True
    else:
        return False

async def process_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the received email and provide further instructions."""
    text = update.message.text
    user_id = update.effective_user.id


    if not text.endswith('@kindle.com'):
        # Check if the input looks like a URL
        if is_url(update, context):
            logger.debug(f"Received URL instead of email from user {user_id}")
            return await process_link(update, context)
        else:
            logger.debug(f"Invalid email format provided by user {user_id}: {text}")
            await update.message.reply_text('Please provide a valid Kindle email address (ending with @kindle.com)')
            return EMAIL

    logger.info(f"Processing email from user {user_id}: {text}")


    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        logger.info(f"Creating new user record for user {user_id}")
        user = User(user_id=user_id)
    user.kindle_email = text
    session.add(user)
    session.commit()
    session.close()
    logger.info(f"Email successfully configured for user {user_id}: {text}")

    response = 'Thank you! Now please add to_kindle@gunneone.de to your approved sender list in your Kindle settings.'
    await update.message.reply_text(response)
    logger.info(f"User {user_id} completed email configuration")
    return ConversationHandler.END


async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the Substack link."""
    url = context.args[0] if context.args else update.message.text
    try:
        # send typing chat action
        await context.bot.send_chat_action(update.effective_chat.id, 'typing')
        logger.info(f"Processing URL: {url}")
        content = get_website_content(url)
        logger.info(f"Successfully retrieved content from URL: {url}")

        ebook=convert_to_epub(content)
        logger.info("Successfully converted content to EPUB")

        session = Session()
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        session.close()

        if not user or not user.kindle_email:
            raise Exception("Please configure your Kindle email first using /config")

        send_email(user.kindle_email, ebook)


        username = update.effective_user.username or f"ID:{update.effective_user.id}"
        logger.info(f"Successfully sent EPUB '{content.Title}' to Kindle for user {username}")

# Update last book received date
        session = Session()
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        user.last_book_received_date = datetime.now().isoformat()
        session.commit()
        session.close()

        await update.message.reply_text('Article has been sent to your Kindle!')
    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        # print full stack trace
        logger.exception(e)
        await update.message.reply_text(f'Error: {str(e)}')
    return ConversationHandler.END


def main():
    """Start the bot."""
    # Initialize database
    Base.metadata.create_all(engine)

    application = Application.builder().token(TOKEN).build()

    # In the main function, modify the conversation handler:
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('config', config)
        ],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_email)]
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("config", config),
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_link))

    # Start the bot
    application.run_polling()


if __name__ == '__main__':
    main()