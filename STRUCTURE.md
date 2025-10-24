#!/usr/bin/env python3
"""
DMRG RSS Generator - Main Application
====================================

A modular RSS and HTML generator for DMRG condensed matter physics papers.
Fetches papers from the DMRG website, enriches with arXiv metadata,
and generates mobile-responsive HTML and RSS feeds with LaTeX rendering.

Entry Point:
  python generate_rss.py

Project Structure:
  root/
  ├── generate_rss.py          (Main entry point wrapper)
  ├── src/                      (Source code package)
  │   ├── __init__.py
  │   ├── config.py             (Configuration constants)
  │   ├── main.py               (Main application logic)
  │   ├── utils/                (Utility modules)
  │   │   ├── __init__.py
  │   │   ├── text_utils.py     (Text processing, accent conversion)
  │   │   ├── cache_manager.py  (JSON cache management)
  │   │   ├── arxiv_processor.py (arXiv API fetching)
  │   │   └── entry_sync.py     (Entry synchronization logic)
  │   └── generators/           (Output generation modules)
  │       ├── __init__.py
  │       ├── latex_renderer.py (LaTeX to HTML conversion)
  │       ├── rss_generator.py  (RSS XML generation)
  │       └── html_generator.py (HTML generation)
  ├── docs/                     (Generated output)
  │   ├── rss.xml               (RSS Feed)
  │   ├── rss.html              (HTML view)
  │   ├── entries_cache.json    (Entry cache)
  │   └── index.html            (Landing page)
  ├── requirements.txt          (Python dependencies)
  └── .github/
      └── workflows/
          └── update-rss.yml    (GitHub Actions configuration)

File Paths:
  All paths are RELATIVE to the root directory:
  - OUTPUT_RSS_PATH = "docs/rss.xml"
  - OUTPUT_HTML_PATH = "docs/rss.html"
  - CACHE_PATH = "docs/entries_cache.json"
  
  This means when running from root:
    python generate_rss.py
  
  Files are created at:
    ./docs/rss.xml
    ./docs/rss.html
    ./docs/entries_cache.json

GitHub Actions:
  The workflow file (.github/workflows/update-rss.yml) does NOT require changes.
  It runs: python generate_rss.py
  Which automatically imports from src/ and generates files at relative paths.
  
  The workflow:
  1. ✅ Checks out repo
  2. ✅ Sets up Python
  3. ✅ Installs dependencies
  4. ✅ Runs: python generate_rss.py
     - This triggers generate_rss.py wrapper
     - Which imports src.main.main()
     - Which generates docs/rss.xml, docs/rss.html, etc.
  5. ✅ Validates generated files
  6. ✅ Commits and pushes changes

Key Design Decisions:
  - Relative paths used for portability across environments
  - generate_rss.py remains at root for GitHub Actions compatibility
  - All Python source code organized in src/ package
  - Modular architecture with clear separation of concerns
  - Backward compatible with existing CI/CD pipeline

Running Locally:
  cd /path/to/dmrg-rss
  python generate_rss.py
  
  Output files:
  - docs/rss.xml     (RSS feed)
  - docs/rss.html    (HTML viewer)
  - logs/sync.log    (Execution log)
"""

print(__doc__)
