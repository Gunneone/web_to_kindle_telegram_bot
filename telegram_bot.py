import os
import os.path
import logging
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy.sql.expression import update
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
import validators

from src.email_sender import send_email
from src.web_scraper import get_website_content
from src.epub_converter import convert_to_epub
from sqlalchemy import create_engine, Column, Integer, String, DateTime, inspect, text
from sqlalchemy.orm import sessionmaker,declarative_base

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add at the top of the file with other states
EMAIL = 0
IMAGE_LINKS = 1

# Database setup
Base = declarative_base()
engine = create_engine('sqlite:///users.db')
Session = sessionmaker(bind=engine)


class Article(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    article_url = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    epub_path = Column(String)
    
    
class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    kindle_email = Column(String)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    last_book_received_date = Column(String)
    preserve_image_links = Column(Integer, default=0)  # SQLite uses INTEGER for boolean


# Load environment variables
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')



async def update_user(user_data, email=None):
    """Helper function to update or insert user data."""
    session = Session()
    user = session.query(User).filter_by(user_id=user_data.id).first()
    if not user:
        user = User(
            user_id=user_data.id,
            username=user_data.username,
            first_name=user_data.first_name,
            last_name=user_data.last_name
        )
    else:
        user.username = user_data.username
        user.first_name = user_data.first_name
        user.last_name = user_data.last_name
    if email:
        user.kindle_email = email
    session.add(user)
    session.commit()
    session.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    logger.info(f"User {update.effective_user.id} started the bot")
    await update_user(update.effective_user)
    await update.message.reply_text(
        'Hi! Use /config to set up your Kindle email. Afterwards just send me any article link to process.')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation."""
    logger.info(f"User {update.effective_user.id} canceled the operation")
    await update.message.reply_text('Operation canceled.')
    return ConversationHandler.END


async def config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the email collection process."""
    user_id = update.effective_user.id
    logger.debug(f"User {user_id} started email configuration")
    await update_user(update.effective_user)
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    message = 'Please enter your Kindle email address.'
    if user and user.kindle_email:
        message = f'Your current Kindle email is: {user.kindle_email}\n\nEnter a new email to update.\nOr /cancel.'

        logger.debug(f"User {user_id} has existing email: {user.kindle_email}")
    session.close()
    await update.message.reply_text(message)
    logger.debug(f"User {user_id} entering EMAIL state")
    return EMAIL


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current settings and allow modification."""
    user_id = update.effective_user.id
    logger.debug(f"User {user_id} requested settings")
    await update_user(update.effective_user)
    
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    
    if not user:
        await update.message.reply_text('Please configure your settings first with /config')
        session.close()
        return ConversationHandler.END
    
    preserve_links = bool(user.preserve_image_links) if user.preserve_image_links is not None else False
    kindle_email = user.kindle_email or "Not configured"
    
    message = f"""Current Settings:
📧 Kindle Email: {kindle_email}
🖼️ Preserve Image Links: {'Yes' if preserve_links else 'No'}

Commands:
/config - Change Kindle email
/imagelinks - Toggle preserve image links setting
/cancel - Cancel operation"""
    
    session.close()
    await update.message.reply_text(message)
    return ConversationHandler.END


async def toggle_image_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle the preserve image links setting."""
    user_id = update.effective_user.id
    logger.debug(f"User {user_id} toggling image links setting")
    await update_user(update.effective_user)
    
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    
    if not user:
        await update.message.reply_text('Please configure your settings first with /config')
        session.close()
        return ConversationHandler.END
    
    # Toggle the setting
    current_setting = bool(user.preserve_image_links) if user.preserve_image_links is not None else False
    new_setting = not current_setting
    user.preserve_image_links = 1 if new_setting else 0
    
    session.commit()
    session.close()
    
    status = "enabled" if new_setting else "disabled"
    await update.message.reply_text(f'Image link preservation has been {status}.')
    logger.info(f"User {user_id} set preserve_image_links to {new_setting}")
    
    return ConversationHandler.END

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

    await update_user(update.effective_user, text)
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
        if not content:
            raise Exception("Failed to retrieve content from URL")
        logger.info(f"Successfully retrieved content from URL: {url}")

        session = Session()
        user = session.query(User).filter_by(user_id=update.effective_user.id).first()

        if not user or not user.kindle_email:
            session.close()
            raise Exception("Please configure your Kindle email first using /config")

        # Get user's preserve image links preference
        preserve_image_links = bool(user.preserve_image_links) if user.preserve_image_links is not None else False
        session.close()

        ebook = convert_to_epub(content, preserve_image_links=preserve_image_links)
        logger.info("Successfully converted content to EPUB")

        send_email(user.kindle_email, ebook)

        # Save article record
        article = Article(
            user_id=update.effective_user.id,
            article_url=url,
            epub_path=ebook
        )
        session = Session()
        session.add(article)
        session.commit()
        session.close()

        username = update.effective_user.username or f"ID:{update.effective_user.id}"
        logger.info(f"Successfully sent EPUB '{content.Title}' to Kindle for user {username}")

        await update.message.reply_text('Article has been sent to your Kindle!')

        # Notify admin
        if ADMIN_ID:
            admin_message = f"Ebook '{content.Title}' sent to {username}."
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
            if os.path.exists(ebook):
                await context.bot.send_document(chat_id=ADMIN_ID, document=open(ebook, 'rb'))
    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        # print full stack trace
        logger.exception(e)
        await update.message.reply_text(f'Sorry, I couldn\'t retrieve your article for some reason. Maybe write the dev to investigate.')
    return ConversationHandler.END

def check_and_create_columns():
    """Check if all columns exist and create missing ones."""
    inspector = inspect(engine)
    for table in Base.metadata.tables.values():
        existing_columns = {col['name'] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing_columns:
                with engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type}'))

def main():
    """Start the bot."""
    # Initialize database
    Base.metadata.create_all(engine)
    check_and_create_columns()

    application = Application.builder().token(TOKEN).build()

    # In the main function, modify the conversation handler:
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('config', config),
            CommandHandler('settings', settings),
            CommandHandler('imagelinks', toggle_image_links)
        ],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_email)]
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("config", config),
            CommandHandler("settings", settings),
            CommandHandler("imagelinks", toggle_image_links),
            CommandHandler("cancel", cancel),
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("imagelinks", toggle_image_links))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_link))

    # Start the bot
    application.run_polling()


if __name__ == '__main__':
    main()