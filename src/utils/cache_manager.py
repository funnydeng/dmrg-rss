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
        Initialize cache manager with intelligent year detection.
        
        Args:
            cache_path (str): Path to the main cache JSON file
                - "docs/entries25.json" → current data (dual files: entries25.json + entries25.json)
                - "docs/entries24.json" → year-specific data (keep as entries24.json)
        """
        self.cache_dir = os.path.dirname(cache_path) if os.path.dirname(cache_path) else "."
        cache_filename = os.path.basename(cache_path)
        
        # Detect if this is a year-specific cache (entries{YY}.json)
        # Pattern: entriesYYYY.json or entriesYY.json where YY/YYYY are digits
        self.is_year_specific = False
        self.target_year = None
        self.current_year_2digit = str(datetime.now().year)[-2:]
        
        if cache_filename.startswith("entries") and cache_filename.endswith(".json"):
            # Extract the middle part (e.g., "24" from "entries24.json")
            middle_part = cache_filename[7:-5]  # Remove "entries" and ".json"
            if middle_part.isdigit():
                # It's a year cache file
                year_2digit = middle_part[-2:] if len(middle_part) >= 2 else middle_part
                
                # Check if this is a different year (year-specific mode)
                if year_2digit != self.current_year_2digit:
                    self.is_year_specific = True
                    self.target_year = year_2digit
                    self.cache_path = cache_path  # Use the specified year-specific file
                else:
                    # Current year, use as latest
                    self.cache_path = cache_path
                    self.yearly_cache_path = cache_path  # Same file
            else:
                # Invalid format, use current year
                self.cache_path = os.path.join(self.cache_dir, f"entries{self.current_year_2digit}.json")
                self.yearly_cache_path = self.cache_path
        else:
            # Default to current year cache
            self.cache_path = os.path.join(self.cache_dir, f"entries{self.current_year_2digit}.json")
            self.yearly_cache_path = self.cache_path
    
    def load_cache(self):
        """
        Load entries from cache file with intelligent fallback.
        
        Year-specific mode (entries24.json when current year is 25):
        - Try: entries24.json (year-specific)
        - Fallback: entries25.json (current year)
        
        Latest mode (entries25.json and current year is 25):
        - Try: entries25.json (current)
        - No fallback needed (same file)
        
        Returns:
            dict: Dictionary of cached entries with metadata
        """
        if self.is_year_specific:
            # Year-specific mode: try year file first, then current year as fallback
            if os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    entries = cache_data.get('entries', {})
                    last_updated = cache_data.get('last_updated', 'unknown')
                    
                    logging.info(f"Loaded {len(entries)} entries from year-specific cache: {self.cache_path} (last updated: {last_updated})")
                    return entries
                    
                except Exception as e:
                    logging.error(f"Error loading year-specific cache file: {e}")
            
            # Fallback: try current year cache
            current_year_file = os.path.join(self.cache_dir, f"entries{self.current_year_2digit}.json")
            if os.path.exists(current_year_file):
                try:
                    with open(current_year_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    entries = cache_data.get('entries', {})
                    last_updated = cache_data.get('last_updated', 'unknown')
                    
                    logging.info(f"Loaded {len(entries)} entries from current year cache (fallback): {current_year_file} (last updated: {last_updated})")
                    return entries
                    
                except Exception as e:
                    logging.error(f"Error loading current year cache: {e}")
        else:
            # Latest mode: try the specified file
            if os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    entries = cache_data.get('entries', {})
                    last_updated = cache_data.get('last_updated', 'unknown')
                    
                    logging.info(f"Loaded {len(entries)} entries from cache (last updated: {last_updated})")
                    return entries
                    
                except Exception as e:
                    logging.error(f"Error loading cache file: {e}")
        
        # No cache files found
        logging.info(f"No cache files found at {self.cache_path}")
        return {}
    
    def save_cache(self, entries_dict):
        """
        Save entries to cache files based on detection mode.
        
        Year-specific mode (entries24.json when current year is 25):
        - Primary: entries24.json (the year-specific file)
        - No backup (keep separate from current year)
        
        Latest mode (entries25.json and current year is 25):
        - Primary: entries25.json (current year)
        - No separate backup (same file)
        
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
            
            # Save to the cache path (year-specific or current year)
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"Saved {len(entries_dict)} entries to cache: {self.cache_path}")
            
        except Exception as e:
            logging.error(f"Error saving cache files: {e}")
            
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
