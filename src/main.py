#!/usr/bin/env python3
"""
DMRG RSS Generator - Main Application
====================================

A modular RSS and HTML generator for DMRG condensed matter physics papers.
Fetches papers from the DMRG website, enriches with arXiv metadata,
and generates mobile-responsive HTML and RSS feeds with LaTeX rendering.

Usage:
    python generate_rss.py            # fetch source page, update archive, publish
    python generate_rss.py --rebuild  # regenerate all XML/HTML from JSON caches (offline)

Author: DMRG RSS Project
License: MIT
"""

import os
import sys
import time
import logging
import argparse
import requests

# Import our modular components
from .config import (
    TARGET_URL, URL_YEAR, USER_AGENT, MAX_ENTRIES, DOCS_DIR, PUBLIC_BASE_URL,
    CANONICAL_RSS_PATH, CANONICAL_HTML_PATH, current_year_2digit, year_paths,
)
from .utils.arxiv_processor import ArXivProcessor, DMRGPageParser
from .utils.cache_manager import CacheManager, list_cache_years
from .utils.entry_sync import EntrySync
from .utils.text_utils import detect_page_year
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
        self.dmrg_parser = DMRGPageParser(self.session)
        self.arxiv_processor = ArXivProcessor(self.session)
        self.entry_sync = EntrySync(self.arxiv_processor, max_entries=MAX_ENTRIES)
        logging.info("All application components initialized successfully")

    def resolve_page_year(self, dmrg_entries):
        """
        Decide which year's archive the source page belongs to.

        The rolling condmat.html keeps listing last year's papers for several
        days into January, so the year is taken from the arXiv IDs on the page
        rather than from the clock.
        """
        if URL_YEAR:
            return URL_YEAR
        year = detect_page_year(dmrg_entries)
        if not year or year > current_year_2digit:
            logging.warning(f"Could not detect page year (got {year}); using current year {current_year_2digit}")
            return current_year_2digit
        logging.info(f"Source page detected as year 20{year}")
        return year

    def archive_links(self):
        """[(label, html filename)] for every archived year, newest first."""
        years = list_cache_years(DOCS_DIR)
        links = []
        for year in reversed(years):
            href = os.path.basename(CANONICAL_HTML_PATH) if year == years[-1] else os.path.basename(year_paths(year)[1])
            links.append((f"20{year}", href))
        return links

    def generate_year_outputs(self, year, entries):
        """
        Write condmat{YY}.xml/html for one year and, if it is the latest
        archived year, the canonical docs/condmat.xml/html as well.

        Each page links to the RSS feed that is published next to it, so the
        canonical page links to condmat.xml and archive pages to condmat{YY}.xml.
        """
        rss_path, html_path, _ = year_paths(year)
        years = list_cache_years(DOCS_DIR)
        is_latest = bool(years) and year == years[-1]

        feeds = [rss_path] + ([CANONICAL_RSS_PATH] if is_latest else [])
        pages = [(html_path, os.path.basename(rss_path))]
        if is_latest:
            pages.append((CANONICAL_HTML_PATH, os.path.basename(CANONICAL_RSS_PATH)))

        # Older setups published symlinks; never write through one
        for path in feeds + [p for p, _ in pages]:
            if os.path.islink(path):
                os.remove(path)

        for path in feeds:
            feed_url = PUBLIC_BASE_URL + os.path.basename(path)
            if not RSSGenerator(path, feed_url=feed_url).generate_feed(entries):
                raise RuntimeError(f"Failed to generate RSS feed {path}")

        html_generator = HTMLGenerator(html_path, skip_numeric_prices=False,
                                       archive_links=self.archive_links(),
                                       archive_current=f"20{year}")
        if not html_generator.generate_html(entries, outputs=pages):
            raise RuntimeError(f"Failed to generate HTML page {html_path}")

    def rebuild_all(self):
        """Regenerate every year's XML/HTML from the JSON caches (no network)."""
        for year in list_cache_years(DOCS_DIR):
            entries = list(CacheManager(year_paths(year)[2]).load_cache().values())
            logging.info(f"Rebuilding outputs for 20{year} ({len(entries)} entries)")
            self.generate_year_outputs(year, entries)
        return True

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

            # Step 2: Load that year's archive
            year = self.resolve_page_year(dmrg_entries)
            cache_path = year_paths(year)[2]
            is_new_year = not os.path.exists(cache_path)
            cache_manager = CacheManager(cache_path)
            cached_entries = cache_manager.load_cache()

            # Step 3: Synchronize entries
            all_entries, updated_cache = self.entry_sync.sync_entries(
                dmrg_entries, {}, cached_entries
            )

            # Step 4: Save updated cache
            cache_manager.save_cache(updated_cache)

            # Step 5: Generate RSS/HTML (+ canonical copies for the latest year).
            # A new year changes the archive navigation of every page and
            # which year is published canonically, so rebuild everything then.
            if is_new_year:
                logging.info(f"New archive year 20{year}: rebuilding all years")
                self.rebuild_all()
            else:
                self.generate_year_outputs(year, all_entries)

            execution_time = time.time() - start_time
            self.log_sync_statistics(year, all_entries, updated_cache, execution_time)
            return True

        except Exception as e:
            logging.error(f"Full sync failed: {e}")
            return False

    def log_sync_statistics(self, year, all_entries, updated_cache, execution_time):
        """Log a summary of the sync operation."""
        rss_path, html_path, cache_path = year_paths(year)
        logging.info("=== Sync Statistics ===")
        logging.info(f"Total execution time: {execution_time:.2f} seconds")
        logging.info(f"Archive year: 20{year}")
        logging.info(f"Total entries: {len(all_entries)}")
        logging.info(f"Cache entries: {len(updated_cache)}")
        logging.info("=== Full Sync Complete ===")
        logging.info(f"Generated versioned files:")
        logging.info(f"  RSS: {rss_path}")
        logging.info(f"  HTML: {html_path}")
        logging.info(f"  Cache: {cache_path}")

    def get_status(self):
        """
        Get current application status and file information.

        Returns:
            dict: Status information
        """
        status = {}
        for year in list_cache_years(DOCS_DIR):
            rss_path, html_path, cache_path = year_paths(year)
            status[year] = {"cache": CacheManager(cache_path).get_cache_stats(), "files": {}}
            for file_path, name in [(rss_path, "rss"), (html_path, "html")]:
                if os.path.exists(file_path):
                    status[year]["files"][name] = {
                        "exists": True,
                        "size": os.path.getsize(file_path),
                        "modified": os.path.getmtime(file_path)
                    }
                else:
                    status[year]["files"][name] = {"exists": False}
        return status


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Generate DMRG cond-mat RSS feed and HTML pages")
    parser.add_argument("--rebuild", action="store_true",
                        help="regenerate all XML/HTML from the JSON caches without fetching anything")
    args = parser.parse_args()

    try:
        app = DMRGRSSApplication()
        success = app.rebuild_all() if args.rebuild else app.run_full_sync()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
