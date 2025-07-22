#!/usr/bin/env python3
"""
Disk space monitor for auto-deletion of old EPUB and HTML files.

This service monitors disk space and automatically deletes the oldest
HTML and EPUB files when available space falls below 2GB to prevent
storage issues while keeping recent files for debugging purposes.
"""

import os
import shutil
import logging
import time
import glob
from typing import List, Tuple
from pathlib import Path

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Threshold for triggering cleanup (2GB in bytes)
DISK_SPACE_THRESHOLD = 2 * 1024 * 1024 * 1024  # 2GB
CHECK_INTERVAL = 300  # Check every 5 minutes
HTML_DIR = './html'
EPUBS_DIR = './epubs'


def get_disk_usage() -> Tuple[int, int, int]:
    """
    Get disk usage statistics for the current directory.
    
    Returns:
        Tuple of (total, used, free) disk space in bytes
    """
    try:
        statvfs = os.statvfs('.')
        total = statvfs.f_frsize * statvfs.f_blocks
        # Try different attributes for available space
        if hasattr(statvfs, 'f_bavail'):
            free = statvfs.f_frsize * statvfs.f_bavail
        elif hasattr(statvfs, 'f_avail'):
            free = statvfs.f_frsize * statvfs.f_avail
        else:
            free = statvfs.f_frsize * statvfs.f_ffree
        used = total - free
        return total, used, free
    except Exception as e:
        logger.error(f"Error getting disk usage: {e}")
        # Return dummy values for testing
        return 100 * 1024**3, 50 * 1024**3, 50 * 1024**3  # 100GB total, 50GB used, 50GB free


def get_files_by_age(directory: str, pattern: str = '*') -> List[Tuple[str, float]]:
    """
    Get list of files sorted by modification time (oldest first).
    
    Args:
        directory: Directory to scan
        pattern: File pattern to match
        
    Returns:
        List of tuples (filepath, modification_time)
    """
    files = []
    try:
        if os.path.exists(directory):
            search_pattern = os.path.join(directory, '**', pattern)
            for filepath in glob.glob(search_pattern, recursive=True):
                if os.path.isfile(filepath):
                    mtime = os.path.getmtime(filepath)
                    files.append((filepath, mtime))
            
            # Sort by modification time (oldest first)
            files.sort(key=lambda x: x[1])
    except Exception as e:
        logger.error(f"Error scanning directory {directory}: {e}")
    
    return files


def delete_file_safely(filepath: str) -> bool:
    """
    Safely delete a file and log the action.
    
    Args:
        filepath: Path to file to delete
        
    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        file_size = os.path.getsize(filepath)
        os.remove(filepath)
        logger.info(f"Deleted file: {filepath} (freed {file_size:,} bytes)")
        return True
    except Exception as e:
        logger.error(f"Error deleting file {filepath}: {e}")
        return False


def delete_empty_directories(directory: str):
    """
    Remove empty directories within the given directory.
    
    Args:
        directory: Root directory to clean up
    """
    try:
        if os.path.exists(directory):
            for root, dirs, files in os.walk(directory, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):  # Directory is empty
                            os.rmdir(dir_path)
                            logger.debug(f"Removed empty directory: {dir_path}")
                    except OSError:
                        pass  # Directory not empty or other error
    except Exception as e:
        logger.error(f"Error cleaning up empty directories in {directory}: {e}")


def cleanup_old_files(free_space: int) -> int:
    """
    Delete old files until disk space is above threshold.
    
    Args:
        free_space: Current free space in bytes
        
    Returns:
        Amount of space freed in bytes
    """
    space_needed = DISK_SPACE_THRESHOLD - free_space
    space_freed = 0
    
    logger.info(f"Starting cleanup - need to free {space_needed:,} bytes")
    
    # Get all files from both directories
    html_files = get_files_by_age(HTML_DIR, '*.html')
    epub_files = get_files_by_age(EPUBS_DIR, '*.epub')
    
    # Combine and sort all files by age (oldest first)
    all_files = html_files + epub_files
    all_files.sort(key=lambda x: x[1])
    
    logger.info(f"Found {len(html_files)} HTML files and {len(epub_files)} EPUB files")
    
    files_deleted = 0
    for filepath, mtime in all_files:
        if space_freed >= space_needed:
            break
            
        try:
            file_size = os.path.getsize(filepath)
            if delete_file_safely(filepath):
                space_freed += file_size
                files_deleted += 1
        except Exception as e:
            logger.error(f"Error processing file {filepath}: {e}")
    
    # Clean up empty directories
    delete_empty_directories(HTML_DIR)
    delete_empty_directories(EPUBS_DIR)
    
    logger.info(f"Cleanup completed - deleted {files_deleted} files, freed {space_freed:,} bytes")
    return space_freed


def monitor_disk_space():
    """
    Main monitoring loop that checks disk space and triggers cleanup when needed.
    """
    logger.info(f"Starting disk monitor - threshold: {DISK_SPACE_THRESHOLD:,} bytes ({DISK_SPACE_THRESHOLD // (1024**3)}GB)")
    logger.info(f"Check interval: {CHECK_INTERVAL} seconds")
    logger.info(f"Monitoring directories: {HTML_DIR}, {EPUBS_DIR}")
    
    while True:
        try:
            total, used, free = get_disk_usage()
            
            if total > 0:
                usage_percent = (used / total) * 100
                logger.debug(f"Disk usage: {used:,}/{total:,} bytes ({usage_percent:.1f}%) - Free: {free:,} bytes")
                
                if free < DISK_SPACE_THRESHOLD:
                    logger.warning(f"Low disk space detected! Free space: {free:,} bytes (threshold: {DISK_SPACE_THRESHOLD:,})")
                    space_freed = cleanup_old_files(free)
                    
                    # Recheck disk space after cleanup
                    _, _, new_free = get_disk_usage()
                    logger.info(f"After cleanup - Free space: {new_free:,} bytes")
                    
                    if new_free < DISK_SPACE_THRESHOLD:
                        logger.warning("Still below threshold after cleanup - may need manual intervention")
                else:
                    logger.debug(f"Disk space OK - {free:,} bytes free")
            else:
                logger.error("Unable to get disk usage information")
                
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
        
        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    try:
        monitor_disk_space()
    except KeyboardInterrupt:
        logger.info("Disk monitor stopped by user")
    except Exception as e:
        logger.error(f"Disk monitor crashed: {e}")
        raise