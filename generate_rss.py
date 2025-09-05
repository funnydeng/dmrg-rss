#!/usr/bin/env python3
import os
import re
import sys
import time
import logging
import hashlib
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

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
USER_AGENT = "dmrg-rss-fullsync/1.4"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

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
            title = title_el.text.strip().replace("\n", " ") if title_el is not None else ""
            title = re.sub(r'\s+', ' ', title)

            # Extract abstract
            abstract_el = entry.find(".//{http://www.w3.org/2005/Atom}summary")
            abstract = abstract_el.text.strip().replace("\n", " ") if abstract_el is not None else ""
            abstract = re.sub(r'\s+', ' ', abstract)

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
                re.sub(r'\s+', ' ', a.findtext("{http://www.w3.org/2005/Atom}name", "").strip())
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
    complete = (
        entry.get("title") and entry.get("title").strip() and
        entry.get("abstract") and entry.get("abstract").strip() and 
        entry.get("authors") and entry.get("authors").strip() and
        entry.get("pubdate") and entry.get("pubdate").strip()
    )
    
    if not complete:
        missing_fields = []
        if not (entry.get("title") and entry.get("title").strip()):
            missing_fields.append("title")
        if not (entry.get("abstract") and entry.get("abstract").strip()):
            missing_fields.append("abstract")
        if not (entry.get("authors") and entry.get("authors").strip()):
            missing_fields.append("authors")
        if not (entry.get("pubdate") and entry.get("pubdate").strip()):
            missing_fields.append("pubdate")
        
        logging.info(f"Entry {entry.get('link', 'unknown')} missing fields: {missing_fields}")
    
    return complete

def sync_entries(dmrg_entries, existing_entries):
    """Sync entries and return complete list of entries"""
    # Filter out old entries that are no longer on DMRG page
    dmrg_ids = {e["id"] for e in dmrg_entries}
    filtered_existing = {
        eid: e for eid, e in existing_entries.items() 
        if eid in dmrg_ids
    }
    
    removed_count = len(existing_entries) - len(filtered_existing)
    if removed_count > 0:
        logging.info(f"Filtered existing entries: {len(filtered_existing)} (removed {removed_count} obsolete entries)")
    else:
        logging.info(f"Filtered existing entries: {len(filtered_existing)} (no obsolete entries)")

    # Find entries that need detailed information
    new_or_incomplete = []
    complete_existing = []
    
    for dmrg_entry in dmrg_entries:
        eid = dmrg_entry["id"]
        
        if eid not in filtered_existing:
            # Completely new entry
            new_or_incomplete.append(dmrg_entry)
            logging.debug(f"New entry: {dmrg_entry['link']}")
        else:
            existing = filtered_existing[eid]
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
    
    # Sort by publication date: newest first (displayed first in RSS)
    def pubdate_key(entry):
        if entry.get("pubdate"):
            try:
                return parsedate_to_datetime(entry["pubdate"])
            except Exception as e:
                logging.warning(f"Failed to parse date {entry.get('pubdate')}: {e}")
                return datetime.min
        return datetime.min

    # reverse=True ensures newest articles appear first
    # all_entries.sort(key=pubdate_key, reverse=True)
    
    # Log sorting results
    if all_entries:
        first_entry = all_entries[0]
        last_entry = all_entries[-1]
        first_date = pubdate_key(first_entry).strftime("%Y-%m-%d") if pubdate_key(first_entry) != datetime.min else "Unknown"
        last_date = pubdate_key(last_entry).strftime("%Y-%m-%d") if pubdate_key(last_entry) != datetime.min else "Unknown"
        logging.info(f"Entries sorted by date: newest ({first_date}) to oldest ({last_date})")
    
    logging.info(f"Final sync result: {len(all_entries)} total entries")
    logging.info(f"- {len(complete_existing)} existing complete entries")
    logging.info(f"- {len(detailed_new_entries)} newly fetched/updated entries")
    
    return all_entries

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
            
            if entry.get("pubdate"):
                # Convert date format for RSS compatibility
                try:
                    pubdate_str = entry["pubdate"].strip()
                    
                    # If it's ISO format (arXiv format), convert to RFC-2822
                    if 'T' in pubdate_str and pubdate_str.endswith('Z'):
                        dt = datetime.strptime(pubdate_str, "%Y-%m-%dT%H:%M:%SZ")
                        dt = dt.replace(tzinfo=timezone.utc)
                        rfc_date = dt.strftime("%a, %d %b %Y %H:%M:%S %z")
                        fe.pubDate(rfc_date)
                        formatted_str = dt.strftime("%a, %d %b %Y %H:%M:%S")
                    else:
                        # Already in RFC format or other format
                        fe.pubDate(entry["pubdate"])
                        try:
                            dt = parsedate_to_datetime(entry["pubdate"])
                            formatted_str = dt.strftime("%a, %d %b %Y %H:%M:%S")
                        except:
                            formatted_str = entry["pubdate"]
                    
                    # Log dates for first few entries to verify sorting
                    if i < 3:
                        try:
                            if 'T' in pubdate_str and pubdate_str.endswith('Z'):
                                parsed_date = datetime.strptime(pubdate_str, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
                            else:
                                parsed_date = parsedate_to_datetime(entry["pubdate"]).strftime("%Y-%m-%d")
                            logging.info(f"Entry {i+1} date: {parsed_date}")
                        except:
                            logging.info(f"Entry {i+1} date: {entry['pubdate']} (unparseable)")
                    
                    # Create description with properly formatted date
                    description = f"<b>Author(s):</b> {authors}<br><br><b>Abstract:</b> {abstract}<br><br><b>[<a href='{entry['link']}'>arXiv:{arxiv_id}</a>] Published {formatted_str} UTC</b>"
                    fe.description(description)
                            
                except Exception as e:
                    logging.warning(f"Failed to process pubdate for {entry['link']}: {e}")
                    current_time = datetime.now(timezone.utc)
                    formatted_time = current_time.strftime("%a, %d %b %Y %H:%M:%S %z")
                    fe.pubDate(formatted_time)
                    # Create description with unknown date
                    description = f"<b>Author(s):</b> {authors}<br><br><b>Abstract:</b> {abstract}<br><br><b>[<a href='{entry['link']}'>arXiv:{arxiv_id}</a>] Published Unknown</b>"
                    fe.description(description)

            else:
                # Use current time if no publication date (these entries will appear last)
                current_time = datetime.now(timezone.utc)
                formatted_time = current_time.strftime("%a, %d %b %Y %H:%M:%S %z")
                fe.pubDate(formatted_time)
                logging.warning(f"No pubdate for entry: {entry['link']}")
                
                # Create description with unknown date
                description = f"<b>Author(s):</b> {authors}<br><br><b>Abstract:</b> {abstract}<br><br><b>[<a href='{entry['link']}'>arXiv:{arxiv_id}</a>] Published Unknown</b>"
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
            # Extract authors from description
            authors = ""
            if description:
                try:
                    soup = BeautifulSoup(description, "html.parser")
                    text = soup.get_text()
                    if "Author(s):" in text:
                        authors = text.split("Author(s):", 1)[1].split("Abstract:")[0].strip()
                except:
                    authors = ""
            
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


def main():
    """Main function"""
    logging.info("=== DMRG RSS Full Sync Started ===")
    start_time = time.time()
    
    try:
        # 1. Fetch DMRG page
        soup = fetch_page(TARGET_URL)
        if not soup:
            logging.error("Failed to fetch DMRG page")
            sys.exit(1)

        # 2. Parse arXiv entries
        dmrg_entries = parse_dmrg_entries(soup)
        if not dmrg_entries:
            logging.warning("No arXiv entries found on DMRG page")
            sys.exit(1)

        # For testing: limit to first N entries
        # dmrg_entries = dmrg_entries[:10]
        # logging.info(f"Limited to first {len(dmrg_entries)} entries for testing")

        # 3. Load existing entries
        existing_entries = load_existing_entries(OUTPUT_PATH)

        # 4. Sync entries
        all_entries = sync_entries(dmrg_entries, existing_entries)

        # 5. Generate RSS
        generate_rss(all_entries, OUTPUT_PATH)

        # 6. Output statistics
        elapsed_time = time.time() - start_time
        new_count = len(all_entries) - len([e for e in existing_entries.values() if is_entry_complete(e)])
        
        logging.info("=== Sync Statistics ===")
        logging.info(f"Total execution time: {elapsed_time:.2f} seconds")
        logging.info(f"Total entries in RSS: {len(all_entries)}")
        logging.info(f"New or updated entries: {max(0, new_count)}")
        logging.info("=== Full Sync Complete ===")

    except Exception as e:
        logging.error(f"Sync failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()