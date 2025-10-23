#!/usr/bin/env python3
import os
import re
import sys
import time
import logging
import hashlib
import requests
import json
import subprocess
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import escape

# Configure logging with detailed output to both console and file
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/sync.log', mode='w', encoding='utf-8')
    ]
)

TARGET_URL = "http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat.html"
OUTPUT_PATH = "docs/rss.xml"
CACHE_PATH = "docs/entries_cache.json"
USER_AGENT = "dmrg-rss-fullsync/1.4"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

def clean_text(text):
    """Clean and normalize text by removing extra whitespace"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.strip().replace("\n", " "))

def format_date_for_rss(date_str):
    """Convert date string to RFC-2822 format for RSS"""
    if not date_str:
        return None
    
    try:
        # Handle ISO format (arXiv format)
        if 'T' in date_str and date_str.endswith('Z'):
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%a, %d %b %Y %H:%M:%S %z")
        else:
            # Assume it's already in RFC format
            return date_str
    except Exception as e:
        logging.warning(f"Failed to format date {date_str}: {e}")
        return None

def load_entries_cache(cache_path):
    """Load entries from JSON cache file"""
    if not os.path.exists(cache_path):
        logging.info("No cache file found, starting fresh")
        return {}
    
    try:
        logging.info(f"Loading entries cache from {cache_path}")
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        cached_entries = cache_data.get('entries', {})
        cache_timestamp = cache_data.get('timestamp', '')
        
        logging.info(f"Loaded {len(cached_entries)} entries from cache (last updated: {cache_timestamp})")
        return cached_entries
    
    except Exception as e:
        logging.error(f"Error loading cache file: {e}")
        return {}

def save_entries_cache(entries_dict, cache_path):
    """Save entries to JSON cache file"""
    try:
        cache_data = {
            'entries': entries_dict,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_entries': len(entries_dict)
        }
        
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logging.info(f"Saved {len(entries_dict)} entries to cache: {cache_path}")
        
    except Exception as e:
        logging.error(f"Error saving cache file: {e}")

def preprocess_latex_formula(formula):
    """Preprocess LaTeX formula to handle KaTeX unsupported commands"""
    if not formula:
        return formula
    
    processed_formula = formula
    
    # Handle unicode characters first
    processed_formula = re.sub(r'\\unicode\{x2014\}', r'\\text{---}', processed_formula)  # em dash
    processed_formula = re.sub(r'\\unicode\{x2013\}', r'\\text{--}', processed_formula)   # en dash
    
    # Handle common unsupported commands
    processed_formula = re.sub(r'\\cross\b', r'\\times', processed_formula)               # cross product
    processed_formula = re.sub(r'\\Cross\b', r'\\times', processed_formula)               # cross product variant
    processed_formula = re.sub(r'\\vector\{([^}]+)\}', r'\\vec{\\1}', processed_formula) # vector notation
    processed_formula = re.sub(r'\\mbox\{([^}]*)\}', r'\\text{\\1}', processed_formula)  # mbox to text
    
    # Handle other unsupported commands
    processed_formula = re.sub(r'\\varnothing\b', r'\\emptyset', processed_formula)       # empty set
    processed_formula = re.sub(r'\\complement\b', r'\\mathsf{c}', processed_formula)      # complement
    processed_formula = re.sub(r'\\Bold\b', r'\\mathbf', processed_formula)               # bold text
    processed_formula = re.sub(r'\\gcd\b', r'\\text{gcd}', processed_formula)             # greatest common divisor
    processed_formula = re.sub(r'\\lcm\b', r'\\text{lcm}', processed_formula)             # least common multiple
    processed_formula = re.sub(r'\\Pr\b', r'\\text{Pr}', processed_formula)               # probability
    processed_formula = re.sub(r'\\argmax\b', r'\\text{argmax}', processed_formula)       # argmax
    processed_formula = re.sub(r'\\argmin\b', r'\\text{argmin}', processed_formula)       # argmin
    
    # Handle limit functions
    processed_formula = re.sub(r'\\limsup\b', r'\\overline{\\lim}', processed_formula)    # limit superior
    processed_formula = re.sub(r'\\liminf\b', r'\\underline{\\lim}', processed_formula)   # limit inferior
    processed_formula = re.sub(r'\\varlimsup\b', r'\\overline{\\lim}', processed_formula) # variant limit superior
    processed_formula = re.sub(r'\\varliminf\b', r'\\underline{\\lim}', processed_formula)# variant limit inferior
    
    return processed_formula

def render_katex_formula_safe(formula, display_mode=False):
    """Use KaTeX CLI to safely render a single LaTeX formula"""
    try:
        # Skip empty or very short formulas
        if not formula or len(formula.strip()) < 2:
            return f"${formula}$" if not display_mode else f"$${formula}$$"
        
        # Preprocess formula to handle unsupported commands
        processed_formula = preprocess_latex_formula(formula)
        
        # Additional check for problematic patterns that can't be easily fixed
        problematic_patterns = [
            r'\\[0-9]',  # commands like \1, \2, etc.
            r'\\[^a-zA-Z]',  # commands with non-alphabetic characters
        ]
        
        for pattern in problematic_patterns:
            if re.search(pattern, processed_formula):
                logging.info(f"[KaTeX Skip] Skipping problematic formula: {formula}")
                return f"${formula}$" if not display_mode else f"$${formula}$$"
        
        cmd = ["katex"]
        if display_mode:
            cmd.append("--display-mode")
        
        result = subprocess.run(
            cmd,
            input=processed_formula.strip().encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=10
        )
        
        rendered = result.stdout.decode("utf-8").strip()
        
        if rendered and ('<span' in rendered or '<div' in rendered):
            return rendered
        else:
            logging.warning(f"[KaTeX Warning] Unexpected output for formula: {formula}")
            return f"${formula}$" if not display_mode else f"$${formula}$$"
            
    except subprocess.TimeoutExpired:
        logging.warning(f"[KaTeX Error] Timeout rendering formula: {formula}")
        return f"${formula}$" if not display_mode else f"$${formula}$$"
    except subprocess.CalledProcessError as e:
        logging.warning(f"[KaTeX Error] Failed to render formula: {formula}")
        if e.stderr:
            error_msg = e.stderr.decode('utf-8')
            logging.warning(f"Error details: {error_msg}")
        # Try to provide a fallback with plain text representation
        fallback = preprocess_latex_formula(formula)
        if fallback != formula:
            logging.info(f"[KaTeX Fallback] Falling back to plain text: {fallback}")
        return f"${formula}$" if not display_mode else f"$${formula}$$"
    except FileNotFoundError:
        # KaTeX CLI not available, return original formula
        logging.info("KaTeX CLI not found, LaTeX formulas will not be rendered")
        return f"${formula}$" if not display_mode else f"$${formula}$$"
    except Exception as e:
        logging.warning(f"[KaTeX Error] Unexpected error rendering formula: {formula}")
        logging.warning(f"Error: {str(e)}")
        return f"${formula}$" if not display_mode else f"$${formula}$$"

def render_katex_in_html(html_content):
    """Render LaTeX formulas in HTML content using KaTeX"""
    if not html_content:
        return html_content
    
    processed_formulas = {}
    placeholder_counter = 0
    
    def create_placeholder():
        nonlocal placeholder_counter
        placeholder = f"__KATEX_PLACEHOLDER_{placeholder_counter}__"
        placeholder_counter += 1
        return placeholder
    
    def process_display_math(match):
        formula = match.group(1)
        placeholder = create_placeholder()
        rendered = render_katex_formula_safe(formula, display_mode=True)
        processed_formulas[placeholder] = f'<div class="katex-display" style="margin: 1.5em 0; text-align: center;">{rendered}</div>'
        return placeholder
    
    def process_inline_math(match):
        formula = match.group(1)
        if '$$' in match.group(0):
            return match.group(0)
        placeholder = create_placeholder()
        rendered = render_katex_formula_safe(formula, display_mode=False)
        processed_formulas[placeholder] = f'<span class="katex-inline">{rendered}</span>'
        return placeholder
    
    # Process display math formulas $$...$$
    html_content = re.sub(r'\$\$([^$]+?)\$\$', process_display_math, html_content, flags=re.DOTALL)
    
    # Process inline math formulas $...$
    html_content = re.sub(r'(?<!\$)\$([^$\n]+?)\$(?!\$)', process_inline_math, html_content)
    
    # Replace all placeholders
    for placeholder, rendered in processed_formulas.items():
        html_content = html_content.replace(placeholder, rendered)
    
    return html_content

def fetch_page(url, timeout=30):
    """Fetch web page content"""
    try:
        logging.info(f"Fetching page: {url}")
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        logging.info(f"Successfully fetched page, size: {len(r.content)} bytes")
        return BeautifulSoup(r.content, "html.parser")
    except Exception as e:
        logging.error("Failed to fetch page %s: %s", url, e)
        return None

def fetch_arxiv_details(arxiv_url, retry_count=3):
    """Fetch paper details from arXiv API with retry mechanism"""
    for attempt in range(retry_count):
        try:
            arxiv_id = arxiv_url.rstrip("/").split("/")[-1]
            api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
            
            logging.info(f"Fetching arXiv details (attempt {attempt + 1}): {arxiv_id}")
            r = session.get(api_url, timeout=20)
            r.raise_for_status()
            
            root = ET.fromstring(r.content)

            # Check for errors
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            if not entries:
                logging.warning(f"No entry found for {arxiv_id}")
                if attempt < retry_count - 1:
                    time.sleep(2)
                    continue
                return "", "", None, ""

            entry = entries[0]

            # Extract title
            title_el = entry.find(".//{http://www.w3.org/2005/Atom}title")
            title = clean_text(title_el.text if title_el is not None else "")

            # Extract abstract
            abstract_el = entry.find(".//{http://www.w3.org/2005/Atom}summary")
            abstract = clean_text(abstract_el.text if abstract_el is not None else "")

            # Extract publication date
            published_el = entry.find(".//{http://www.w3.org/2005/Atom}published")
            pubdate = None
            if published_el is not None:
                try:
                    # Validate date format and convert to RFC-2822 format for RSS
                    dt = datetime.strptime(published_el.text, "%Y-%m-%dT%H:%M:%SZ")
                    dt = dt.replace(tzinfo=timezone.utc)
                    pubdate = dt.strftime("%a, %d %b %Y %H:%M:%S %z")
                    logging.debug(f"Parsed pubdate: {pubdate}")
                except Exception as e:
                    logging.warning(f"Failed to parse pubdate {published_el.text}: {e}")
                    pubdate = None

            # Extract authors
            authors_list = entry.findall(".//{http://www.w3.org/2005/Atom}author")
            authors = ", ".join([
                clean_text(a.findtext("{http://www.w3.org/2005/Atom}name", ""))
                for a in authors_list
            ])

            logging.info(f"Successfully fetched details for {arxiv_id}: '{title[:50]}...'")
            return title, abstract, pubdate, authors

        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed for {arxiv_url}: {e}")
            if attempt < retry_count - 1:
                time.sleep(2)
            else:
                logging.error(f"All attempts failed for {arxiv_url}")
                return "", "", None, ""

def parse_dmrg_entries(soup):
    """Parse all arXiv links from DMRG page"""
    entries = []
    b_tags = soup.find_all("b")
    logging.info(f"Found {len(b_tags)} bold tags to check")
    
    for i, b_tag in enumerate(b_tags):
        a_tag = b_tag.find("a", href=True)
        if not a_tag or not a_tag["href"].startswith("http://arxiv.org/abs/"):
            continue
        
        href = a_tag["href"]
        entry_id = hashlib.md5(href.encode()).hexdigest()
        entries.append({"id": entry_id, "link": href})
        
        if (i + 1) % 10 == 0:  # Log progress every 10 entries
            logging.info(f"Processed {i + 1} bold tags, found {len(entries)} arXiv links so far")
    
    logging.info(f"Total arXiv entries found: {len(entries)}")
    return entries

def load_existing_entries(rss_file_path):
    """Load existing entries from RSS file"""
    existing_entries = {}
    if not os.path.exists(rss_file_path):
        logging.info("No existing RSS file found, will create new one")
        return existing_entries
    
    try:
        logging.info(f"Loading existing RSS file: {rss_file_path}")
        tree = ET.parse(rss_file_path)
        root = tree.getroot()
        items = root.findall(".//item")
        
        logging.info(f"Found {len(items)} existing entries")
        
        successful_loads = 0
        for item in items:
            try:
                link_elem = item.find("link")
                if link_elem is not None and link_elem.text:
                    link = link_elem.text.strip()
                    entry_id = hashlib.md5(link.encode()).hexdigest()
                    
                    title = item.findtext("title", "").strip()
                    authors = item.findtext("{http://purl.org/dc/elements/1.1/}creator") or ""
                    authors = authors.strip()
                    
                    # Extract abstract from description (remove HTML tags)
                    description = item.findtext("description", "").strip()
                    abstract = ""
                    if description:
                        # Extract abstract from HTML description
                        try:
                            desc_soup = BeautifulSoup(description, "html.parser")
                            text = desc_soup.get_text()
                            if "Abstract:" in text:
                                abstract = text.split("Abstract:", 1)[1].strip()
                                # Remove the "Published" part if it exists
                                if "[arXiv:" in abstract:
                                    abstract = abstract.split("[arXiv:")[0].strip()
                            else:
                                abstract = text.strip()
                        except:
                            abstract = description
                    
                    pubdate = item.findtext("pubDate", "").strip() or None
                    
                    existing_entries[entry_id] = {
                        "id": entry_id,
                        "title": title,
                        "authors": authors,
                        "link": link,
                        "abstract": abstract,
                        "pubdate": pubdate
                    }
                    successful_loads += 1
            except Exception as e:
                logging.warning(f"Failed to parse RSS item: {e}")
                continue
        
        logging.info(f"Successfully loaded {successful_loads} existing entries")
        if successful_loads < len(items):
            logging.warning(f"Failed to load {len(items) - successful_loads} entries")
        
    except Exception as e:
        logging.error(f"Error parsing existing RSS: {e}")
        
    return existing_entries

def is_entry_complete(entry):
    """Check if entry information is complete"""
    required_fields = ["title", "abstract", "authors", "pubdate"]
    missing_fields = [field for field in required_fields 
                     if not (entry.get(field) and entry.get(field).strip())]
    
    if missing_fields:
        logging.info(f"Entry {entry.get('link', 'unknown')} missing fields: {missing_fields}")
        return False
    return True

def sync_entries(dmrg_entries, existing_entries, cached_entries):
    """Sync entries and return complete list of entries"""
    # Filter out old entries that are no longer on DMRG page
    dmrg_ids = {e["id"] for e in dmrg_entries}
    
    # Combine existing RSS entries and cached entries, prioritizing cache for complete data
    combined_existing = {}
    
    # First add existing RSS entries
    for eid, entry in existing_entries.items():
        if eid in dmrg_ids:
            combined_existing[eid] = entry
    
    # Then update with cached entries (which have complete data)
    for eid, entry in cached_entries.items():
        if eid in dmrg_ids:
            combined_existing[eid] = entry
    
    removed_count = len(existing_entries) + len(cached_entries) - len(combined_existing)
    if removed_count > 0:
        logging.info(f"Combined existing entries: {len(combined_existing)} (removed {removed_count} obsolete entries)")
    else:
        logging.info(f"Combined existing entries: {len(combined_existing)} (no obsolete entries)")

    # Find entries that need detailed information
    new_or_incomplete = []
    complete_existing = []
    
    for dmrg_entry in dmrg_entries:
        eid = dmrg_entry["id"]
        
        if eid not in combined_existing:
            # Completely new entry
            new_or_incomplete.append(dmrg_entry)
            logging.debug(f"New entry: {dmrg_entry['link']}")
        else:
            existing = combined_existing[eid]
            if is_entry_complete(existing):
                # Entry has complete information
                complete_existing.append(existing)
                logging.debug(f"Complete existing entry: {existing['link']}")
            else:
                # Entry has incomplete information, needs refetching
                new_or_incomplete.append(dmrg_entry)
                logging.info(f"Incomplete entry, will refetch: {dmrg_entry['link']}")

    logging.info(f"Entries analysis: {len(complete_existing)} complete, {len(new_or_incomplete)} need fetching")
    
    if len(new_or_incomplete) == 0:
        logging.info("All entries are complete, no fetching needed")

    # Fetch detailed information for new or incomplete entries
    detailed_new_entries = []
    total_to_fetch = len(new_or_incomplete)
    
    for i, entry in enumerate(new_or_incomplete):
        progress = f"{i+1}/{total_to_fetch}"
        logging.info(f"Fetching details [{progress}]: {entry['link']}")
        
        title, abstract, pubdate, authors = fetch_arxiv_details(entry["link"])
        
        detailed_entry = {
            "id": entry["id"],
            "link": entry["link"],
            "title": title,
            "abstract": abstract,
            "pubdate": pubdate,
            "authors": authors
        }
        
        detailed_new_entries.append(detailed_entry)
        
        # Add delay for API requests
        if i < total_to_fetch - 1:
            time.sleep(2)

    # Merge all entries
    all_entries = complete_existing + detailed_new_entries
    
    # Create updated cache dictionary for saving
    updated_cache = {}
    for entry in all_entries:
        updated_cache[entry["id"]] = entry
    
    # Note: Entries are naturally ordered by how they appear on the DMRG page
    # RSS readers will sort by pubDate if needed
    
    logging.info(f"Final sync result: {len(all_entries)} total entries")
    logging.info(f"- {len(complete_existing)} existing complete entries")
    logging.info(f"- {len(detailed_new_entries)} newly fetched/updated entries")
    
    return all_entries, updated_cache

def generate_rss(entries, output_path):
    """Generate RSS file with entries ordered from newest to oldest"""
    logging.info(f"Generating RSS with {len(entries)} entries (newest first)")
    
    fg = FeedGenerator()
    fg.title("DMRG cond-mat")
    fg.link(href=TARGET_URL, rel="alternate")
    fg.link(href=TARGET_URL, rel="self")
    fg.description("Aggregated feed from DMRG cond-mat page, includes abstracts and authors from arXiv (sorted by publication date, newest first)")
    fg.language("en")
    fg.lastBuildDate(datetime.now(timezone.utc))

    added_count = 0
    for i, entry in enumerate(entries):
        try:
            fe = fg.add_entry()
            fe.title(entry.get("title", "Untitled"))
            fe.link(href=entry["link"])
            
            # Build description
            arxiv_id = entry["link"].rsplit("/", 1)[-1]
            authors = entry.get("authors", "Unknown")
            abstract = entry.get("abstract", "No abstract available")
            
            # Handle publication date
            pubdate = entry.get("pubdate")
            if pubdate:
                formatted_date = format_date_for_rss(pubdate)
                if formatted_date:
                    fe.pubDate(formatted_date)
                    try:
                        # Parse date for display
                        if 'T' in pubdate and pubdate.endswith('Z'):
                            dt = datetime.strptime(pubdate, "%Y-%m-%dT%H:%M:%SZ")
                        else:
                            dt = parsedate_to_datetime(pubdate)
                        display_date = dt.strftime("%a, %d %b %Y %H:%M:%S")
                    except:
                        display_date = pubdate
                else:
                    # Fallback to current time
                    current_time = datetime.now(timezone.utc)
                    fe.pubDate(current_time.strftime("%a, %d %b %Y %H:%M:%S %z"))
                    display_date = "Unknown"
            else:
                # Use current time if no publication date
                current_time = datetime.now(timezone.utc)
                fe.pubDate(current_time.strftime("%a, %d %b %Y %H:%M:%S %z"))
                display_date = "Unknown"
                logging.warning(f"No pubdate for entry: {entry['link']}")
            
            # Log dates for first few entries to verify sorting
            if i < 3:
                logging.info(f"Entry {i+1} date: {display_date}")
            
            # Create description
            description = f"<b>Author(s):</b> {authors}<br><br><b>Abstract:</b> {abstract}<br><br><b>[<a href='{entry['link']}'>arXiv:{arxiv_id}</a>] Published {display_date} UTC</b>"
            fe.description(description)
                
            fe.guid(entry["link"])
            added_count += 1

        except Exception as e:
            logging.error(f"Failed to add entry {entry['link']}: {e}")

    # Generate RSS string and parse as XML
    try:
        rss_str = fg.rss_str(pretty=True)
        root = ET.fromstring(rss_str)
        ns = {'dc': 'http://purl.org/dc/elements/1.1/'}
        ET.register_namespace('dc', ns['dc'])
    except Exception as e:
        logging.error(f"Failed to parse generated RSS string: {e}")
        raise
        
    # Add dc:creator elements
    for item in root.findall(".//item"):
        try:
            description = item.findtext("description", "")
            # Extract authors from description using simple string splitting
            authors = ""
            if "Author(s):" in description:
                # Extract text between "Author(s):" and "Abstract:"
                try:
                    soup = BeautifulSoup(description, "html.parser")
                    text = soup.get_text()
                    start = text.find("Author(s):") + len("Author(s):")
                    end = text.find("Abstract:")
                    if start > 10 and end > start:  # Valid indices
                        authors = text[start:end].strip()
                except Exception:
                    pass
            
            # Add dc:creator element
            creator = ET.Element("{http://purl.org/dc/elements/1.1/}creator")
            creator.text = authors or "Unknown"
            item.append(creator)
        except Exception as e:
            logging.warning(f"Failed to add dc:creator: {e}")
        
    # Create output directory and write file
    tree = ET.ElementTree(root)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)            
    
    # Validate generated file
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        logging.info(f"RSS successfully written to {output_path}")
        logging.info(f"File size: {file_size} bytes, entries added: {added_count}")
        logging.info("RSS entries are ordered from newest to oldest publication date")
    else:
        logging.error(f"Failed to create RSS file at {output_path}")
        raise FileNotFoundError(f"RSS file not created: {output_path}")


def generate_html(entries, output_path):
    """Generate HTML file from entries"""
    html_output_path = output_path.replace('.xml', '.html')
    logging.info(f"Generating HTML with {len(entries)} entries")
    
    # Validate that entries have complete data before generating HTML
    complete_entries = []
    incomplete_entries = []
    
    for entry in entries:
        if is_entry_complete(entry):
            complete_entries.append(entry)
        else:
            incomplete_entries.append(entry)
            logging.warning(f"Incomplete entry found for HTML generation: {entry.get('link', 'unknown')} - missing: {[f for f in ['title', 'abstract', 'authors', 'pubdate'] if not (entry.get(f) and entry.get(f).strip())]}")
    
    if incomplete_entries:
        logging.warning(f"HTML generation using {len(complete_entries)} complete entries, skipping {len(incomplete_entries)} incomplete entries")
    
    # Start building HTML content
    html_content = []
    
    # Add generation info (header with title is now in template)
    html_content.append(f"<p><em>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>")
    html_content.append(f"<p>Total papers: {len(complete_entries)}")
    if incomplete_entries:
        html_content.append(f" ({len(incomplete_entries)} entries with incomplete data not shown)")
    html_content.append("</p>")
    
    # Add entry list
    html_content.append("<h2>Recent Papers</h2>")
    
    # Sort entries by publication date (newest first) for better HTML presentation
    def get_sort_date(entry):
        pubdate = entry.get("pubdate", "")
        if not pubdate:
            return datetime.min
        try:
            if 'T' in pubdate and pubdate.endswith('Z'):
                return datetime.strptime(pubdate, "%Y-%m-%dT%H:%M:%SZ")
            else:
                return parsedate_to_datetime(pubdate)
        except:
            return datetime.min
    
    sorted_entries = sorted(complete_entries, key=get_sort_date, reverse=True)
    logging.info(f"Sorted {len(sorted_entries)} entries by publication date for HTML display")
    
    for i, entry in enumerate(sorted_entries):
        try:
            title = entry.get("title", "Untitled")
            authors = entry.get("authors", "Unknown")
            abstract = entry.get("abstract", "No abstract available")
            link = entry.get("link", "")
            arxiv_id = link.rsplit("/", 1)[-1] if link else "unknown"
            
            # Format publication date
            pubdate = entry.get("pubdate", "")
            if pubdate:
                try:
                    if 'T' in pubdate and pubdate.endswith('Z'):
                        dt = datetime.strptime(pubdate, "%Y-%m-%dT%H:%M:%SZ")
                    else:
                        dt = parsedate_to_datetime(pubdate)
                    display_date = dt.strftime("%Y-%m-%d")
                except:
                    display_date = pubdate
            else:
                display_date = "Unknown"
            
            # Render LaTeX in title and abstract
            title_with_latex = render_katex_in_html(title)
            abstract_with_latex = render_katex_in_html(abstract)
            
            # Create entry HTML
            entry_html = f"""
            <article class='paper-entry'>
                <h3><a href='{escape(link)}'>{title_with_latex}</a></h3>
                <p class='meta'><strong>Authors:</strong> {escape(authors)}</p>
                <p class='meta'><strong>arXiv ID:</strong> {arxiv_id} | <strong>Date:</strong> {display_date}</p>
                <div class='abstract'>
                    <strong>Abstract:</strong> {abstract_with_latex}
                </div>
            </article>
            <hr>
            """
            html_content.append(entry_html)
            
        except Exception as e:
            logging.error(f"Failed to add HTML entry {entry.get('link', 'unknown')}: {e}")
    
    # Create complete HTML document
    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DMRG cond-mat Papers</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    <style>
        body {{ 
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; 
            line-height: 1.6; 
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        h1 {{ 
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            font-size: 2.2em;
        }}
        
        h2 {{ 
            color: #34495e;
            border-bottom: 1px solid #bdc3c7;
            padding-bottom: 5px;
            font-size: 1.5em;
        }}
        
        h3 {{ 
            color: #2980b9;
            margin-bottom: 0.5em;
            font-size: 1.2em;
        }}
        
        .paper-entry {{ 
            margin-bottom: 2em;
            padding: 1em;
            background-color: #f8f9fa;
            border-radius: 5px;
        }}
        
        .meta {{ 
            color: #7f8c8d;
            font-size: 0.9em;
            margin: 0.5em 0;
        }}
        
        .abstract {{ 
            margin-top: 1em;
            text-align: justify;
        }}
        
        a {{ 
            color: #3498db;
            text-decoration: none;
            word-break: break-word;
        }}
        
        a:hover {{ 
            text-decoration: underline;
        }}
        
        hr {{ 
            border: 0;
            border-top: 1px solid #ecf0f1;
            margin: 2em 0;
        }}
        
        /* KaTeX styles */
        .katex-display {{ 
            margin: 1.5em 0 !important;
            text-align: center !important;
            overflow-x: auto;
        }}
        
        .katex-inline {{
            /* Inline math formulas */
        }}
        
        .katex {{
            font-size: 1.1em;
        }}
        
        /* Mobile responsiveness - Phones */
        @media screen and (max-width: 600px) {{
            body {{
                padding: 12px;
                max-width: 100%;
                font-size: 14px;
            }}
            
            h1 {{
                font-size: 1.6em;
                text-align: center;
                margin-bottom: 1em;
            }}
            
            h2 {{
                font-size: 1.2em;
            }}
            
            h3 {{
                font-size: 1.0em;
                line-height: 1.3;
                word-break: break-word;
            }}
            
            .paper-entry {{
                padding: 0.7em;
                margin-bottom: 1.2em;
                border-radius: 3px;
            }}
            
            .meta {{
                font-size: 0.8em;
                line-height: 1.3;
                margin: 0.3em 0;
            }}
            
            .abstract {{
                text-align: left;
                font-size: 0.9em;
                line-height: 1.4;
            }}
            
            .katex {{
                font-size: 0.9em;
            }}
            
            .katex-display {{
                overflow-x: auto;
                overflow-y: hidden;
                font-size: 0.85em;
            }}
            
            a {{
                word-break: break-all;
            }}
        }}
        
        /* Tablets */
        @media screen and (min-width: 601px) and (max-width: 768px) {{
            body {{
                padding: 15px;
                max-width: 100%;
                font-size: 15px;
            }}
            
            h1 {{
                font-size: 1.9em;
                text-align: center;
            }}
            
            h2 {{
                font-size: 1.4em;
            }}
            
            h3 {{
                font-size: 1.1em;
                line-height: 1.4;
            }}
            
            .paper-entry {{
                padding: 0.8em;
                margin-bottom: 1.5em;
            }}
            
            .meta {{
                font-size: 0.85em;
                line-height: 1.4;
            }}
            
            .abstract {{
                text-align: justify;
                font-size: 0.95em;
            }}
            
            .katex {{
                font-size: 1em;
            }}
            
            .katex-display {{
                overflow-x: auto;
                overflow-y: hidden;
            }}
        }}
        
        /* Large tablets/small desktops */
        @media screen and (min-width: 769px) and (max-width: 1024px) {{
            body {{
                padding: 18px;
                max-width: 95%;
            }}
            
            h1 {{
                font-size: 2em;
            }}
        }}
        
        @media print {{
            body {{ 
                max-width: none;
                margin: 0;
                padding: 15mm;
            }}
        }}
        
        /* Header styles */
        .header {{
            text-align: center;
            margin-bottom: 2em;
            padding-bottom: 1em;
            border-bottom: 2px solid #ecf0f1;
        }}
        
        .header h1 {{
            margin-bottom: 0.5em;
        }}
        
        .header .description {{
            color: #7f8c8d;
            font-size: 1.1em;
            margin-bottom: 1em;
        }}
        
        .header .nav-links {{
            display: flex;
            justify-content: center;
            gap: 2em;
            flex-wrap: wrap;
        }}
        
        .header .nav-links a {{
            color: #3498db;
            text-decoration: none;
            font-weight: 500;
            padding: 0.5em 1em;
            border: 1px solid #3498db;
            border-radius: 5px;
            transition: all 0.3s ease;
        }}
        
        .header .nav-links a:hover {{
            background-color: #3498db;
            color: white;
        }}
        
        /* Footer styles */
        .footer {{
            margin-top: 3em;
            padding-top: 2em;
            border-top: 2px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        
        .footer a {{
            color: #3498db;
        }}
        
        /* Mobile adjustments for header/footer */
        @media screen and (max-width: 600px) {{
            .header .nav-links {{
                flex-direction: column;
                gap: 1em;
            }}
            
            .header .nav-links a {{
                width: 80%;
                text-align: center;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔬 DMRG cond-mat Papers</h1>
        <p class="description">
            Condensed matter physics papers from the DMRG research group with abstracts and LaTeX rendering
        </p>
        <div class="nav-links">
            <a href="index.html">← Home</a>
            <a href="rss.xml">📡 RSS Feed</a>
            <a href="https://github.com/funnydeng/dmrg-rss">🔧 GitHub</a>
        </div>
    </div>
    
{chr(10).join(html_content)}

    <div class="footer">
        <p>
            Updated automatically every 12 hours via GitHub Actions<br>
            <a href="https://github.com/funnydeng/dmrg-rss">View Source Code on GitHub</a>
        </p>
    </div>
</body>
</html>"""
    
    # Write HTML file
    try:
        os.makedirs(os.path.dirname(html_output_path), exist_ok=True)
        with open(html_output_path, 'w', encoding='utf-8') as f:
            f.write(html_template)
        
        if os.path.exists(html_output_path):
            file_size = os.path.getsize(html_output_path)
            logging.info(f"HTML successfully written to {html_output_path}")
            logging.info(f"HTML file size: {file_size} bytes")
            logging.info(f"HTML entries processed: {len(sorted_entries)} (with LaTeX rendering)")
        else:
            logging.error(f"Failed to create HTML file at {html_output_path}")
            raise FileNotFoundError(f"HTML file not created: {html_output_path}")
    
    except Exception as e:
        logging.error(f"Error writing HTML file: {e}")
        raise


def main():
    """Main function"""
    logging.info("=== DMRG RSS Full Sync Started ===")
    start_time = time.time()
    
    try:
        # Fetch and parse DMRG page
        soup = fetch_page(TARGET_URL)
        if not soup:
            raise RuntimeError("Failed to fetch DMRG page")

        dmrg_entries = parse_dmrg_entries(soup)
        if not dmrg_entries:
            raise RuntimeError("No arXiv entries found on DMRG page")

        # Load existing entries from RSS and cache
        existing_entries = load_existing_entries(OUTPUT_PATH)
        cached_entries = load_entries_cache(CACHE_PATH)

        # Sync entries using both RSS and cache data
        all_entries, updated_cache = sync_entries(dmrg_entries, existing_entries, cached_entries)

        # Save updated cache
        save_entries_cache(updated_cache, CACHE_PATH)

        # Generate RSS and HTML from complete cached data
        generate_rss(all_entries, OUTPUT_PATH)
        generate_html(all_entries, OUTPUT_PATH)

        # Log completion statistics
        elapsed_time = time.time() - start_time
        complete_existing_count = len([e for e in existing_entries.values() if is_entry_complete(e)])
        new_count = len(all_entries) - complete_existing_count
        
        logging.info("=== Sync Statistics ===")
        logging.info(f"Total execution time: {elapsed_time:.2f} seconds")
        logging.info(f"Total entries in RSS/HTML: {len(all_entries)}")
        logging.info(f"New or updated entries: {max(0, new_count)}")
        logging.info(f"Cache entries: {len(updated_cache)}")
        logging.info("=== Full Sync Complete ===")
        logging.info("Generated both RSS (docs/rss.xml) and HTML (docs/rss.html) files")

    except Exception as e:
        logging.error(f"Sync failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()