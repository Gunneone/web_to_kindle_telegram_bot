#!/usr/bin/env python3
"""
Comprehensive tests for Substack metadata extraction functionality.

This test suite validates the Substack content extraction for specific URLs
as requested in issue #25, using mock HTTP responses to avoid network dependencies.
"""

import unittest
from unittest.mock import patch, Mock, mock_open
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from web_scraper import get_substack_content, Article


class TestSubstackMetadataExtraction(unittest.TestCase):
    """Test class for Substack metadata extraction functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.maxDiff = None

    def create_mock_html(self, title, author, publication, og_site_name=True):
        """
        Create mock HTML content for testing.
        
        Args:
            title (str): Article title
            author (str): Author name
            publication (str): Publication name
            og_site_name (bool): Whether to include og:site_name meta tag
        
        Returns:
            str: Mock HTML content
        """
        og_meta = f'<meta property="og:site_name" content="{publication}">' if og_site_name else ''
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title} | {publication}</title>
            {og_meta}
            <meta name="author" content="{author}">
        </head>
        <body>
            <article>
                <h1>{title}</h1>
                <div class="profile-hover-card-target">
                    <a>{author}</a>
                </div>
                <div class="article-content">
                    <p>This is the main article content.</p>
                    <p>More content here with various paragraphs.</p>
                </div>
                <div class="pc-display-flex">Should be removed</div>
                <div class="button-wrapper">Share button</div>
            </article>
        </body>
        </html>
        """

    @patch('src.web_scraper.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.web_scraper.requests.get')
    def test_win_win_metadata_extraction(self, mock_get, mock_file, mock_makedirs):
        """Test metadata extraction for Win-Win publication."""
        url = "https://substack.com/inbox/post/166333070"
        title = "Can We Save Our Internet From The Bots, AND Preserve Anonymity?"
        author = "Liv Boeree"
        publication = "Win-Win"
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.create_mock_html(title, author, publication)
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test the extraction
        article = get_substack_content(url)
        
        # Assertions
        self.assertIsInstance(article, Article)
        self.assertEqual(article.URL, url)
        self.assertEqual(article.Title, title)
        self.assertEqual(article.Author, author)
        self.assertEqual(article.Publication, publication)
        self.assertIn(title, article.Content)
        self.assertIn(f"By {author}", article.Content)
        self.assertIn(f"From: {publication}", article.Content)

    @patch('src.web_scraper.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.web_scraper.requests.get')
    def test_knowingless_metadata_extraction(self, mock_get, mock_file, mock_makedirs):
        """Test metadata extraction for Knowingless publication."""
        url = "https://aella.substack.com/p/pt3-the-status-wars-of-apes"
        title = "Pt3: The Status Wars of Apes"
        author = "Aella"
        publication = "Knowingless"
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.create_mock_html(title, author, publication)
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test the extraction
        article = get_substack_content(url)
        
        # Assertions
        self.assertIsInstance(article, Article)
        self.assertEqual(article.URL, url)
        self.assertEqual(article.Title, title)
        self.assertEqual(article.Author, author)
        self.assertEqual(article.Publication, publication)
        self.assertIn(title, article.Content)
        self.assertIn(f"By {author}", article.Content)
        self.assertIn(f"From: {publication}", article.Content)

    @patch('src.web_scraper.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.web_scraper.requests.get')
    def test_sustainability_by_numbers_metadata_extraction(self, mock_get, mock_file, mock_makedirs):
        """Test metadata extraction for Sustainability by Numbers publication."""
        url = "https://www.sustainabilitybynumbers.com/p/population-growth-decline-climate"
        title = "Population growth or decline will have little impact on climate change"
        author = "Hannah Ritchie"
        publication = "Sustainability by Numbers"
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.create_mock_html(title, author, publication)
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test the extraction
        article = get_substack_content(url)
        
        # Assertions
        self.assertIsInstance(article, Article)
        self.assertEqual(article.URL, url)
        self.assertEqual(article.Title, title)
        self.assertEqual(article.Author, author)
        self.assertEqual(article.Publication, publication)
        self.assertIn(title, article.Content)
        self.assertIn(f"By {author}", article.Content)
        self.assertIn(f"From: {publication}", article.Content)

    @patch('src.web_scraper.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.web_scraper.requests.get')
    def test_missing_og_site_name_subdomain_fallback(self, mock_get, mock_file, mock_makedirs):
        """Test extraction when og:site_name is missing, falling back to subdomain extraction."""
        url = "https://testpub.substack.com/p/test-article"
        title = "Test Article"
        author = "Test Author"
        publication = "Testpub"  # Should be extracted from subdomain
        
        # Mock HTTP response without og:site_name
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.create_mock_html(title, author, publication, og_site_name=False)
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test the extraction
        article = get_substack_content(url)
        
        # Assertions
        self.assertIsInstance(article, Article)
        self.assertEqual(article.Publication, publication)
        self.assertIn(f"From: {publication}", article.Content)

    @patch('src.web_scraper.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.web_scraper.requests.get')
    def test_content_cleanup(self, mock_get, mock_file, mock_makedirs):
        """Test that unwanted elements are removed from content."""
        url = "https://test.substack.com/p/test"
        title = "Test Article"
        author = "Test Author"
        publication = "Test Publication"
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.create_mock_html(title, author, publication)
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test the extraction
        article = get_substack_content(url)
        
        # Assertions - unwanted elements should be removed
        self.assertNotIn("pc-display-flex", article.Content)
        self.assertNotIn("button-wrapper", article.Content)
        self.assertNotIn("Should be removed", article.Content)
        self.assertNotIn("Share button", article.Content)

    @patch('src.web_scraper.requests.get')
    def test_http_error_handling(self, mock_get):
        """Test handling of HTTP errors."""
        url = "https://nonexistent.substack.com/p/test"
        
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 404 Not Found")
        mock_get.return_value = mock_response
        
        # Test that exception is raised
        with self.assertRaises(Exception) as context:
            get_substack_content(url)
        
        self.assertIn("Error processing content", str(context.exception))

    @patch('src.web_scraper.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.web_scraper.requests.get')
    def test_missing_article_content(self, mock_get, mock_file, mock_makedirs):
        """Test handling when article content is not found."""
        url = "https://test.substack.com/p/test"
        
        # Mock HTTP response without article tag
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><div>No article here</div></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test that exception is raised
        with self.assertRaises(Exception) as context:
            get_substack_content(url)
        
        self.assertIn("Could not find article content", str(context.exception))

    @patch('src.web_scraper.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.web_scraper.requests.get')
    def test_title_extraction_fallback(self, mock_get, mock_file, mock_makedirs):
        """Test title extraction when no valid h1 is found."""
        url = "https://test.substack.com/p/test"
        
        # Create HTML without proper h1 or with h1 in pc-display-flex
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Title | Test Publication</title>
            <meta property="og:site_name" content="Test Publication">
        </head>
        <body>
            <article>
                <div class="pc-display-flex">
                    <h1>Should be ignored</h1>
                </div>
                <div class="profile-hover-card-target">
                    <a>Test Author</a>
                </div>
                <div class="article-content">
                    <p>Article content here.</p>
                </div>
            </article>
        </body>
        </html>
        """
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test the extraction
        article = get_substack_content(url)
        
        # Should fall back to "Unknown Title"
        self.assertEqual(article.Title, "Unknown Title")


if __name__ == '__main__':
    unittest.main(verbosity=2)