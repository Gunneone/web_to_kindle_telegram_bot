"""
Generic content scraper for non-Substack websites.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from readability import Document
import os
from urllib.parse import urljoin
from .article import Article

logger = logging.getLogger(__name__)


class GenericScraper:
    """Handles content extraction from generic websites using readability."""

    def extract_content(self, url: str) -> Article:
        """
        Extracts content from a generic webpage using readability-lxml.

        Args:
            url (str): The URL to process

        Returns:
            Article: Article object containing extracted content
        """
        logger.info(f"Processing URL using readability-lxml: {url}... ")
        try:
            headers = {
                'User-Agent': 'Chrome/58.0.3029.110 Safari/537.3',
                'Accept': 'text/html'
            }
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                doc = Document(response.text)
                content = doc.summary()
                title = doc.title()

                if content:
                    logger.info("Content extracted using readability")

                    # Extract h1 title if missing
                    content, h1_title = self._extract_h1_from_response(content, response.text)
                    if h1_title:
                        title = h1_title

                    # Extract metadata (author and publication date)
                    author, published_date = self._extract_metadata(response.text)

                    # Add missing metadata to content
                    content = self._add_missing_metadata(content, author, published_date)

                    # Fix relative image URLs
                    content = self._fix_image_urls(content, url)

                    # Save content to file
                    self._save_content_to_file(content, title)

                    return Article(
                        url=url,
                        title=title,
                        author=author,
                        published_at=published_date or datetime.now().isoformat(),
                        content=content,
                        publication=None
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

    def _extract_h1_from_response(self, content: str, response_text: str) -> tuple[str, str]:
        """Extract h1 title from content or response if missing."""
        soup = BeautifulSoup(content, 'html.parser')
        if not soup.find('h1'):
            # Find the first h1 with actual text content from the full response
            full_soup = BeautifulSoup(response_text, 'html.parser')
            h1_elements = full_soup.find_all('h1')
            for h1 in h1_elements:
                text = h1.get_text().strip()
                if text:  # Only use h1 if it has actual content
                    logger.info(f"Found h1 with content: {text}")
                    return f"<h1>{text}</h1>\n{content}", text
        return content, None

    def _extract_metadata(self, response_text: str) -> tuple[str, str]:
        """Extract author and publication date from HTML metadata."""
        full_soup = BeautifulSoup(response_text, 'html.parser')

        # Extract author
        author_meta = full_soup.find('meta', {'name': 'author'})
        author = author_meta['content'] if author_meta else "Unknown Author"

        # Extract publication date
        published_date = None
        raw_date = None

        # First try meta tags
        published_meta = full_soup.find('meta', {'property': 'article:published_time'})
        if not published_meta:
            published_meta = full_soup.find('meta', {'name': 'publication_date'})
        if not published_meta:
            published_meta = full_soup.find('meta', {'property': 'article:published'})

        if published_meta and published_meta.get('content'):
            raw_date = published_meta['content']
            logger.info(f"Found date in meta tag: {raw_date}")

        # If no meta date found, look for <time> elements with datetime attribute
        if not raw_date:
            time_elements = full_soup.find_all('time')
            for time_elem in time_elements:
                if time_elem.get('datetime'):
                    raw_date = time_elem['datetime']
                    logger.info(f"Found date in <time> element: {raw_date}")
                    break

        # Parse and format the date if found
        if raw_date:
            published_date = self._parse_and_format_date(raw_date)

        return author, published_date

    def _parse_and_format_date(self, raw_date: str) -> str:
        """Parse various date formats and return formatted date string."""
        try:
            # Handle various datetime formats
            if 'T' in raw_date or '+' in raw_date or raw_date.endswith('Z'):
                # ISO format with timezone info
                parsed_date = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            else:
                # Try parsing as ISO format without timezone
                try:
                    parsed_date = datetime.fromisoformat(raw_date)
                except ValueError:
                    # Try parsing with space separator (like "2025-07-29 00:00:00+00:00")
                    parsed_date = datetime.fromisoformat(raw_date.replace(' ', 'T'))

            formatted_date = parsed_date.strftime("%B %d, %Y")
            logger.info(f"Successfully formatted published date: {formatted_date}")
            return formatted_date
        except Exception as e:
            logger.warning(f"Could not parse date '{raw_date}': {e}")
            # If parsing fails, try to extract at least the year for basic info
            if raw_date and len(raw_date) >= 4:
                try:
                    year_match = raw_date[:4]
                    if year_match.isdigit():
                        fallback_date = f"Published in {year_match}"
                        logger.info(f"Extracted year from unparseable date: {fallback_date}")
                        return fallback_date
                except:
                    pass
        return None

    def _add_missing_metadata(self, content: str, author: str, published_date: str) -> str:
        """Add author and/or publication date to content if missing."""
        soup = BeautifulSoup(content, 'html.parser')
        content_text = soup.get_text().lower()
        author_name_parts = author.lower().split()

        # Check if author appears meaningfully in the first 1000 characters
        first_portion = content_text[:1000]
        author_in_beginning = any(part in first_portion for part in author_name_parts if len(part) > 2)

        # Check if published date appears in the first 1000 characters
        date_in_beginning = False
        if published_date:
            date_patterns = [
                published_date.lower(),
                str(datetime.now().year) if published_date else None,
                published_date.split()[0].lower() if published_date and len(published_date.split()) > 0 else None
            ]
            date_in_beginning = any(pattern and pattern in first_portion for pattern in date_patterns if pattern)

        # Add missing metadata if needed
        if (not author_in_beginning and author != "Unknown Author") or (published_date and not date_in_beginning):
            h1_element = soup.find('h1')
            if h1_element:
                elements_to_add = []

                # Create author heading if needed
                if not author_in_beginning and author != "Unknown Author":
                    author_heading = soup.new_tag('h4')
                    author_heading.string = f"By {author}"
                    author_heading['style'] = 'color: #666; font-style: italic; margin: 10px 0;'
                    elements_to_add.append(author_heading)
                    logger.info(f"Added author info to content: {author}")

                # Create date heading if needed
                if published_date and not date_in_beginning:
                    date_heading = soup.new_tag('h5')
                    date_heading.string = f"Published: {published_date}"
                    date_heading['style'] = 'color: #888; font-style: italic; margin: 5px 0;'
                    elements_to_add.append(date_heading)
                    logger.info(f"Added publication date to content: {published_date}")

                # Create horizontal line
                if elements_to_add:
                    horizontal_line = soup.new_tag('hr')
                    horizontal_line['style'] = 'border-top: 1px solid #ccc; margin: 20px 0;'
                    elements_to_add.append(horizontal_line)

                # Insert all elements after h1 (in reverse order)
                for element in reversed(elements_to_add):
                    h1_element.insert_after(element)

                return str(soup)

        return content

    def _fix_image_urls(self, content: str, base_url: str) -> str:
        """Convert relative image URLs to absolute URLs."""
        soup = BeautifulSoup(content, 'html.parser')
        for img in soup.find_all('img', src=True):
            src = img['src']
            absolute_src = urljoin(base_url, src)
            img['src'] = absolute_src
        return str(soup)

    def _save_content_to_file(self, content: str, title: str) -> None:
        """Save content to HTML file with safe filename."""
        safe_title = ''.join(c for c in title.lower() if c.isalnum() or c in ' -_')
        safe_title = safe_title.replace(' ', '-')[:70]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        os.makedirs('./output/html', exist_ok=True)
        file_path = os.path.join('./output/html', f"{safe_title}-{timestamp}.html")

        with open(file_path, "w", encoding='utf-8') as f:
            f.write(content)
