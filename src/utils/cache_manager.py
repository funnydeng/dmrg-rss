#!/usr/bin/env python3
"""
Cache management module for storing and retrieving processed entries.

Each year has its own cache file (docs/entries{YY}.json). A cache file is
only ever read from and written to for its own year, so a run can never mix
papers from different years into the same archive.
"""
import os
import re
import json
import logging
from datetime import datetime, timezone


def list_cache_years(cache_dir="docs"):
    """Return the 2-digit years that have an entries{YY}.json cache, sorted ascending."""
    years = []
    if os.path.isdir(cache_dir):
        for name in os.listdir(cache_dir):
            match = re.fullmatch(r"entries(\d{2})\.json", name)
            if match:
                years.append(match.group(1))
    return sorted(years)


class CacheManager:
    """Manages the JSON cache for one year's entries."""

    def __init__(self, cache_path):
        """
        Args:
            cache_path (str): Path to the cache JSON file, e.g. "docs/entries26.json"
        """
        self.cache_path = cache_path
        self.cache_dir = os.path.dirname(cache_path) or "."

    def load_cache(self):
        """
        Load entries from the cache file.

        Returns:
            dict: {entry_id: entry_dict}; empty if the file does not exist.

        Raises:
            RuntimeError: if the file exists but cannot be read. Continuing with
                an empty cache would overwrite the archive on the next save.
        """
        if not os.path.exists(self.cache_path):
            logging.info(f"No cache file found at {self.cache_path}")
            return {}

        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Error loading cache file {self.cache_path}: {e}") from e

        entries = cache_data.get('entries', {})
        last_updated = cache_data.get('last_updated', 'unknown')
        logging.info(f"Loaded {len(entries)} entries from cache: {self.cache_path} (last updated: {last_updated})")
        return entries

    def save_cache(self, entries_dict):
        """
        Save entries to the cache file.

        Args:
            entries_dict (dict): Dictionary of entries to cache
        """
        cache_data = {
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'entries': entries_dict
        }
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        logging.info(f"Saved {len(entries_dict)} entries to cache: {self.cache_path}")

    def get_cache_stats(self):
        """
        Get statistics about the cache file.

        Returns:
            dict: Cache file statistics
        """
        if not os.path.exists(self.cache_path):
            return {"exists": False}
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            return {
                "exists": True,
                "path": self.cache_path,
                "file_size": os.path.getsize(self.cache_path),
                "entry_count": len(cache_data.get('entries', {})),
                "last_updated": cache_data.get('last_updated', 'unknown')
            }
        except Exception as e:
            logging.error(f"Error getting cache stats for {self.cache_path}: {e}")
            return {"exists": True, "error": str(e)}
