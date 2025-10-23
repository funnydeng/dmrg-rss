#!/usr/bin/env python3
"""
Utility functions for text processing and date handling.
"""
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def latex_to_unicode(text):
    r"""
    Convert common LaTeX accent commands to Unicode characters.
    
    Handles:
    - \v{x} -> ǩ, ř, š, ť, ž, etc. (háček/caron)
    - \'{x} -> á, é, í, ó, ú, etc. (acute)
    - \"{x} -> ä, ë, ï, ö, ü, etc. (diaeresis)
    - \^{x} -> â, ê, î, ô, û, etc. (circumflex)
    - \~{x} -> ã, ñ, õ, etc. (tilde)
    - \c{x} -> ç (cedilla)
    - \u{x} -> ă, ĕ, ĭ, ŏ, ŭ (breve)
    - \H{x} -> ő, ű (double acute)
    - \k{x} -> ą, ę (ogonek)
    
    Args:
        text (str): Text potentially containing LaTeX accent commands
        
    Returns:
        str: Text with LaTeX accents converted to Unicode
    """
    if not text:
        return text
    
    # Mapping of LaTeX accent commands to Unicode equivalents
    # Note: JSON stores single backslash as \, so \'{e} appears as \'  {e}
    # We need patterns that match both \v{r} and v{r} forms
    latex_accents = {
        # Háček/Caron: \v{x}
        r'\\?v\{c\}': 'č', r'\\?v\{C\}': 'Č',
        r'\\?v\{d\}': 'ď', r'\\?v\{D\}': 'Ď',
        r'\\?v\{e\}': 'ě', r'\\?v\{E\}': 'Ě',
        r'\\?v\{l\}': 'ľ', r'\\?v\{L\}': 'Ľ',
        r'\\?v\{n\}': 'ň', r'\\?v\{N\}': 'Ň',
        r'\\?v\{r\}': 'ř', r'\\?v\{R\}': 'Ř',
        r'\\?v\{s\}': 'š', r'\\?v\{S\}': 'Š',
        r'\\?v\{t\}': 'ť', r'\\?v\{T\}': 'Ť',
        r'\\?v\{z\}': 'ž', r'\\?v\{Z\}': 'Ž',
        
        # Acute: \'{x} - match both \' and just '
        r"\\'a": 'á', r"\\'A": 'Á',
        r"\\'e": 'é', r"\\'E": 'É',
        r"\\'i": 'í', r"\\'I": 'Í',
        r"\\'o": 'ó', r"\\'O": 'Ó',
        r"\\'u": 'ú', r"\\'U": 'Ú',
        r"\\'y": 'ý', r"\\'Y": 'Ý',
        r"\\'c": 'ć', r"\\'C": 'Ć',
        r"\\'n": 'ń', r"\\'N": 'Ń',
        r"\\'s": 'ś', r"\\'S": 'Ś',
        r"\\'z": 'ź', r"\\'Z": 'Ź',
        
        # Diaeresis: \"{x}
        r'\\"a': 'ä', r'\\"A': 'Ä',
        r'\\"e': 'ë', r'\\"E': 'Ë',
        r'\\"i': 'ï', r'\\"I': 'Ï',
        r'\\"o': 'ö', r'\\"O': 'Ö',
        r'\\"u': 'ü', r'\\"U': 'Ü',
        r'\\"y': 'ÿ',
        
        # Circumflex: \^{x}
        r'\\?\^a': 'â', r'\\?\^A': 'Â',
        r'\\?\^e': 'ê', r'\\?\^E': 'Ê',
        r'\\?\^i': 'î', r'\\?\^I': 'Î',
        r'\\?\^o': 'ô', r'\\?\^O': 'Ô',
        r'\\?\^u': 'û', r'\\?\^U': 'Û',
        
        # Tilde: \~{x}
        r'\\?~a': 'ã', r'\\?~A': 'Ã',
        r'\\?~n': 'ñ', r'\\?~N': 'Ñ',
        r'\\?~o': 'õ', r'\\?~O': 'Õ',
        
        # Cedilla: \c{x}
        r'\\?c\{c\}': 'ç', r'\\?c\{C\}': 'Ç',
        
        # Breve: \u{x}
        r'\\?u\{a\}': 'ă', r'\\?u\{A\}': 'Ă',
        r'\\?u\{e\}': 'ĕ', r'\\?u\{E\}': 'Ĕ',
        r'\\?u\{i\}': 'ĭ', r'\\?u\{I\}': 'Ĭ',
        r'\\?u\{o\}': 'ŏ', r'\\?u\{O\}': 'Ŏ',
        r'\\?u\{u\}': 'ŭ', r'\\?u\{U\}': 'Ŭ',
        
        # Double acute: \H{x}
        r'\\?H\{o\}': 'ő', r'\\?H\{O\}': 'Ő',
        r'\\?H\{u\}': 'ű', r'\\?H\{U\}': 'Ű',
        
        # Ogonek: \k{x}
        r'\\?k\{a\}': 'ą', r'\\?k\{A\}': 'Ą',
        r'\\?k\{e\}': 'ę', r'\\?k\{E\}': 'Ę',
    }
    
    result = text
    for latex_cmd, unicode_char in latex_accents.items():
        result = re.sub(latex_cmd, unicode_char, result)
    
    return result


def clean_text(text):
    """
    Clean and normalize text by removing extra whitespace and converting LaTeX to Unicode.
    
    Args:
        text (str): Raw text to clean
        
    Returns:
        str: Cleaned text with normalized whitespace and LaTeX accents converted
    """
    if not text:
        return ""
    # First convert LaTeX accents to Unicode
    text = latex_to_unicode(text)
    # Then normalize whitespace
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