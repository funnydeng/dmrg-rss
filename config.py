#!/usr/bin/env python3
"""
Configuration module for DMRG RSS generator.
Contains all configuration constants and settings.
"""

# URL and file paths
TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat.html"
OUTPUT_RSS_PATH = "docs/rss.xml"
OUTPUT_HTML_PATH = "docs/rss.html"
CACHE_PATH = "docs/entries_cache.json"

# HTTP settings
USER_AGENT = "dmrg-rss-fullsync/1.4"
REQUEST_TIMEOUT = 30
ARXIV_API_TIMEOUT = 20
ARXIV_RETRY_COUNT = 3
ARXIV_DELAY_SECONDS = 2

# LaTeX rendering settings
KATEX_TIMEOUT = 10

# RSS feed metadata
RSS_TITLE = "DMRG cond-mat"
RSS_DESCRIPTION = "Aggregated feed from DMRG cond-mat page, includes abstracts and authors from arXiv (sorted by publication date, newest first)"
RSS_LANGUAGE = "en"

# HTML metadata
HTML_TITLE = "DMRG cond-mat Papers"
HTML_DESCRIPTION = "Condensed matter physics papers from the DMRG research group with abstracts and LaTeX rendering"