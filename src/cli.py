import click
from dotenv import load_dotenv
import os
import logging
from web_scraper import get_website_content
from epub_converter import convert_to_epub
from email_sender import send_email

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


@click.command()
@click.argument('url', required=False)
@click.option('--file', '-f', type=click.Path(exists=True), help='File containing one URL per line')
@click.option('--preserve-image-links', is_flag=True, default=False, help='Preserve links in images')
@click.option('--send-mail', is_flag=True, default=False, help='Send the EPUB file via email (default: False)')
def main(url, file, preserve_image_links, send_mail):
    """Convert web article(s) to EPUB and send to Kindle.

    Either provide a single URL as argument or use --file to process multiple URLs.
    """
    # Validate that either URL or file is provided, but not both
    if not url and not file:
        click.echo("Error: Must provide either a URL argument or --file option")
        return

    if url and file:
        click.echo("Error: Cannot provide both URL argument and --file option")
        return

    # Determine URLs to process
    urls_to_process = []
    if url:
        urls_to_process = [url]
    else:
        # Read URLs from file
        try:
            with open(file, 'r', encoding='utf-8') as f:
                urls_to_process = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            logger.info(f"Loaded {len(urls_to_process)} URLs from file: {file}")
        except Exception as e:
            click.echo(f"Error reading file {file}: {str(e)}")
            return

    if not urls_to_process:
        click.echo("No valid URLs found to process")
        return

    # Process each URL
    successful_count = 0
    failed_count = 0

    for i, current_url in enumerate(urls_to_process, 1):
        try:
            logger.info(f"Processing URL {i}/{len(urls_to_process)}: {current_url}")
            click.echo(f"Processing {i}/{len(urls_to_process)}: {current_url}")

            content = get_website_content(current_url)
            logger.info("Successfully retrieved content from URL")

            ebook = convert_to_epub(content, preserve_image_links)
            logger.info("Successfully converted content to EPUB")

            if send_mail:
                kindle_email = 'amazon12345@kindle.com'  # Replace with actual default email
                send_email(kindle_email, ebook)
                logger.info("Successfully sent EPUB to Kindle")
                click.echo(f'✓ Article "{content.Title}" sent to Kindle')
            else:
                logger.info("Email sending skipped as requested")
                click.echo(f'✓ Article "{content.Title}" converted to EPUB')

            successful_count += 1

        except Exception as e:
            logger.error(f"Error processing URL {current_url}: {str(e)}")
            click.echo(f'✗ Error processing {current_url}: {str(e)}')
            failed_count += 1
            # Continue processing other URLs instead of stopping

    # Summary
    click.echo(f"\nProcessing complete: {successful_count} successful, {failed_count} failed")


if __name__ == '__main__':
    main()