import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from src.email_sender import send_email
from src.web_scraper import get_substack_content
from src.epub_converter import convert_to_epub
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker,declarative_base

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add at the top of the file with other states
EMAIL, WAITING_FOR_LINK = range(2)


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


    """Handle the /send command. If URL is provided with command, process it directly."""
    if context.args and len(context.args) > 0:
        url = context.args[0]
        await process_link(update, context)
        return ConversationHandler.END

    await update.message.reply_text('Please provide the Substack article link:')
    return WAITING_FOR_LINK


async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the Substack link."""
    url = context.args[0] if context.args else update.message.text
    try:
        # send typing chat action
        await context.bot.send_chat_action(update.effective_chat.id, 'typing')
        content = get_substack_content(url)
        logger.info(f"Successfully retrieved content from URL: {url}")

        ebook=convert_to_epub(content)
        logger.info("Successfully converted content to EPUB")

        session = Session()
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()
        session.close()

        if not user or not user.kindle_email:
            raise Exception("Please configure your Kindle email first using /config")

        send_email(user.kindle_email, ebook)
        logger.info("Successfully sent EPUB to Kindle")

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
            CommandHandler('config', config),
            CommandHandler('send', send)
        ],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_email)],
            WAITING_FOR_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_link)]
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("send", send),
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