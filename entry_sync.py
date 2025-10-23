#!/usr/bin/env python3
"""
Entry synchronization module for managing data consistency between sources.
"""
import time
import logging

from text_utils import is_entry_complete


class EntrySync:
    """Manages synchronization of entries from multiple sources."""
    
    def __init__(self, arxiv_processor):
        """
        Initialize entry synchronizer.
        
        Args:
            arxiv_processor (ArXivProcessor): Processor for fetching arXiv data
        """
        self.arxiv_processor = arxiv_processor
    
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

        # Fetch detailed information for new or incomplete entries
        detailed_new_entries = []
        total_to_fetch = len(new_or_incomplete)
        
        for i, entry in enumerate(new_or_incomplete):
            progress = f"{i+1}/{total_to_fetch}"
            logging.info(f"Fetching details [{progress}]: {entry['link']}")
            
            title, abstract, pubdate, authors = self.arxiv_processor.fetch_paper_details(entry["link"])
            
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

        # Merge all entries: keep DMRG page order, complete existing first, then new entries
        all_entries = complete_existing + detailed_new_entries
        
        # Create updated cache dictionary for saving
        updated_cache = {}
        for entry in all_entries:
            updated_cache[entry["id"]] = entry
        
        logging.info(f"Final sync result: {len(all_entries)} total entries")
        logging.info(f"- {len(complete_existing)} existing complete entries")
        logging.info(f"- {len(detailed_new_entries)} newly fetched/updated entries")
        
        return all_entries, updated_cache