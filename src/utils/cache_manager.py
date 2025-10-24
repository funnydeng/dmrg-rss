#!/usr/bin/env python3
"""
Cache management module for storing and retrieving processed entries.
Supports dual-file caching: entries_latest.json (current) and entries_YYYY.json (yearly backup).
"""
import os
import json
import logging
from datetime import datetime, timezone


class CacheManager:
    """Manages JSON cache for entry data persistence with versioning support."""
    
    def __init__(self, cache_path):
        """
        Initialize cache manager.
        
        Args:
            cache_path (str): Path to the main cache JSON file (entries_latest.json)
        """
        # Main cache file (always entries_latest.json)
        self.cache_dir = os.path.dirname(cache_path) if os.path.dirname(cache_path) else "."
        self.cache_path = os.path.join(self.cache_dir, "entries_latest.json")
        
        # Yearly backup cache file (entries_YYYY.json)
        current_year = datetime.now().year
        self.yearly_cache_path = os.path.join(self.cache_dir, f"entries_{current_year}.json")
    
    def load_cache(self):
        """
        Load entries from latest cache file.
        Priority: entries_latest.json > entries_YYYY.json
        
        Returns:
            dict: Dictionary of cached entries with metadata
        """
        # Try loading from entries_latest.json first
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                entries = cache_data.get('entries', {})
                last_updated = cache_data.get('last_updated', 'unknown')
                
                logging.info(f"Loaded {len(entries)} entries from latest cache (last updated: {last_updated})")
                return entries
                
            except Exception as e:
                logging.error(f"Error loading latest cache file: {e}")
        
        # Fallback: Try loading from yearly cache if latest doesn't exist
        if os.path.exists(self.yearly_cache_path):
            try:
                with open(self.yearly_cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                entries = cache_data.get('entries', {})
                last_updated = cache_data.get('last_updated', 'unknown')
                
                logging.info(f"Loaded {len(entries)} entries from yearly cache: {self.yearly_cache_path} (last updated: {last_updated})")
                return entries
                
            except Exception as e:
                logging.error(f"Error loading yearly cache file: {e}")
        
        # No cache files found
        logging.info(f"No cache files found. Latest path: {self.cache_path}, Yearly path: {self.yearly_cache_path}")
        return {}
    
    def save_cache(self, entries_dict):
        """
        Save entries to both latest and yearly cache files.
        
        - entries_latest.json: Current working cache (always updated)
        - entries_YYYY.json: Yearly backup (updated yearly)
        
        Args:
            entries_dict (dict): Dictionary of entries to cache
        """
        try:
            # Create cache data structure
            cache_data = {
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'entries': entries_dict
            }
            
            # Ensure directory exists
            os.makedirs(self.cache_dir, exist_ok=True)
            
            # Save to entries_latest.json (always)
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"Saved {len(entries_dict)} entries to latest cache: {self.cache_path}")
            
            # Save to yearly backup (entries_YYYY.json)
            with open(self.yearly_cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"Saved {len(entries_dict)} entries to yearly backup: {self.yearly_cache_path}")
            
        except Exception as e:
            logging.error(f"Error saving cache files: {e}")
    
    def get_cache_stats(self):
        """
        Get statistics about both cache files (latest and yearly).
        
        Returns:
            dict: Cache statistics for both files
        """
        stats = {
            "latest": self._get_cache_file_stats(self.cache_path),
            "yearly": self._get_cache_file_stats(self.yearly_cache_path)
        }
        return stats
    
    def _get_cache_file_stats(self, file_path):
        """
        Get statistics for a single cache file.
        
        Args:
            file_path (str): Path to the cache file
            
        Returns:
            dict: Cache file statistics
        """
        try:
            if not os.path.exists(file_path):
                return {"exists": False}
            
            file_size = os.path.getsize(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            return {
                "exists": True,
                "path": file_path,
                "file_size": file_size,
                "entry_count": len(cache_data.get('entries', {})),
                "last_updated": cache_data.get('last_updated', 'unknown')
            }
            
        except Exception as e:
            logging.error(f"Error getting cache stats for {file_path}: {e}")
            return {"exists": True, "error": str(e)}
