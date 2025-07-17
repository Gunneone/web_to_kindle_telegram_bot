import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from readability import Document
import os
from urllib.parse import urlparse

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class Article:
    def __init__(self, url, title, author, published_at, content, publication=None):
        self.URL = url
        self.Title = title
        self.Author = author
        self.Published_At = published_at
        self.Content = content
        self.Publication = publication

    def __getitem__(self, key):
        return getattr(self, key)
    def __setitem__(self, key, value):
        return setattr(self, key, value)


def is_substack_site(url: str) -> bool:
    """
    Determines if a URL is a Substack site by checking URL patterns and HTML content.
    
    Args:
        url (str): The URL to check
        
    Returns:
        bool: True if the site is detected as Substack, False otherwise
    """
    # First check the URL pattern - if it contains substack.com, it's definitely Substack
    if 'substack.com' in url.lower():
        return True
    
    # Check for common Substack URL patterns (like /p/ for posts)
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    if '/p/' in path:
        # This could be Substack, let's verify by checking the HTML
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                html_content = response.text.lower()
                
                # Check for various Substack indicators in the HTML
                substack_indicators = [
                    'substack',  # General Substack references
                    'generator" content="substack',  # Meta generator tag
                    'substack-app',  # Common Substack div ID
                    'substackcdn.com',  # Substack CDN references
                ]
                
                # If any indicator is found, it's likely a Substack site
                for indicator in substack_indicators:
                    if indicator in html_content:
                        logger.info(f"Detected Substack site based on HTML indicator: {indicator}")
                        return True
                        
        except Exception as e:
            logger.warning(f"Could not verify Substack status for {url}: {str(e)}")
            # Only assume it's Substack based on URL pattern if we can't check the HTML
            # and the domain looks like it could reasonably be a Substack custom domain
            hostname = parsed_url.hostname
            if hostname and not hostname.endswith(('.gov', '.edu')) and '/p/' in path:
                logger.info(f"Assuming Substack based on URL pattern /p/ for: {url}")
                return True
    
    return False


def get_website_content(url: str) -> Article:
    """
    Determines if URL is a Substack page and extracts content accordingly.

    Args:
        url (str): The URL to process

    Returns:
        Article: Article object containing extracted content
    """
    if is_substack_site(url):
        return get_substack_content(url)
    else:
        return get_generic_content(url)


def get_generic_content(url: str) -> Article | None:
    """
    Extracts content from a generic webpage using readability-lxml.

    Args:
        url (str): The URL to process

    Returns:
        Article: Article object containing extracted content
    """
    logger.info(f"Processing URL using readability-lxml: {url}... ")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            doc = Document(response.text)
            content = doc.summary()
            title = doc.title()

            if content:
                logger.info("Content extracted using readability")

                # Create safe filename by removing special characters
                safe_title = ''.join(c for c in title.lower() if c.isalnum() or c in ' -_')
                safe_title = safe_title.replace(' ', '-')[:70]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                # Ensure html directory exists
                os.makedirs('./html', exist_ok=True)
                
                # Use os.path.join for proper path handling
                file_path = os.path.join('./html', f"{safe_title}-{timestamp}.html")
                
                with open(file_path, "w", encoding='utf-8') as f:
                    f.write(content)

                # Parse metadata from HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                author = soup.find('meta', {'name': 'author'})
                author = author['content'] if author else "Unknown Author"

                published = soup.find('meta', {'property': 'article:published_time'})
                published = published['content'] if published else datetime.now().isoformat()

                return Article(
                    url=url,
                    title=title,
                    author=author,
                    published_at=published,
                    content=content,
                    publication=None  # Generic content doesn't have publication info
                )
            else:
                logger.error("Readability failed to extract content")
                raise Exception("Sorry, content extraction failed for this URL")
        else:
            logger.error(f"HTTP Status Code: {response.status_code}")
            raise Exception(f"HTTP Status Code: {response.status_code}")

    except Exception as e:
        logger.error(f"Error extracting content: {str(e)}")
        raise Exception(f"Error extracting content: {str(e)}")

def get_substack_content(url: str) -> Article:
    """
    Extracts the main article content from a Substack blog post URL.

    Args:
        url (str): The URL of the Substack blog post

    Returns:
        str: HTML content of the main article

    Raises:
        Exception: If the URL is invalid or content cannot be retrieved
    """
    logger.info(f"Processing URL using Substack Extractor: {url}... ")
    try:
        # Send HTTP GET request
        response = requests.get(url)
        response.raise_for_status()

        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the main article content by looking for the article class
        article_content = soup.find('article')

        if article_content:

            # extract author
            author_element = soup.find('div', class_='profile-hover-card-target')
            author = author_element.find('a').text.strip() if author_element else "Unknown Author"

            # Extract publication name from multiple potential sources
            publication = None
            
            # Method 1: Check og:site_name meta tag
            og_site_name = soup.find('meta', property='og:site_name')
            if og_site_name and og_site_name.get('content'):
                publication = og_site_name['content'].strip()
                logger.info(f"Found publication name from og:site_name: {publication}")
            
            # Method 2: If no og:site_name, try to extract from URL subdomain
            if not publication:
                parsed_url = urlparse(url)
                hostname = parsed_url.hostname
                if hostname and hostname.endswith('.substack.com') and hostname != 'substack.com':
                    subdomain = hostname.replace('.substack.com', '')
                    # Convert subdomain to title case and replace hyphens
                    publication = subdomain.replace('-', ' ').title()
                    logger.info(f"Extracted publication name from subdomain: {publication}")
            
            # Method 3: Look for publication name in the page header/branding area
            if not publication:
                # Check for publication name in header elements
                header_elements = soup.find_all(['h1', 'h2', 'h3'], class_=lambda x: x and any(
                    keyword in x.lower() for keyword in ['publication', 'header', 'title', 'name', 'brand']
                ))
                for header in header_elements:
                    text = header.get_text().strip()
                    # Skip if it looks like an article title (too long or contains common article words)
                    if len(text) < 50 and not any(word in text.lower() for word in ['how', 'why', 'what', 'the art', 'a guide']):
                        publication = text
                        logger.info(f"Found publication name from header: {publication}")
                        break
            
            # Method 4: Check title tag for publication name pattern
            if not publication:
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text()
                    # Many Substack pages have titles like "Article Title | Publication Name"
                    if ' | ' in title_text:
                        parts = title_text.split(' | ')
                        if len(parts) >= 2:
                            potential_pub = parts[-1].strip()
                            # Avoid generic terms
                            if potential_pub.lower() not in ['substack', 'blog', 'newsletter']:
                                publication = potential_pub
                                logger.info(f"Found publication name from title: {publication}")

            # extract title which is the first h1, that is not in a .pc-display-flex element
            h1_elements = soup.find_all('h1')
            title = None
            for h1 in h1_elements:
                if not h1.find_parent(class_='pc-display-flex'):
                    title = h1.text.strip()

                    # Create and insert author heading and horizontal line after title
                    author_heading = soup.new_tag('h4')
                    author_heading.string = f"By {author}"
                    horizontal_line = soup.new_tag('hr')
                    horizontal_line['style'] = 'border-top: 1px solid #ccc; margin: 20px 0;'
                    
                    # Add publication info if available
                    if publication:
                        publication_heading = soup.new_tag('h5')
                        publication_heading.string = f"From: {publication}"
                        publication_heading['style'] = 'color: #666; font-style: italic; margin: 10px 0;'
                        h1.insert_after(horizontal_line)
                        h1.insert_after(publication_heading)
                        h1.insert_after(author_heading)
                    else:
                        h1.insert_after(horizontal_line)
                        h1.insert_after(author_heading)
                    break
            if not title:
                title = "Unknown Title"

            # Remove share buttons, like buttons etc
            for element in article_content.select(
                    '.pc-display-flex, .button-wrapper, .modal, .popup'):
                element.decompose()

            # Create safe filename
            safe_title = ''.join(c for c in title.lower() if c.isalnum() or c in ' -_')
            safe_title = safe_title.replace(' ', '-')[:70]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Ensure html directory exists
            os.makedirs('./html', exist_ok=True)
            
            # Use os.path.join for proper path handling
            file_path = os.path.join('./html', f"{safe_title}-{timestamp}.html")
            
            with open(file_path, "w", encoding='utf-8') as f:
                f.write(str(article_content))

            # create Article object with article_content, title and author
            logger.info("Content extracted using Substack Extractor")
            article = Article(
                url=url,
                title=title,
                author=author,
                published_at=datetime.now().isoformat(),
                content=str(article_content),
                publication=publication
            )

            return article
        else:
            raise Exception("Could not find article content")

    except requests.RequestException as e:
        raise Exception(f"Error fetching content: {str(e)}")
    except Exception as e:
        # print whole stack trace
        print(e)
        raise Exception(f"Error processing content: {str(e)}")