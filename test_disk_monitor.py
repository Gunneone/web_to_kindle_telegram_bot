#!/usr/bin/env python3
"""
Tests for disk monitor functionality.
"""

import unittest
import tempfile
import shutil
import os
import time
from unittest.mock import patch, Mock
import sys

# Add the main directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disk_monitor import (
    get_disk_usage, get_files_by_age, delete_file_safely,
    delete_empty_directories, cleanup_old_files, DISK_SPACE_THRESHOLD
)


class TestDiskMonitor(unittest.TestCase):
    """Test class for disk monitor functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_dir = tempfile.mkdtemp()
        self.html_dir = os.path.join(self.test_dir, 'html')
        self.epubs_dir = os.path.join(self.test_dir, 'epubs')
        os.makedirs(self.html_dir)
        os.makedirs(self.epubs_dir)

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_get_disk_usage(self):
        """Test disk usage retrieval."""
        total, used, free = get_disk_usage()
        
        # Should return valid numbers
        self.assertGreaterEqual(total, 0)
        self.assertGreaterEqual(used, 0)
        self.assertGreaterEqual(free, 0)
        
        # Total should be sum of used and free (approximately)
        self.assertAlmostEqual(total, used + free, delta=total * 0.01)

    def test_get_files_by_age(self):
        """Test file listing by age."""
        # Create test files with different timestamps
        file1 = os.path.join(self.html_dir, 'old_file.html')
        file2 = os.path.join(self.html_dir, 'new_file.html')
        
        # Create older file first
        with open(file1, 'w') as f:
            f.write('old content')
        
        # Wait a bit to ensure different timestamps
        time.sleep(0.1)
        
        with open(file2, 'w') as f:
            f.write('new content')
        
        files = get_files_by_age(self.html_dir, '*.html')
        
        # Should have 2 files
        self.assertEqual(len(files), 2)
        
        # Files should be sorted by age (oldest first)
        self.assertTrue(files[0][1] < files[1][1])
        self.assertTrue(file1 in files[0][0])
        self.assertTrue(file2 in files[1][0])

    def test_get_files_by_age_nonexistent_directory(self):
        """Test file listing for non-existent directory."""
        files = get_files_by_age('/nonexistent/directory')
        self.assertEqual(files, [])

    def test_delete_file_safely(self):
        """Test safe file deletion."""
        test_file = os.path.join(self.test_dir, 'test_file.txt')
        
        # Create test file
        with open(test_file, 'w') as f:
            f.write('test content')
        
        # File should exist
        self.assertTrue(os.path.exists(test_file))
        
        # Delete file
        result = delete_file_safely(test_file)
        
        # Should return True and file should be gone
        self.assertTrue(result)
        self.assertFalse(os.path.exists(test_file))

    def test_delete_file_safely_nonexistent(self):
        """Test safe deletion of non-existent file."""
        result = delete_file_safely('/nonexistent/file.txt')
        self.assertFalse(result)

    def test_delete_empty_directories(self):
        """Test deletion of empty directories."""
        # Create nested empty directories
        nested_dir = os.path.join(self.epubs_dir, 'empty_subdir', 'nested_empty')
        os.makedirs(nested_dir)
        
        # Directories should exist
        self.assertTrue(os.path.exists(nested_dir))
        
        # Delete empty directories
        delete_empty_directories(self.epubs_dir)
        
        # Empty directories should be removed
        self.assertFalse(os.path.exists(nested_dir))
        # But parent directory should still exist
        self.assertTrue(os.path.exists(self.epubs_dir))

    def test_delete_empty_directories_with_files(self):
        """Test that directories with files are not deleted."""
        # Create directory with a file
        subdir = os.path.join(self.epubs_dir, 'with_file')
        os.makedirs(subdir)
        test_file = os.path.join(subdir, 'file.txt')
        
        with open(test_file, 'w') as f:
            f.write('content')
        
        # Delete empty directories
        delete_empty_directories(self.epubs_dir)
        
        # Directory with file should still exist
        self.assertTrue(os.path.exists(subdir))
        self.assertTrue(os.path.exists(test_file))

    def create_test_files(self, num_html=3, num_epub=2):
        """Helper method to create test files."""
        files_created = []
        
        # Create HTML files
        for i in range(num_html):
            filename = os.path.join(self.html_dir, f'article-{i}-20240101_120000.html')
            with open(filename, 'w') as f:
                f.write(f'<html>Content {i}</html>' * 100)  # Make files a decent size
            files_created.append(filename)
            time.sleep(0.01)  # Ensure different timestamps
        
        # Create EPUB files in subdirectories
        for i in range(num_epub):
            subdir = os.path.join(self.epubs_dir, f'article-{i}')
            os.makedirs(subdir)
            filename = os.path.join(subdir, f'article-{i}.epub')
            with open(filename, 'w') as f:
                f.write(f'EPUB content {i}' * 200)  # Make files a decent size
            files_created.append(filename)
            time.sleep(0.01)  # Ensure different timestamps
        
        return files_created

    def test_cleanup_old_files_integration(self):
        """Test cleanup of old files with actual file operations."""
        # Create test files
        files_created = self.create_test_files(3, 2)
        
        # Verify files exist
        for filepath in files_created:
            self.assertTrue(os.path.exists(filepath))
        
        # Patch the directory constants to point to our test directories
        with patch('disk_monitor.HTML_DIR', self.html_dir), \
             patch('disk_monitor.EPUBS_DIR', self.epubs_dir):
            
            # Simulate low disk space (need to free some bytes)
            space_freed = cleanup_old_files(1024)  # Very small threshold to trigger cleanup
            
            # Should have freed some space (at least one file should be deleted)
            self.assertGreater(space_freed, 0)
            
            # At least one file should be deleted
            remaining_files = [f for f in files_created if os.path.exists(f)]
            self.assertLess(len(remaining_files), len(files_created))

    def test_integration_file_creation_and_cleanup(self):
        """Integration test for file creation and cleanup."""
        # Create test files
        files_created = self.create_test_files(5, 3)
        
        # Verify all files exist
        self.assertEqual(len([f for f in files_created if os.path.exists(f)]), 8)
        
        # Get files by age
        html_files = get_files_by_age(self.html_dir, '*.html')
        epub_files = get_files_by_age(self.epubs_dir, '*.epub')
        
        # Should find all files
        self.assertEqual(len(html_files), 5)
        self.assertEqual(len(epub_files), 3)
        
        # Delete oldest file
        oldest_file = html_files[0][0]
        self.assertTrue(delete_file_safely(oldest_file))
        
        # File should be gone
        self.assertFalse(os.path.exists(oldest_file))
        
        # Should now have 4 HTML files
        html_files_after = get_files_by_age(self.html_dir, '*.html')
        self.assertEqual(len(html_files_after), 4)


if __name__ == '__main__':
    unittest.main()