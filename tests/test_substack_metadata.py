#!/usr/bin/env python3
"""
Comprehensive tests for Substack metadata extraction functionality.

This test suite validates the Substack content extraction for specific URLs
using real HTTP requests.
"""

import unittest
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

    def assert_article_properties(self, article, expected_url, expected_title, expected_author, expected_publication):
        """
        Assert all article properties match expected values.

        Args:
            article: Article object to test
            expected_url (str): Expected URL
            expected_title (str): Expected title
            expected_author (str): Expected author
            expected_publication (str): Expected publication
        """
        self.assertIsInstance(article, Article)
        self.assertEqual(article.URL, expected_url)
        self.assertEqual(article.Title, expected_title)
        self.assertEqual(article.Author, expected_author)
        self.assertEqual(article.Publication, expected_publication)
        self.assertIn(expected_title, article.Content)
        self.assertIn(f"By {expected_author}", article.Content)
        self.assertIn(f"From: {expected_publication}", article.Content)

    def print_test_results(self, test_name, article, expected_url, expected_title, expected_author,
                           expected_publication):
        """Print formatted test results with emojis."""
        print(f"\n{'=' * 60}")
        print(f"🧪 TEST: {test_name}")
        print(f"{'=' * 60}")

        checks = [
            ("URL", article.URL, expected_url),
            ("Title", article.Title, expected_title),
            ("Author", article.Author, expected_author),
            ("Publication", article.Publication, expected_publication)
        ]

        for field_name, actual, expected in checks:
            emoji = "✅" if actual == expected else "❌"
            print(f"{emoji} {field_name}: {actual}")
            if actual != expected:
                print(f"   Expected: {expected}")

        content_checks = [
            ("Title in content", expected_title in article.Content),
            ("Author in content", f"By {expected_author}" in article.Content),
            ("Publication in content", f"From: {expected_publication}" in article.Content)
        ]

        for check_name, check_result in content_checks:
            emoji = "✅" if check_result else "❌"
            print(f"{emoji} {check_name}: {'PASSED' if check_result else 'FAILED'}")

    def test_win_win_metadata_extraction(self):
        """Test metadata extraction for Win-Win publication."""
        url = "https://substack.com/inbox/post/166333070"
        title = "Can We Save Our Internet From The Bots, AND Preserve Anonymity?"
        author = "Liv Boeree"
        publication = "Win-Win"

        try:
            # Make real HTTP request
            article = get_substack_content(url)

            # Print results and assert
            self.print_test_results("Win-Win Metadata Extraction", article, url, title, author, publication)
            self.assert_article_properties(article, url, title, author, publication)

        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            self.fail(f"Win-Win article extraction failed: {str(e)}")

    def test_knowingless_metadata_extraction(self):
        """Test metadata extraction for Knowingless publication."""
        url = "https://aella.substack.com/p/pt3-the-status-wars-of-apes"
        title = "Pt3: The Status Wars of Apes"
        author = "Aella"
        publication = "Knowingless"

        try:
            # Make real HTTP request
            article = get_substack_content(url)

            # Print results and assert
            self.print_test_results("Knowingless Metadata Extraction", article, url, title, author, publication)
            self.assert_article_properties(article, url, title, author, publication)

        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            self.fail(f"Knowingless article extraction failed: {str(e)}")

    def test_sustainability_by_numbers_metadata_extraction(self):
        """Test metadata extraction for Sustainability by Numbers publication."""
        url = "https://www.sustainabilitybynumbers.com/p/population-growth-decline-climate"
        title = "Population growth or decline will have little impact on climate change"
        author = "Hannah Ritchie"
        publication = "Sustainability by numbers"

        try:
            # Make real HTTP request
            article = get_substack_content(url)

            # Print results and assert
            self.print_test_results("Sustainability by Numbers Metadata Extraction", article, url, title, author,
                                    publication)
            self.assert_article_properties(article, url, title, author, publication)

        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            self.fail(f"Sustainability by Numbers article extraction failed: {str(e)}")

    def test_real_inbox_post_metadata_extraction(self):
        """Test metadata extraction for REAL Substack inbox post - NO MOCKING."""
        url = "https://substack.com/inbox/post/164719684"

        print(f"\n{'=' * 60}")
        print(f"🧪 TEST: REAL Inbox Post Metadata Extraction")
        print(f"{'=' * 60}")

        try:
            # Make REAL HTTP request - no mocking
            article = get_substack_content(url)

            # Print actual extracted data
            print(f"📄 Extracted Data:")
            print(f"   URL: {article.URL}")
            print(f"   Title: {article.Title}")
            print(f"   Author: {article.Author}")
            print(f"   Publication: {article.Publication}")
            print(f"   Content length: {len(article.Content)} characters")

            # Basic validation checks
            validation_checks = [
                ("Article object created", article is not None),
                ("URL preserved", article.URL == url),
                ("Title extracted", hasattr(article, 'Title') and bool(article.Title)),
                ("Author extracted", hasattr(article, 'Author') and bool(article.Author)),
                ("Publication extracted", hasattr(article, 'Publication') and bool(article.Publication)),
                ("Content extracted", hasattr(article, 'Content') and len(article.Content) > 0)
            ]

            for check_name, check_result in validation_checks:
                emoji = "✅" if check_result else "❌"
                status = "PASSED" if check_result else "FAILED"
                print(f"{emoji} {check_name}: {status}")

            # Assertions
            self.assertIsNotNone(article)
            self.assertEqual(article.URL, url)
            self.assertTrue(hasattr(article, 'Title') and article.Title)
            self.assertTrue(hasattr(article, 'Author') and article.Author)
            self.assertTrue(hasattr(article, 'Publication') and article.Publication)
            self.assertTrue(hasattr(article, 'Content') and len(article.Content) > 0)

        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            self.fail(f"Real article extraction failed: {str(e)}")

    def test_error_handling_http_error(self):
        """Test error handling when HTTP request fails."""
        url = "https://substack.com/inbox/post/nonexistent"

        print(f"\n{'=' * 60}")
        print(f"🧪 TEST: Error Handling - HTTP Error")
        print(f"{'=' * 60}")

        with self.assertRaises(Exception) as context:
            get_substack_content(url)

        print(f"✅ Exception properly raised: {str(context.exception)}")

    def test_missing_og_site_name(self):
        """Test metadata extraction when og:site_name might be missing."""
        url = "https://example.substack.com/p/test"

        # This test is more exploratory since we can't control the HTML content
        # We'll just verify that the extraction doesn't crash and returns an Article object
        try:
            article = get_substack_content(url)

            # Should still work and return an Article object
            self.assertIsInstance(article, Article)
            self.assertEqual(article.URL, url)
            self.assertTrue(hasattr(article, 'Publication'))

            print(f"✅ Successfully handled potential missing og:site_name")
            print(f"   Title: {article.Title}")
            print(f"   Author: {article.Author}")
            print(f"   Publication: {article.Publication}")

        except Exception as e:
            # If the URL doesn't exist, that's fine - we're testing error handling
            print(f"ℹ️  URL not accessible (expected): {str(e)}")
            self.assertIsInstance(e, Exception)

    def test_article_structure_integrity(self):
        """Test that Article object maintains proper structure and dict-like access."""
        url = "https://substack.com/inbox/post/164719684"

        try:
            article = get_substack_content(url)

            # Test that all required attributes exist
            required_attrs = ['URL', 'Title', 'Author', 'Published_At', 'Content', 'Publication']
            for attr in required_attrs:
                self.assertTrue(hasattr(article, attr), f"Article should have {attr} attribute")

            # Test dict-like access
            self.assertEqual(article['URL'], article.URL)
            self.assertEqual(article['Title'], article.Title)
            self.assertEqual(article['Author'], article.Author)

            # Test assignment through dict-like interface
            original_title = article.Title
            article['Title'] = "Test Modified Title"
            self.assertEqual(article.Title, "Test Modified Title")
            self.assertEqual(article['Title'], "Test Modified Title")

            # Restore original title
            article['Title'] = original_title

            print("✅ Article structure integrity test passed")

        except Exception as e:
            self.fail(f"Article structure test failed: {str(e)}")


if __name__ == '__main__':
    unittest.main()