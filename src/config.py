#!/usr/bin/env python3
"""
Configuration module for DMRG RSS generator.
Contains all configuration constants and settings.

File naming strategy:
  ALL internal files (JSON/XML/HTML) use year suffix for versioning.
  Publishing layer (symlinks) provides clean URLs without suffix.

Dynamic path generation from TARGET_URL:
- TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat.html"
  → All files use current year: entries25.json, condmat25.xml, condmat25.html
  → Symlinks: condmat.xml → condmat25.xml (for publishing)

- TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat24.html"
  → Files use 24: entries24.json, condmat24.xml, condmat24.html
  → Symlinks: condmat.xml → condmat24.xml (for publishing)
"""
import os
import re
from datetime import datetime

# URL and file paths
TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat24.html"

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
_base_name = _extract_base_name_from_url(TARGET_URL)
_url_year = _extract_year_from_url(TARGET_URL)

# Determine the year to use for file suffixes
_year = _url_year if _url_year else current_year_2digit

# Internal storage paths (always with year suffix for versioning)
OUTPUT_RSS_PATH = f"docs/{_base_name}{_year}.xml"
OUTPUT_HTML_PATH = f"docs/{_base_name}{_year}.html"
CACHE_PATH = f"docs/entries{_year}.json"

# Auto-create publishing symlinks only when TARGET_URL has NO year suffix
# (i.e., when using current year data)
AUTO_CREATE_SYMLINKS = _url_year is None

# Clean up temporary variables
del _base_name, _url_year, _year

# HTTP settings
USER_AGENT = "dmrg-rss-fullsync/1.4"
REQUEST_TIMEOUT = 30
ARXIV_API_TIMEOUT = 20
ARXIV_RETRY_COUNT = 3
ARXIV_DELAY_SECONDS = 2

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
