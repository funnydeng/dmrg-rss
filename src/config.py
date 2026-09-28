#!/usr/bin/env python3
"""
Configuration module for DMRG RSS generator.
Contains all configuration constants and settings.

File naming strategy:
  ALL internal files (JSON/XML/HTML) use year suffix for versioning.
  Publishing layer uses canonical copies for clean URLs (no symlinks).
  Every year keeps its own entries{YY}.json / condmat{YY}.xml / condmat{YY}.html
  archive; docs/condmat.{xml,html} always hold the latest year.

Dynamic path generation from TARGET_URL:
- TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat.html"
  → Year detected from the page's arXiv IDs, e.g. 26: entries26.json, condmat26.xml, condmat26.html
  → Canonical published copies: docs/condmat.xml <- docs/condmat26.xml

- TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat24.html"
  → Files use 24: entries24.json, condmat24.xml, condmat24.html
  → Canonical copies only updated if 24 is the latest archived year
"""
import os
import re
from datetime import datetime

# URL and file paths
TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat.html"

# Get current year (last 2 digits)
current_year_2digit = str(datetime.now().year)[-2:]

# Auto-generate output paths from TARGET_URL
def _extract_base_name_from_url(url):
    """Extract base filename from URL (e.g., 'condmat' from URL ending with 'condmat.html')"""
    match = re.search(r'/([^/]+)\.html$', url)
    if match:
        return match.group(1).rstrip('0123456789')  # Remove trailing digits
    return 'condmat'  # fallback

def _extract_year_from_url(url):
    """
    Extract year suffix from URL.
    Examples:
    - 'http://.../condmat.html' → None (use current year)
    - 'http://.../condmat24.html' → '24'
    - 'http://.../condmat2024.html' → '24' (last 2 digits)
    """
    match = re.search(r'/([^/]+)\.html$', url)
    if match:
        filename = match.group(1)
        # Extract trailing digits
        digits_match = re.search(r'(\d+)$', filename)
        if digits_match:
            digits = digits_match.group(1)
            return digits[-2:]  # Return last 2 digits
    return None

# Extract base name and year from URL
BASE_NAME = _extract_base_name_from_url(TARGET_URL)

# Year of the source page if the URL pins one (e.g. condmat24.html → "24").
# For the rolling page (condmat.html) this is None and the year is detected
# from the arXiv IDs listed on the page at run time (see detect_page_year):
# the source page keeps showing last year's papers for a few days after
# New Year, so the system clock is not a reliable indicator.
URL_YEAR = _extract_year_from_url(TARGET_URL)

DOCS_DIR = "docs"

# Where docs/ is served (GitHub Pages)
PUBLIC_BASE_URL = "https://funnydeng.github.io/dmrg-rss/"

# Canonical publishing paths (clean URLs, always the latest year)
CANONICAL_RSS_PATH = f"{DOCS_DIR}/{BASE_NAME}.xml"
CANONICAL_HTML_PATH = f"{DOCS_DIR}/{BASE_NAME}.html"


def year_paths(year):
    """Return the versioned (rss, html, cache) paths for a 2-digit year."""
    return (
        f"{DOCS_DIR}/{BASE_NAME}{year}.xml",
        f"{DOCS_DIR}/{BASE_NAME}{year}.html",
        f"{DOCS_DIR}/entries{year}.json",
    )


# Internal storage paths for the configured/current year (kept for compatibility)
_year = URL_YEAR if URL_YEAR else current_year_2digit
OUTPUT_RSS_PATH, OUTPUT_HTML_PATH, CACHE_PATH = year_paths(_year)
del _year

# HTTP settings
USER_AGENT = "dmrg-rss-fullsync/1.4"
REQUEST_TIMEOUT = 30
ARXIV_API_TIMEOUT = 20
ARXIV_RETRY_COUNT = 3
ARXIV_DELAY_SECONDS = 3  # arXiv API terms ask for >= 3s between requests
ARXIV_BATCH_SIZE = 50

# Maximum number of entries to process (None = all entries)
# Set to a small number (e.g., 5) for quick testing
# Set to None for production (process all entries)
MAX_ENTRIES = None

# LaTeX rendering settings
KATEX_TIMEOUT = 10

# RSS feed metadata
RSS_TITLE = "DMRG cond-mat"
RSS_DESCRIPTION = "Aggregated feed from DMRG cond-mat page, includes abstracts and authors from arXiv (sorted by publication date, newest first)"
RSS_LANGUAGE = "en"

# HTML metadata
HTML_TITLE = "DMRG cond-mat Papers"
HTML_DESCRIPTION = "Condensed matter physics papers from the DMRG research group with abstracts and LaTeX rendering"
