#!/usr/bin/env python3
"""
RSS feed generator module.
"""
import os
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from feedgen.feed import FeedGenerator
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

from ..utils.text_utils import format_date_for_rss, latex_to_unicode, generate_entry_id, is_entry_complete, entry_sort_date
from .latex_renderer import LaTeXRenderer
from ..config import RSS_TITLE, RSS_DESCRIPTION, RSS_LANGUAGE, TARGET_URL


class RSSGenerator:
    """Generator for RSS feed from entry data."""
    
    def __init__(self, output_path, feed_url=None):
        """
        Initialize RSS generator.
        
        Args:
            output_path (str): Path where RSS file will be saved
            feed_url (str): Public URL of the feed (for the rel="self" link)
        """
        self.output_path = output_path
        self.feed_url = feed_url
    
    def load_existing_entries(self):
        """
        Load existing entries from RSS file.
        
        Returns:
            dict: Dictionary of existing entries indexed by entry ID
        """
        existing_entries = {}
        if not os.path.exists(self.output_path):
            logging.info("No existing RSS file found, will create new one")
            return existing_entries
        
        try:
            logging.info(f"Loading existing RSS file: {self.output_path}")
            tree = ET.parse(self.output_path)
            root = tree.getroot()
            items = root.findall(".//item")
            
            logging.info(f"Found {len(items)} existing entries")
            
            successful_loads = 0
            for item in items:
                try:
                    link_elem = item.find("link")
                    if link_elem is not None and link_elem.text:
                        link = link_elem.text.strip()
                        entry_id = generate_entry_id(link)
                        
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
    
    def generate_feed(self, entries):
        """
        Generate RSS feed with entries ordered from newest to oldest.
        
        Args:
            entries (list): List of entry dictionaries
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Items without metadata would show up in feed readers as blank posts
        # (and readers keep the first version they see of a guid), so wait
        # until the next run has fetched them.
        skipped = [e for e in entries if not is_entry_complete(e)]
        if skipped:
            logging.warning(f"RSS: skipping {len(skipped)} entries with incomplete metadata")
        entries = sorted((e for e in entries if is_entry_complete(e)), key=entry_sort_date, reverse=True)
        logging.info(f"Generating RSS with {len(entries)} entries (newest first)")
        
        # Formulas become MathML: feed readers do not load the KaTeX stylesheet
        # the HTML output needs, and readers without MathML support still show
        # the formula's text.
        latex_renderer = LaTeXRenderer()
        latex_renderer.prerender_texts([latex_to_unicode(e.get("abstract", "")) for e in entries], output="mathml")

        fg = FeedGenerator()
        fg.title(RSS_TITLE)
        fg.link(href=TARGET_URL, rel="alternate")
        fg.link(href=self.feed_url or TARGET_URL, rel="self")
        fg.description(RSS_DESCRIPTION)
        fg.language(RSS_LANGUAGE)
        fg.lastBuildDate(datetime.now(timezone.utc))

        added_count = 0
        for i, entry in enumerate(entries):
            try:
                # Convert LaTeX accents to Unicode
                title = latex_to_unicode(entry.get("title", "Untitled"))
                authors = latex_to_unicode(entry.get("authors", "Unknown"))
                abstract = latex_renderer.render_in_html(
                    latex_to_unicode(entry.get("abstract", "No abstract available")), output="mathml")
                
                fe = fg.add_entry(order='append')
                fe.title(title)
                fe.link(href=entry["link"])
                
                # Build description
                arxiv_id = entry["link"].rsplit("/", 1)[-1]
                
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
            return False
            
        # Add dc:creator elements (shown as the item's author by feed readers)
        creators = {e["link"]: format_creator(latex_to_unicode(e.get("authors", ""))) for e in entries}
        for item in root.findall(".//item"):
            creator = ET.Element("{http://purl.org/dc/elements/1.1/}creator")
            creator.text = creators.get(item.findtext("link", "").strip()) or "Unknown"
            item.append(creator)

        # Create output directory and write file
        try:
            tree = ET.ElementTree(root)
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            tree.write(self.output_path, encoding="utf-8", xml_declaration=True)            
            
            # Validate generated file
            if os.path.exists(self.output_path):
                file_size = os.path.getsize(self.output_path)
                logging.info(f"RSS successfully written to {self.output_path}")
                logging.info(f"File size: {file_size} bytes, entries added: {added_count}")
                logging.info("RSS entries are ordered from newest to oldest publication date")
                return True
            else:
                logging.error(f"Failed to create RSS file at {self.output_path}")
                return False
                
        except Exception as e:
            logging.error(f"Error writing RSS file: {e}")
            return False


def format_creator(authors, max_listed=3):
    """
    Short author line for dc:creator: everyone for up to max_listed authors,
    otherwise "First Author et al." (the full list stays in the description).
    """
    names = [n.strip() for n in (authors or "").split(",") if n.strip()]
    if len(names) <= max_listed:
        return ", ".join(names)
    return f"{names[0]} et al."
