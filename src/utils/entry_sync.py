#!/usr/bin/env python3
"""
Entry synchronization module for managing data consistency between sources.
"""
import time
import logging

from .text_utils import is_entry_complete
from .arxiv_processor import arxiv_id_from_url
from ..config import ARXIV_DELAY_SECONDS


class EntrySync:
    """Manages synchronization of entries from multiple sources."""
    
    def __init__(self, arxiv_processor, max_entries=None):
        """
        Initialize entry synchronizer.
        
        Args:
            arxiv_processor (ArXivProcessor): Processor for fetching arXiv data
            max_entries (int, optional): Maximum number of entries to process (None = all)
        """
        self.arxiv_processor = arxiv_processor
        self.max_entries = max_entries
    
    def sync_entries(self, dmrg_entries, existing_entries, cached_entries):
        """
        Sync entries: compare DMRG page with JSON cache, fetch missing/incomplete from arXiv.
        
        Args:
            dmrg_entries (list): Fresh entries from DMRG page (basic info only)
            existing_entries (dict): Entries from existing RSS (ignored in new logic)
            cached_entries (dict): Entries from JSON cache file (source of truth for complete data)
            
        Returns:
            tuple: (all_entries, updated_cache) - ordered by DMRG page
        """
        # Apply max_entries limit if configured
        if self.max_entries and len(dmrg_entries) > self.max_entries:
            original_count = len(dmrg_entries)
            dmrg_entries = dmrg_entries[:self.max_entries]
            logging.info(f"LIMITED entries from {original_count} to {self.max_entries} (MAX_ENTRIES={self.max_entries})")
        
        # The source page occasionally lists a paper twice
        dmrg_entries = list({e["id"]: e for e in reversed(dmrg_entries)}.values())[::-1]

        logging.info(f"DMRG page entries: {len(dmrg_entries)}")
        logging.info(f"JSON cache entries: {len(cached_entries)}")

        # Find entries that need to be fetched from arXiv
        new_or_incomplete = []
        complete_existing = []
        
        for dmrg_entry in dmrg_entries:
            eid = dmrg_entry["id"]
            
            if eid not in cached_entries:
                # Not in cache - completely new entry
                new_or_incomplete.append(dmrg_entry)
                logging.debug(f"New entry not in cache: {dmrg_entry['link']}")
            else:
                # In cache - check if complete
                cached_entry = cached_entries[eid]
                if is_entry_complete(cached_entry):
                    # Entry is complete in cache
                    complete_existing.append(cached_entry)
                    logging.debug(f"Complete cached entry: {cached_entry['link']}")
                else:
                    # Entry exists in cache but is incomplete - needs refetch
                    new_or_incomplete.append(dmrg_entry)
                    logging.info(f"Incomplete entry in cache, will refetch: {dmrg_entry['link']}")

        logging.info(f"Entries analysis: {len(complete_existing)} complete, {len(new_or_incomplete)} need fetching")
        
        if len(new_or_incomplete) == 0:
            logging.info("All entries are complete, no fetching needed")

        # Fetch details for new or incomplete entries: batched first, then
        # one-by-one for anything the batch query did not return
        batch = self.arxiv_processor.fetch_papers_batch([e["link"] for e in new_or_incomplete]) if new_or_incomplete else {}
        detailed_new_entries = []
        total_to_fetch = len(new_or_incomplete)

        for i, entry in enumerate(new_or_incomplete):
            details = batch.get(arxiv_id_from_url(entry["link"]))
            if details is None:
                logging.info(f"Fetching details individually [{i+1}/{total_to_fetch}]: {entry['link']}")
                details = self.arxiv_processor.fetch_paper_details(entry["link"])
                time.sleep(ARXIV_DELAY_SECONDS)
            title, abstract, pubdate, authors = details

            detailed_entry = {
                "id": entry["id"],
                "link": entry["link"],
                "title": title,
                "abstract": abstract,
                "pubdate": pubdate,
                "authors": authors
            }
            if not is_entry_complete(detailed_entry) and entry["id"] in cached_entries:
                # Keep whatever we already had rather than a blank record
                detailed_entry = {**cached_entries[entry["id"]], **{k: v for k, v in detailed_entry.items() if v}}
            if not is_entry_complete(detailed_entry):
                logging.warning(f"Could not fetch complete metadata for {entry['link']}; will retry next run")

            detailed_new_entries.append(detailed_entry)

        # Merge all entries: complete existing first, then new entries
        all_entries = complete_existing + detailed_new_entries

        # The cache is an append-only archive for its year: entries that have
        # dropped off the source page (or a temporarily truncated page) must not
        # erase already-archived papers.
        page_ids = {e["id"] for e in all_entries}
        retained = [v for k, v in cached_entries.items() if k not in page_ids]
        if retained and not self.max_entries:
            logging.info(f"Keeping {len(retained)} archived entries no longer listed on the source page")
            all_entries += retained

        # Create updated cache dictionary for saving
        updated_cache = {}
        for entry in all_entries:
            updated_cache[entry["id"]] = entry

        logging.info(f"Final sync result: {len(all_entries)} total entries")
        logging.info(f"- {len(complete_existing)} existing complete entries")
        logging.info(f"- {len(detailed_new_entries)} newly fetched/updated entries")
        
        return all_entries, updated_cache
