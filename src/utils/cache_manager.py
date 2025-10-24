#!/usr/bin/env python3
"""
Cache management module for storing and retrieving processed entries.
"""
import os
import json
import logging
from datetime import datetime, timezone


class CacheManager:
    """Manages JSON cache for entry data persistence."""
    
    def __init__(self, cache_path):
        """
        Initialize cache manager.
        
        Args:
            cache_path (str): Path to the cache JSON file
        """
        self.cache_path = cache_path
    
    def load_cache(self):
        """
        Load entries from cache file.
        
        Returns:
            dict: Dictionary of cached entries with metadata
        """
        if not os.path.exists(self.cache_path):
            logging.info(f"No cache file found at {self.cache_path}")
            return {}
        
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            entries = cache_data.get('entries', {})
            last_updated = cache_data.get('last_updated', 'unknown')
            
            logging.info(f"Loaded {len(entries)} entries from cache (last updated: {last_updated})")
            return entries
            
        except Exception as e:
            logging.error(f"Error loading cache file: {e}")
            return {}
    
    def save_cache(self, entries_dict):
        """
        Save entries to cache file.
        
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
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            
            # Write cache file
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"Saved {len(entries_dict)} entries to cache: {self.cache_path}")
            
        except Exception as e:
            logging.error(f"Error saving cache file: {e}")
    
    def get_cache_stats(self):
        """
        Get statistics about the cache file.
        
        Returns:
            dict: Cache statistics including size and entry count
        """
        try:
            if not os.path.exists(self.cache_path):
                return {"exists": False}
            
            file_size = os.path.getsize(self.cache_path)
            
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            return {
                "exists": True,
                "file_size": file_size,
                "entry_count": len(cache_data.get('entries', {})),
                "last_updated": cache_data.get('last_updated', 'unknown')
            }
            
        except Exception as e:
            logging.error(f"Error getting cache stats: {e}")
            return {"exists": True, "error": str(e)}
