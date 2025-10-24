#!/usr/bin/env python3
"""
DMRG RSS Generator - Main Application
====================================

A modular RSS and HTML generator for DMRG condensed matter physics papers.
Fetches papers from the DMRG website, enriches with arXiv metadata,
and generates mobile-responsive HTML and RSS feeds with LaTeX rendering.

Author: DMRG RSS Project
License: MIT
"""

import os
import sys
import time
import logging
import requests

# Import our modular components
from .config import (
    TARGET_URL, OUTPUT_RSS_PATH, OUTPUT_HTML_PATH, CACHE_PATH, USER_AGENT, MAX_ENTRIES,
    AUTO_CREATE_SYMLINKS
)
from .utils.arxiv_processor import ArXivProcessor, DMRGPageParser
from .utils.cache_manager import CacheManager
from .utils.entry_sync import EntrySync
from .generators.rss_generator import RSSGenerator
from .generators.html_generator import HTMLGenerator


class DMRGRSSApplication:
    """Main application class for DMRG RSS generation."""
    
    def __init__(self):
        """Initialize the application with all required components."""
        self.setup_logging()
        self.setup_session()
        self.setup_components()
    
    def setup_logging(self):
        """Configure logging with detailed output to both console and file."""
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO, 
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('logs/sync.log', mode='w', encoding='utf-8')
            ]
        )
        
        logging.info("=== DMRG RSS Application Initialized ===")
    
    def setup_session(self):
        """Setup HTTP session with proper headers."""
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        logging.info(f"HTTP session initialized with User-Agent: {USER_AGENT}")
    
    def setup_components(self):
        """Initialize all application components."""
        # Data processing components
        self.dmrg_parser = DMRGPageParser(self.session)
        self.arxiv_processor = ArXivProcessor(self.session)
        self.cache_manager = CacheManager(CACHE_PATH)
        self.entry_sync = EntrySync(self.arxiv_processor, max_entries=MAX_ENTRIES)
        
        # Output generators
        self.rss_generator = RSSGenerator(OUTPUT_RSS_PATH)
        self.html_generator = HTMLGenerator(OUTPUT_HTML_PATH, skip_numeric_prices=False)
        
        logging.info("All application components initialized successfully")
    
    def create_publishing_symlinks(self):
        """
        Create symlinks for publishing layer (URLs without year suffix).
        Only called when TARGET_URL has no year suffix (using current year).
        
        Maps versioned files to clean URLs:
        - docs/condmat.xml → docs/condmat25.xml (symlink)
        - docs/condmat.html → docs/condmat25.html (symlink)
        """
        try:
            import re
            
            # Extract base name and versioned file names
            match = re.search(r'/([^/]+)\.html$', TARGET_URL)
            if not match:
                logging.warning("Could not extract base name from TARGET_URL for symlink creation")
                return
            
            base_name = match.group(1).rstrip('0123456789')
            
            # Get the versioned filenames from config
            versioned_xml = OUTPUT_RSS_PATH
            versioned_html = OUTPUT_HTML_PATH
            publish_xml = f"docs/{base_name}.xml"
            publish_html = f"docs/{base_name}.html"
            
            # Remove old symlinks if they exist
            for link_path in [publish_xml, publish_html]:
                if os.path.lexists(link_path):
                    old_target = os.readlink(link_path) if os.path.islink(link_path) else "file"
                    os.remove(link_path)
                    logging.info(f"Removed existing {link_path} (was → {old_target})")
            
            # Create new symlinks (relative paths for portability)
            symlinks = [
                (os.path.basename(versioned_xml), publish_xml, "RSS"),
                (os.path.basename(versioned_html), publish_html, "HTML")
            ]
            
            for target_basename, link_path, name in symlinks:
                os.symlink(target_basename, link_path)
                logging.info(f"Created {name} symlink: {link_path} → {target_basename}")
            
            logging.info("✓ Publishing symlinks created successfully")
            
        except Exception as e:
            logging.error(f"Failed to create publishing symlinks: {e}")
            # Non-fatal error - continue with file output
    
    def run_full_sync(self):
        """
        Execute a complete synchronization cycle.
        
        Returns:
            bool: True if successful, False otherwise
        """
        start_time = time.time()
        logging.info("=== DMRG RSS Full Sync Started ===")
        
        try:
            # Step 1: Fetch and parse DMRG page
            soup = self.dmrg_parser.fetch_page(TARGET_URL)
            if not soup:
                raise RuntimeError("Failed to fetch DMRG page")

            dmrg_entries = self.dmrg_parser.parse_entries(soup)
            if not dmrg_entries:
                raise RuntimeError("No arXiv entries found on DMRG page")

            # Step 2: Load existing data
            cached_entries = self.cache_manager.load_cache()

            # Step 3: Synchronize entries
            all_entries, updated_cache = self.entry_sync.sync_entries(
                dmrg_entries, {}, cached_entries  # existing_rss_entries no longer used
            )

            # Step 4: Save updated cache
            self.cache_manager.save_cache(updated_cache)

            # Step 5: Generate RSS feed
            if not self.rss_generator.generate_feed(all_entries):
                raise RuntimeError("Failed to generate RSS feed")

            # Step 6: Generate HTML page
            if not self.html_generator.generate_html(all_entries):
                raise RuntimeError("Failed to generate HTML page")

            # Step 7: Create publishing symlinks (if TARGET_URL has no year suffix)
            if AUTO_CREATE_SYMLINKS:
                self.create_publishing_symlinks()

            # Success summary
            execution_time = time.time() - start_time
            self.log_sync_statistics(all_entries, updated_cache, execution_time)
            
            return True

        except Exception as e:
            logging.error(f"Full sync failed: {e}")
            return False
    
    def log_sync_statistics(self, all_entries, updated_cache, execution_time):
        """
        Log comprehensive statistics about the sync operation.
        
        Args:
            all_entries (list): All processed entries
            updated_cache (dict): Updated cache data
            execution_time (float): Total execution time in seconds
        """
        # Calculate new/updated entries
        existing_count = len(all_entries)
        cache_count = len(updated_cache)
        new_count = existing_count - (cache_count if cache_count < existing_count else 0)
        
        logging.info("=== Sync Statistics ===")
        logging.info(f"Total execution time: {execution_time:.2f} seconds")
        logging.info(f"Total entries in RSS/HTML: {existing_count}")
        logging.info(f"New or updated entries: {max(0, new_count)}")
        logging.info(f"Cache entries: {cache_count}")
        logging.info("=== Full Sync Complete ===")
        logging.info(f"Generated versioned files:")
        logging.info(f"  RSS: {OUTPUT_RSS_PATH}")
        logging.info(f"  HTML: {OUTPUT_HTML_PATH}")
        logging.info(f"  Cache: {CACHE_PATH}")
        logging.info("Note: Publishing symlinks managed by separate update_publish.py script")
    
    def get_status(self):
        """
        Get current application status and file information.
        
        Returns:
            dict: Status information
        """
        status = {
            "cache": self.cache_manager.get_cache_stats(),
            "files": {}
        }
        
        # Check output files
        for file_path, name in [(OUTPUT_RSS_PATH, "rss"), (OUTPUT_HTML_PATH, "html")]:
            if os.path.exists(file_path):
                status["files"][name] = {
                    "exists": True,
                    "size": os.path.getsize(file_path),
                    "modified": os.path.getmtime(file_path)
                }
            else:
                status["files"][name] = {"exists": False}
        
        return status


def main():
    """Main entry point for the application."""
    try:
        # Create and run the application
        app = DMRGRSSApplication()
        
        # Execute full synchronization
        success = app.run_full_sync()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
