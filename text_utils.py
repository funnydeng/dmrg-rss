#!/usr/bin/env python3
"""
Utility functions for text processing and date handling.
"""
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def clean_text(text):
    """
    Clean and normalize text by removing extra whitespace.
    
    Args:
        text (str): Raw text to clean
        
    Returns:
        str: Cleaned text with normalized whitespace
    """
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.strip().replace("\n", " "))


def format_date_for_rss(date_str):
    """
    Convert date string to RFC-2822 format for RSS.
    
    Args:
        date_str (str): Date string in various formats
        
    Returns:
        str or None: RFC-2822 formatted date string, or None if invalid
    """
    if not date_str:
        return None
    
    try:
        # Handle ISO format (arXiv format)
        if 'T' in date_str and date_str.endswith('Z'):
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%a, %d %b %Y %H:%M:%S %z")
        
        # Handle RFC-2822 format (already correct)
        if date_str.count(',') == 1:
            # Try to parse as existing RFC-2822
            try:
                dt = parsedate_to_datetime(date_str)
                return dt.strftime("%a, %d %b %Y %H:%M:%S %z")
            except:
                pass
        
        # Fallback to current time if can't parse
        current_time = datetime.now(timezone.utc)
        return current_time.strftime("%a, %d %b %Y %H:%M:%S %z")
        
    except Exception:
        # Return None for any parsing errors
        return None


def generate_entry_id(url):
    """
    Generate a unique ID for an entry based on its URL.
    
    Args:
        url (str): The URL to generate ID from
        
    Returns:
        str: MD5 hash of the URL
    """
    import hashlib
    return hashlib.md5(url.encode()).hexdigest()


def is_entry_complete(entry):
    """
    Check if an entry has all required fields populated.
    
    Args:
        entry (dict): Entry dictionary to validate
        
    Returns:
        bool: True if entry is complete, False otherwise
    """
    required_fields = ["title", "abstract", "authors", "pubdate"]
    return all(entry.get(field) and entry.get(field).strip() for field in required_fields)