#!/usr/bin/env python3
"""
ArXiv data processor for fetching and parsing paper details.
"""
import time
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from .text_utils import clean_text, generate_entry_id
from ..config import ARXIV_API_TIMEOUT, ARXIV_RETRY_COUNT, ARXIV_DELAY_SECONDS


class ArXivProcessor:
    """Handles fetching and processing of arXiv paper data."""
    
    def __init__(self, session):
        """
        Initialize ArXiv processor.
        
        Args:
            session (requests.Session): HTTP session for requests
        """
        self.session = session
    
    def fetch_paper_details(self, arxiv_url, retry_count=ARXIV_RETRY_COUNT):
        """
        Fetch paper details from arXiv API with retry mechanism.
        
        Args:
            arxiv_url (str): URL to the arXiv paper
            retry_count (int): Number of retry attempts
            
        Returns:
            tuple: (title, abstract, pubdate, authors)
        """
        for attempt in range(retry_count):
            try:
                arxiv_id = arxiv_url.rstrip("/").split("/")[-1]
                api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
                
                logging.info(f"Fetching arXiv details (attempt {attempt + 1}): {arxiv_id}")
                r = self.session.get(api_url, timeout=ARXIV_API_TIMEOUT)
                r.raise_for_status()
                
                root = ET.fromstring(r.content)
    
                # Check for errors
                entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
                if not entries:
                    logging.warning(f"No entry found for {arxiv_id}")
                    if attempt < retry_count - 1:
                        time.sleep(ARXIV_DELAY_SECONDS)
                        continue
                    return "", "", None, ""
    
                entry = entries[0]
    
                # Extract title
                title_el = entry.find(".//{http://www.w3.org/2005/Atom}title")
                title = clean_text(title_el.text if title_el is not None else "")
    
                # Extract abstract - need to handle LaTeX with < and > properly
                abstract_el = entry.find(".//{http://www.w3.org/2005/Atom}summary")
                if abstract_el is not None:
                    # Use itertext() to get all text including nested elements
                    # This handles cases where LaTeX formulas like $1<c<2$ are present
                    abstract_text = ''.join(abstract_el.itertext())
                    abstract = clean_text(abstract_text)
                else:
                    abstract = ""
    
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
                    time.sleep(ARXIV_DELAY_SECONDS)
                else:
                    logging.error(f"All attempts failed for {arxiv_url}")
                    return "", "", None, ""


class DMRGPageParser:
    """Parser for the DMRG cond-mat page to extract arXiv links."""
    
    def __init__(self, session):
        """
        Initialize DMRG page parser.
        
        Args:
            session (requests.Session): HTTP session for requests
        """
        self.session = session
    
    def fetch_page(self, url, timeout=30):
        """
        Fetch web page content.
        
        Args:
            url (str): URL to fetch
            timeout (int): Request timeout in seconds
            
        Returns:
            BeautifulSoup or None: Parsed HTML content or None on error
        """
        try:
            logging.info(f"Fetching page: {url}")
            r = self.session.get(url, timeout=timeout)
            r.raise_for_status()
            logging.info(f"Successfully fetched page, size: {len(r.content)} bytes")
            return BeautifulSoup(r.content, "html.parser")
        except Exception as e:
            logging.error("Failed to fetch page %s: %s", url, e)
            return None
    
    def parse_entries(self, soup):
        """
        Parse all arXiv links from DMRG page.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            list: List of entry dictionaries with id and link
        """
        entries = []
        b_tags = soup.find_all("b")
        logging.info(f"Found {len(b_tags)} bold tags to check")
        
        for i, b_tag in enumerate(b_tags):
            a_tag = b_tag.find("a", href=True)
            if not a_tag or not a_tag["href"].startswith("http://arxiv.org/abs/"):
                continue
            
            href = a_tag["href"]
            entry_id = generate_entry_id(href)
            entries.append({"id": entry_id, "link": href})
            
            if (i + 1) % 10 == 0:  # Log progress every 10 entries
                logging.info(f"Processed {i + 1} bold tags, found {len(entries)} arXiv links so far")
        
        logging.info(f"Total arXiv entries found: {len(entries)}")
        return entries
