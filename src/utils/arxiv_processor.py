#!/usr/bin/env python3
"""
ArXiv data processor for fetching and parsing paper details.
"""
import re
import time
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from .text_utils import clean_text, generate_entry_id
from ..config import ARXIV_API_TIMEOUT, ARXIV_RETRY_COUNT, ARXIV_DELAY_SECONDS, ARXIV_BATCH_SIZE


ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_API_URL = "https://export.arxiv.org/api/query"


def arxiv_id_from_url(url):
    """Return the bare arXiv ID (no version suffix) from an abs URL or ID."""
    arxiv_id = url.rstrip("/").split("/abs/")[-1]
    return re.sub(r"v\d+$", "", arxiv_id)


class ArXivProcessor:
    """Handles fetching and processing of arXiv paper data."""
    
    def __init__(self, session):
        """
        Initialize ArXiv processor.
        
        Args:
            session (requests.Session): HTTP session for requests
        """
        self.session = session

    def _query(self, params):
        """GET the arXiv API, backing off on rate limiting (429/503)."""
        r = self.session.get(ARXIV_API_URL, params=params, timeout=ARXIV_API_TIMEOUT)
        if r.status_code in (429, 503):
            raise requests.HTTPError(f"arXiv API returned {r.status_code} (rate limited)", response=r)
        r.raise_for_status()
        return ET.fromstring(r.content)

    @staticmethod
    def _parse_entry(entry):
        """Parse an Atom <entry> into (title, abstract, pubdate, authors)."""
        title_el = entry.find(f"{ATOM_NS}title")
        title = clean_text(title_el.text if title_el is not None else "")

        # Use itertext() so LaTeX formulas like $1<c<2$ survive intact
        abstract_el = entry.find(f"{ATOM_NS}summary")
        abstract = clean_text(''.join(abstract_el.itertext())) if abstract_el is not None else ""

        published_el = entry.find(f"{ATOM_NS}published")
        pubdate = None
        if published_el is not None and published_el.text:
            try:
                # Convert to RFC-2822 format for RSS
                dt = datetime.strptime(published_el.text, "%Y-%m-%dT%H:%M:%SZ")
                pubdate = dt.replace(tzinfo=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
            except Exception as e:
                logging.warning(f"Failed to parse pubdate {published_el.text}: {e}")

        authors = ", ".join(
            clean_text(a.findtext(f"{ATOM_NS}name", ""))
            for a in entry.findall(f"{ATOM_NS}author")
        )
        return title, abstract, pubdate, authors

    def fetch_papers_batch(self, arxiv_urls, batch_size=ARXIV_BATCH_SIZE, retry_count=ARXIV_RETRY_COUNT):
        """
        Fetch details for many papers using few API calls (id_list batching).

        Args:
            arxiv_urls (list): arXiv abs URLs

        Returns:
            dict: {arxiv_id (no version): (title, abstract, pubdate, authors)}
                  Papers that could not be fetched are absent.
        """
        results = {}
        ids = list(dict.fromkeys(arxiv_id_from_url(u) for u in arxiv_urls))
        for start in range(0, len(ids), batch_size):
            chunk = ids[start:start + batch_size]
            params = {"id_list": ",".join(chunk), "max_results": len(chunk)}
            for attempt in range(retry_count):
                try:
                    logging.info(f"Fetching arXiv batch {start // batch_size + 1} "
                                 f"({len(chunk)} ids, attempt {attempt + 1})")
                    root = self._query(params)
                    for entry in root.findall(f"{ATOM_NS}entry"):
                        entry_id = arxiv_id_from_url(entry.findtext(f"{ATOM_NS}id", ""))
                        details = self._parse_entry(entry)
                        # arXiv reports unknown IDs as an entry titled "Error"
                        if entry_id in chunk and details[0] and details[0] != "Error":
                            results[entry_id] = details
                    break
                except Exception as e:
                    wait = ARXIV_DELAY_SECONDS * (2 ** attempt)
                    logging.warning(f"arXiv batch request failed: {e}; retrying in {wait}s")
                    time.sleep(wait)
            if start + batch_size < len(ids):
                time.sleep(ARXIV_DELAY_SECONDS)
        logging.info(f"arXiv batch fetch: {len(results)}/{len(ids)} papers retrieved")
        return results

    def fetch_paper_details(self, arxiv_url, retry_count=ARXIV_RETRY_COUNT):
        """
        Fetch paper details from arXiv API with retry mechanism.
        
        Args:
            arxiv_url (str): URL to the arXiv paper
            retry_count (int): Number of retry attempts
            
        Returns:
            tuple: (title, abstract, pubdate, authors)
        """
        arxiv_id = arxiv_id_from_url(arxiv_url)
        for attempt in range(retry_count):
            try:
                logging.info(f"Fetching arXiv details (attempt {attempt + 1}): {arxiv_id}")
                root = self._query({"id_list": arxiv_id})
                entries = root.findall(f"{ATOM_NS}entry")
                if entries:
                    title, abstract, pubdate, authors = self._parse_entry(entries[0])
                    if title and title != "Error":
                        logging.info(f"Successfully fetched details for {arxiv_id}: '{title[:50]}...'")
                        return title, abstract, pubdate, authors
                logging.warning(f"No entry found for {arxiv_id}")
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed for {arxiv_url}: {e}")
            if attempt < retry_count - 1:
                time.sleep(ARXIV_DELAY_SECONDS * (2 ** attempt))
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
            
            # Log progress less frequently to reduce noise in logs (every 200 entries)
            if (i + 1) % 200 == 0:
                logging.info(f"Processed {i + 1} bold tags, found {len(entries)} arXiv links so far")
        
        logging.info(f"Total arXiv entries found: {len(entries)}")
        return entries
