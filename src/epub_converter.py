import os
import requests
import logging
from bs4 import BeautifulSoup
from ebooklib import epub

from src.web_scraper import Article

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def download_image(url: str, images_dir: str, article_title: str, index: int) -> tuple:


    """Download image from URL and save it locally"""
    logger.debug(f"Attempting to download image from: {url}")
    try:
        response = requests.get(url)
        logger.debug(f"HTTP Status Code: {response.status_code}")

        if response.status_code == 200:
            # Generate safe filename from title and index
            safe_title = "".join(x for x in article_title if x.isalnum() or x in (' ', '-', '_')).strip()
            content_type = response.headers.get('content-type', 'image/jpeg')
            ext_map = {
                'image/jpeg': '.jpg',
                'image/png': '.png',
                'image/gif': '.gif',
                'image/webp': '.webp'
            }
            image_ext = ext_map.get(content_type, '.jpg')
            image_name = f"{safe_title}_{index}{image_ext}"
            image_path = os.path.join(images_dir, image_name)
            logger.debug(f"Saving image to: {image_path}")

            with open(image_path, 'wb') as f:
                f.write(response.content)
            logger.debug(f"Successfully saved image: {image_name}")
            return image_name, content_type, response.content
        else:
            logger.error(f"Failed to download image. Status code: {response.status_code}")
            return None, None, None
    except Exception as e:
        logger.error(f"Exception while downloading image: {str(e)}")
        return None, None, None


def process_images(html_content: str, book: epub.EpubBook, images_dir: str, article_title: str) -> str:
    """Process HTML content and download images"""
    logger.debug("Starting image processing")
    logger.debug(f"Images directory: {images_dir}")

    soup = BeautifulSoup(html_content, 'html.parser')
    logger.debug("HTML content parsed successfully")

    os.makedirs(images_dir, exist_ok=True)
    logger.debug("Ensured images directory exists")

    img_count = len(soup.find_all('img'))
    logger.debug(f"Found {img_count} images in HTML content")

    processed_count = 0
    failed_count = 0

    for img in soup.find_all('img'):
        if img.get('src'):
            logger.debug(f"Processing image {processed_count + 1}/{img_count}")
            logger.debug(f"Image source: {img['src']}")

            image_result = download_image(img['src'], images_dir, article_title, processed_count + 1)
            image_name, media_type, image_content = image_result
            if image_name and media_type and image_content:
                try:
                    # Add image to book
                    image_path = os.path.join(images_dir, image_name)
                    logger.debug(f"Processing image: {image_path}")

                    epub_image = epub.EpubImage(
                        uid=image_name,
                        file_name=f'Images/{image_name}',
                        media_type=media_type,
                        content=image_content
                    )
                    book.add_item(epub_image)
                    logger.debug(f"Added image to EPUB book: {image_name}")

                    # Update image source in HTML
                    img['src'] = f'images/{image_name}'
                    logger.debug("Updated image source in HTML")
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Failed to process image {image_name}: {str(e)}")
                    failed_count += 1
            else:
                failed_count += 1

    logger.debug("Image processing complete:")
    logger.debug(f"Successfully processed: {processed_count} images")
    logger.debug(f"Failed to process: {failed_count} images")

    return str(soup)


def convert_to_epub(article: Article) -> str:
    """
    Convert article content to EPUB format and save it.

    Args:
        article (dict): Dictionary containing article title, author and content

    Returns:
        str: Path to the saved EPUB file
    """
    logger.debug("Starting EPUB conversion")

    # Create EPUB book
    book = epub.EpubBook()

    title = article["Title"]
    author = article["Author"]
    html_content = article["Content"]

    logger.debug(f"Article title: {title}")
    logger.debug(f"Article author: {author}")

    # Set metadata
    book.set_title(title)
    book.set_language('en')
    book.add_author(author)

    # Add cover
    cover_path = './Substack Logo.png'
    if os.path.exists(cover_path):
        with open(cover_path, 'rb') as cover_file:
            book.set_cover('cover.png', cover_file.read())
            logger.debug("Added cover image to EPUB")
    else:
        logger.warning(f"Cover image not found at: {cover_path}")

    # Process images and update HTML content
    images_dir = os.path.join('./epubs', 'images')
    processed_content = process_images(html_content, book, images_dir, title)

    # Add content
    content = epub.EpubHtml(title=title, file_name='content.xhtml', content=processed_content)
    book.add_item(content)

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Basic spine with cover
    book.spine = ['cover', content]

    # Create output directory if it doesn't exist
    os.makedirs('./epubs', exist_ok=True)

    # Save EPUB file
    epub_path = os.path.join('./epubs', f"{title}.epub")
    logger.debug(f"Saving EPUB to: {epub_path}")
    epub.write_epub(epub_path, book)
    logger.debug("EPUB file saved successfully")

    # Verify EPUB contents before cleanup
    logger.debug("Verifying EPUB file contents...")
    try:
        import shutil
        test_book = epub.read_epub(epub_path)
        image_items = [item for item in test_book.items if isinstance(item, epub.EpubImage)]
        logger.debug(f"Found {len(image_items)} images in EPUB file")

        if len(image_items) > 0:
            logger.debug("Cleaning up temporary image files")
            # Cleanup images directory
            if os.path.exists(images_dir):
                shutil.rmtree(images_dir)
                logger.debug("Image directory cleaned up")
        else:
            logger.warning("No images found in EPUB file! Keeping image directory for inspection")
    except Exception as e:
        logger.error(f"Failed to verify EPUB contents: {str(e)}")
        logger.warning("Keeping image directory for inspection")

    return epub_path