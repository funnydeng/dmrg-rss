# DMRG RSS Generator - Architecture & Module Design

## Overview

A modular system for generating RSS feeds and HTML pages from DMRG condensed matter physics papers, with automatic arXiv metadata enrichment and LaTeX rendering.

**Key Features:**
- Dynamic configuration from URL (one source of truth)
- Year-versioned file management
- Automatic symlink creation for clean publishing URLs
- Efficient caching with incremental updates
- arXiv API integration with smart batching

---

## Module Organization

```
src/
├── config.py                    # Central configuration
├── main.py                      # Application orchestrator
├── utils/
│   ├── arxiv_processor.py      # arXiv API & DMRG page parsing
│   ├── cache_manager.py        # Cache file I/O & versioning
│   ├── entry_sync.py           # Entry comparison & updates
│   └── text_utils.py           # Text processing utilities
└── generators/
    ├── rss_generator.py        # RSS/XML output
    ├── html_generator.py       # HTML output
    └── latex_renderer.py       # LaTeX → HTML conversion
```

---

## Module Responsibilities

### **config.py** - Configuration & Path Management

**Purpose:** Single source of truth for all configuration

**Key Functions:**
- `_extract_base_name_from_url(url)` - Extract base filename from URL
  - Input: `"http://example.com/condmat24.html"`
  - Output: `"condmat"`
  
- `_extract_year_from_url(url)` - Extract year suffix from URL
  - Input: `"http://example.com/condmat24.html"` → Output: `"24"`
  - Input: `"http://example.com/condmat2024.html"` → Output: `"24"` (last 2 digits)
  - Input: `"http://example.com/condmat.html"` → Output: `None`

**Key Variables:**
- `TARGET_URL` - The DMRG page URL (user configurable)
- `OUTPUT_RSS_PATH` - Auto-generated versioned RSS file path
- `OUTPUT_HTML_PATH` - Auto-generated versioned HTML file path
- `CACHE_PATH` - Auto-generated versioned cache file path
- `AUTO_CREATE_SYMLINKS` - Whether to create clean-URL symlinks
- `MAX_ENTRIES` - Entry limit for testing (None = all entries)

**Design Philosophy:** All paths derive from `TARGET_URL`. Change one URL and everything updates automatically.

---

### **main.py** - Application Orchestrator

**Purpose:** Coordinate the full RSS generation pipeline

**Main Class:** `DMRGRSSApplication`

**Key Methods:**

#### `__init__()`
- Initializes logging system
- Sets up HTTP session
- Instantiates all components

#### `setup_logging()`
- Configures console & file logging
- Ensures `logs/` directory exists
- Output: `logs/sync.log`

#### `setup_session()`
- Creates HTTP session with User-Agent header
- Used for all web requests

#### `setup_components()`
- Instantiates: `DMRGPageParser`, `ArXivProcessor`, `CacheManager`, `EntrySync`
- Instantiates: `RSSGenerator`, `HTMLGenerator`

#### `create_publishing_symlinks()`
- Triggered only if `AUTO_CREATE_SYMLINKS = True` AND URL has no year suffix
- Reads current system date to determine year
- Creates symlinks: `docs/condmat.xml → docs/condmat25.xml`
- Allows clean URLs for web publishing

#### `run_full_sync()` - Main Pipeline
**Steps:**
1. **Fetch DMRG Page** - Get HTML from TARGET_URL
2. **Parse Entries** - Extract arXiv IDs and titles
3. **Load Cache** - Read existing cached entries
4. **Sync Entries** - Compare new vs cached, fetch missing metadata
5. **Save Cache** - Update entries{YY}.json file
6. **Generate RSS** - Create condmat{YY}.xml
7. **Generate HTML** - Create condmat{YY}.html
8. **Create Symlinks** - If enabled, create clean URLs (optional)

#### `log_sync_statistics(all_entries, updated_cache, execution_time)`
- Logs summary: total entries, new entries, cache size, execution time
- Displays file paths and symlink status

#### `get_status()`
- Returns status dict with cache stats and file info
- Used for monitoring

---

### **utils/arxiv_processor.py** - Data Fetching & Parsing

**Purpose:** Interact with arXiv API and parse DMRG website

**Key Classes:**

#### `DMRGPageParser`
- Fetches and parses the DMRG condensed matter page
- `fetch_page(url)` → BeautifulSoup object
- `parse_entries(soup)` → List of entries with arxiv_id and title

#### `ArXivProcessor`
- Queries arXiv API for paper metadata
- `fetch_entry_details(arxiv_id)` → Full entry dict with:
  - `arxiv_id`, `title`, `authors`, `abstract`, `published`
- Implements retry logic and rate limiting (2-second delays)
- Error handling for failed requests

**Design:** Separates DMRG parsing from arXiv API calls for modularity

---

### **utils/cache_manager.py** - Versioned Caching

**Purpose:** Manage JSON cache with year-aware detection

**Key Class:** `CacheManager`

**Key Methods:**

#### `__init__(cache_path)`
- Parses year from filename (e.g., `entries24.json` → year 24)
- Detects if in "latest" mode or "year-specific" mode
- `is_year_specific = True` when year != current_year_2digit

#### `load_cache()`
- Loads from year-specific file (e.g., entries24.json)
- Falls back to current-year file if not found
- Returns dict: `{arxiv_id: entry_dict}`

#### `save_cache(entries_dict)`
- Writes to versioned file (e.g., entries24.json)
- Creates file if doesn't exist
- Preserves formatting for readability

#### `get_cache_stats()`
- Returns size info for logging

**Design:** Year extracted from filename, not hardcoded. Supports historical data storage.

---

### **utils/entry_sync.py** - Smart Entry Synchronization

**Purpose:** Compare new entries with cached ones, identify what needs updating

**Key Class:** `EntrySync`

**Key Methods:**

#### `__init__(arxiv_processor, max_entries=None)`
- `arxiv_processor` - Reference to API client
- `max_entries` - Optional limit for testing

#### `sync_entries(dmrg_entries, existing_rss_entries, cached_entries)`
- **Input:** New entries from DMRG page, existing RSS entries (unused), cached entries
- **Process:**
  1. Apply `max_entries` limit if configured (for testing)
  2. Categorize entries:
     - `complete_existing`: Have full metadata in cache (reuse)
     - `new_or_incomplete`: Missing or incomplete (fetch from arXiv)
  3. Validate cached entries against current DMRG list
  4. Fetch missing details via arXiv API
  5. Merge all entries with timestamps
  
- **Output:** `(all_entries, updated_cache)`
  - `all_entries`: List ready for RSS/HTML generation
  - `updated_cache`: Dict for saving to JSON

**Optimization:** Only fetches arXiv data for new/changed entries, reuses cached data

---

### **utils/text_utils.py** - Text Processing

**Purpose:** Helper functions for text manipulation

**Key Functions:**
- Clean and normalize text
- Extract metadata from strings
- Validate input data

---

### **generators/rss_generator.py** - RSS/XML Output

**Purpose:** Generate RSS 2.0 compliant XML feed

**Key Class:** `RSSGenerator`

#### `__init__(output_path)`
- `output_path` - Where to write condmat{YY}.xml

#### `generate_feed(entries)`
- Creates valid RSS 2.0 XML
- Includes: title, description, link, author, pub date
- Embeds HTML-rendered abstract with LaTeX
- Returns True if successful

**Output:** Valid RSS 2.0 file with all entries

---

### **generators/html_generator.py** - HTML Output

**Purpose:** Generate mobile-responsive HTML page

**Key Class:** `HTMLGenerator`

#### `__init__(output_path, skip_numeric_prices=False)`
- `output_path` - Where to write condmat{YY}.html
- `skip_numeric_prices` - Whether to skip price extraction

#### `generate_html(entries)`
- Creates responsive HTML5 page
- Renders LaTeX in abstracts
- Includes: entry cards, metadata, sorting
- Mobile-friendly design
- Returns True if successful

**Output:** Standalone HTML file ready for web serving

---

### **generators/latex_renderer.py** - LaTeX Rendering

**Purpose:** Convert LaTeX math to HTML using KaTeX

**Key Class:** `LaTeXRenderer`

#### `render_latex(text)`
- Converts LaTeX expressions to HTML
- Supports: `$...$` (inline) and `$$...$$` (display)
- Uses KaTeX for rendering
- Falls back gracefully on errors

---

## Data Flow

```
TARGET_URL
    ↓
[config.py extracts base_name, year]
    ↓
generate_rss.py → main.py
    ↓
[DMRGPageParser] → Fetch & Parse DMRG page
    ↓
dmrg_entries (list of {arxiv_id, title})
    ↓
[CacheManager] → Load cached entries
    ↓
[EntrySync] → Compare & identify missing
    ↓
[ArXivProcessor] → Fetch details from arXiv API
    ↓
all_entries (complete metadata)
    ↓
[CacheManager] → Save to entries{YY}.json
    ↓
[RSSGenerator] → Generate condmat{YY}.xml
[HTMLGenerator] → Generate condmat{YY}.html
    ↓
[create_publishing_symlinks] → condmat.xml, condmat.html (if enabled)
    ↓
Done! Ready for web serving
```

---

## Configuration Flow

```
TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat24.html"
    ↓
_extract_base_name_from_url() → "condmat"
_extract_year_from_url() → "24"
    ↓
OUTPUT_RSS_PATH = "docs/condmat24.xml"
OUTPUT_HTML_PATH = "docs/condmat24.html"
CACHE_PATH = "docs/entries24.json"
AUTO_CREATE_SYMLINKS = False (has year suffix)
    ↓
Generate versioned files without creating symlinks
```

```
TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat.html"
    ↓
_extract_base_name_from_url() → "condmat"
_extract_year_from_url() → None
    ↓
current_year = "25"
OUTPUT_RSS_PATH = "docs/condmat25.xml"
OUTPUT_HTML_PATH = "docs/condmat25.html"
CACHE_PATH = "docs/entries25.json"
AUTO_CREATE_SYMLINKS = True (no year suffix)
    ↓
Generate versioned files AND create symlinks:
  condmat.xml → condmat25.xml
  condmat.html → condmat25.html
```

---

## Error Handling

- **Network errors:** Retry with exponential backoff
- **arXiv API failures:** Skip entry, log error, continue
- **Cache read/write errors:** Log and continue (non-fatal)
- **LaTeX rendering errors:** Fall back to plain text
- **Missing files for symlink:** Log error, don't create symlink

---

## Performance Considerations

1. **Caching:** Avoid re-fetching unchanged entries from arXiv
2. **Rate Limiting:** 2-second delays between arXiv API calls
3. **Batching:** Process entries in logical groups
4. **Incremental Updates:** Only sync new or changed entries
5. **File I/O:** Buffered writes, single pass generation

---

## Testing

**Quick Test Mode:**
```python
# In config.py
MAX_ENTRIES = 5  # Process only 5 entries instead of all
```

**Version Testing:**
```python
# Change TARGET_URL to test different years
TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat24.html"
# Generates: condmat24.xml, entries24.json (2024 data)
```

---

## Production Checklist

- [ ] Set `MAX_ENTRIES = None` (process all entries)
- [ ] Set `TARGET_URL` to desired source
- [ ] Verify `OUTPUT_RSS_PATH`, `OUTPUT_HTML_PATH` are correct
- [ ] Test symlink creation if `AUTO_CREATE_SYMLINKS = True`
- [ ] Set up cron job for regular execution
- [ ] Configure web server to serve `docs/` directory
- [ ] Monitor `logs/sync.log` for errors

---

## Extension Points

- **Add new data source:** Create new parser in `arxiv_processor.py`
- **Change output format:** Create new generator in `generators/`
- **Custom LaTeX rendering:** Override in `latex_renderer.py`
- **Different caching strategy:** Extend `CacheManager`
- **Custom entry validation:** Hook in `EntrySync.sync_entries()`
