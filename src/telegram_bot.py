import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from web_scraper import get_substack_content
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
EMAIL = 0

# Database setup
Base = declarative_base()
engine = create_engine('sqlite:///users.db')
Session = sessionmaker(bind=engine)


class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    kindle_email = Column(String)


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
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    message = 'Please enter your Kindle email address:'
    if user and user.kindle_email:
        message = f'Your current Kindle email is: {user.kindle_email}\nEnter a new email to update:'
    session.close()
    await update.message.reply_text(message)
    return EMAIL


async def process_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the received email and provide further instructions."""
    email = update.message.text
    if not email.endswith('@kindle.com'):
        logger.error(f"Invalid email format provided: {email}")
        await update.message.reply_text('Please provide a valid Kindle email address (ending with @kindle.com)')
        return EMAIL
    user_id = update.effective_user.id
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        user = User(user_id=user_id)
    user.kindle_email = email
    session.add(user)
    session.commit()
    session.close()
    logger.info(f"Email successfully configured for user {user_id}: {email}")
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
        logger.info(f"Successfully retrieved content from URL: {url}")
        await update.message.reply_text('Content retrieved successfully!')
    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        await update.message.reply_text(f'Error: {str(e)}')


def main():
    """Start the bot."""
    # Initialize database
    Base.metadata.create_all(engine)

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
