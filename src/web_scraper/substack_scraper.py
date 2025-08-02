"""
Substack-specific content scraper.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from urllib.parse import urlparse
import os
from .article import Article

logger = logging.getLogger(__name__)


class SubstackScraper:
    """Handles content extraction from Substack websites."""

    @staticmethod
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
                    # Be more conservative about well-known non-Substack platforms
                    known_non_substack = ['medium.com', 'wordpress.com', 'blogspot.com', 'tumblr.com']
                    if not any(platform in hostname.lower() for platform in known_non_substack):
                        logger.info(f"Assuming Substack based on URL pattern /p/ for: {url}")
                        return True

        return False

    def extract_content(self, url: str) -> Article:
        """
        Extracts the main article content from a Substack blog post URL.

        Args:
            url (str): The URL of the Substack blog post

        Returns:
            Article: Article object containing extracted content

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
                publication = self._extract_publication_name(soup, url)

                # extract title which is the first h1, that is not in a .pc-display-flex element
                title = self._extract_title_and_add_metadata(soup, author, publication)

                # Remove share buttons, like buttons etc
                self._clean_article_content(article_content)

                # Save content to file
                self._save_content_to_file(article_content, title)

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
            logger.error(f"Error processing Substack content: {str(e)}")
            raise Exception(f"Error processing content: {str(e)}")

    def _extract_publication_name(self, soup: BeautifulSoup, url: str) -> str:
        """Extract publication name from meta tags or URL."""
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

        return publication

    def _extract_title_and_add_metadata(self, soup: BeautifulSoup, author: str, publication: str) -> str:
        """Extract title and add author/publication metadata."""
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

        return title if title else "Unknown Title"

    def _clean_article_content(self, article_content: BeautifulSoup) -> None:
        """Remove unwanted elements from article content."""
        for element in article_content.select('.pc-display-flex, .button-wrapper, .modal, .popup'):
            element.decompose()

    def _save_content_to_file(self, article_content: BeautifulSoup, title: str) -> None:
        """Save content to HTML file with safe filename."""
        safe_title = ''.join(c for c in title.lower() if c.isalnum() or c in ' -_')
        safe_title = safe_title.replace(' ', '-')[:70]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Ensure html directory exists
        os.makedirs('./output/html', exist_ok=True)

        # Use os.path.join for proper path handling
        file_path = os.path.join('./output/html', f"{safe_title}-{timestamp}.html")

        with open(file_path, "w", encoding='utf-8') as f:
            f.write(str(article_content))
