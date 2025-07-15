import click
from dotenv import load_dotenv
import os
import logging
from src.web_scraper import get_website_content
from src.epub_converter import convert_to_epub
from src.email_sender import send_email

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


@click.command()
@click.argument('url')
@click.option('--preserve-image-links', is_flag=True, default=False, help='Preserve links in images')
def main(url, preserve_image_links):
    """Convert Substack article to EPUB and send to Kindle."""
    try:
        logger.info(f"Processing URL: {url}")
        content = get_website_content(url)
        logger.info("Successfully retrieved content from URL")
        ebook = convert_to_epub(content, preserve_image_links)
        logger.info("Successfully converted content to EPUB")
        kindle_email = 'amazon_42RbqL@kindle.com'  # Replace with actual default email
        send_email(kindle_email,ebook)
        logger.info("Successfully sent EPUB to Kindle")
        click.echo('Article has been sent to your Kindle!')
    except Exception as e:
        logger.error(f"Error processing article: {str(e)}")
        click.echo(f'Error: {str(e)}')
        raise e


if __name__ == '__main__':
    main()
