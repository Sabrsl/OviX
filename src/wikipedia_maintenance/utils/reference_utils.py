"""
Utility functions for reference and source processing.

Provides:
    - check_link_status(url) - Check if a link is accessible
    - get_archive_url(url) - Get Wayback Machine archive URL
    - fetch_url_metadata(url) - Fetch URL metadata (title, site, date)
    - validate_isbn(isbn) - Validate ISBN format
    - find_duplicate_refs(content) - Find duplicate references
"""

from __future__ import annotations

import re
import logging
from typing import List, Optional, Dict, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def validate_isbn(isbn: str) -> bool:
    """
    Validate ISBN-10 or ISBN-13 format.
    
    Args:
        isbn: ISBN string (with or without hyphens).
        
    Returns:
        True if valid ISBN format, False otherwise.
    """
    # Remove hyphens and spaces
    isbn_clean = re.sub(r'[\s-]', '', isbn.upper())
    
    # Check length
    if len(isbn_clean) == 10:
        # ISBN-10
        if not re.match(r'^\d{9}[\dX]$', isbn_clean):
            return False
        
        # Calculate checksum
        total = 0
        for i, char in enumerate(isbn_clean[:9]):
            total += (i + 1) * int(char)
        
        check_char = isbn_clean[9]
        check_value = 10 if check_char == 'X' else int(check_char)
        
        return total % 11 == check_value
    
    elif len(isbn_clean) == 13:
        # ISBN-13
        if not re.match(r'^\d{13}$', isbn_clean):
            return False
        
        # Calculate checksum
        total = 0
        for i, char in enumerate(isbn_clean[:12]):
            digit = int(char)
            total += digit if i % 2 == 0 else digit * 3
        
        check_digit = int(isbn_clean[12])
        return (10 - (total % 10)) % 10 == check_digit
    
    return False


def check_link_status(url: str, session=None, timeout: float = 5.0) -> bool:
    """
    Check if a URL is accessible (returns True if OK, False if 404/error).
    
    Args:
        url: URL to check.
        session: Optional requests.Session.
        timeout: Request timeout in seconds.
        
    Returns:
        True if accessible, False otherwise.
    """
    if not session:
        try:
            import requests
            session = requests.Session()
        except ImportError:
            logger.warning("requests not installed; cannot check link status")
            return True  # Assume OK
    
    try:
        response = session.head(url, timeout=timeout, allow_redirects=True)
        return response.status_code < 400
    except Exception as e:
        logger.debug(f"Error checking link {url}: {e}")
        return False


def get_archive_url(url: str, session=None, timeout: float = 5.0) -> Optional[str]:
    """
    Get Wayback Machine archive URL for a given URL.
    
    Args:
        url: Original URL.
        session: Optional requests.Session.
        timeout: Request timeout in seconds.
        
    Returns:
        Archive URL if available, None otherwise.
    """
    if not session:
        try:
            import requests
            session = requests.Session()
        except ImportError:
            logger.warning("requests not installed; cannot get archive URL")
            return None
    
    try:
        # Wayback Machine CDX API
        cdx_url = f"https://web.archive.org/cdx/search/cdx?url={url}&output=json&fl=timestamp,original&limit=1"
        response = session.get(cdx_url, timeout=timeout)
        response.raise_for_status()
        
        data = response.json()
        if len(data) > 1:  # First row is header
            timestamp = data[1][0]
            return f"https://web.archive.org/web/{timestamp}/{url}"
        
        return None
        
    except Exception as e:
        logger.warning(f"Error getting archive URL for {url}: {e}")
        return None


def fetch_url_metadata(url: str, session=None, timeout: float = 10.0) -> Optional[Dict[str, str]]:
    """
    Fetch metadata from a URL (title, site, date).
    
    Args:
        url: URL to fetch metadata from.
        session: Optional requests.Session.
        timeout: Request timeout in seconds.
        
    Returns:
        Dictionary with 'title', 'site', 'date' keys, or None if error.
    """
    if not session:
        try:
            import requests
            from bs4 import BeautifulSoup
            session = requests.Session()
        except ImportError:
            logger.warning("requests or beautifulsoup4 not installed; cannot fetch URL metadata")
            return None
    
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title = None
        if soup.title:
            title = soup.title.get_text().strip()
        
        # Extract site name from URL
        parsed = urlparse(url)
        site = parsed.netloc
        
        # Try to get date from meta tags
        date = None
        date_meta = soup.find('meta', property='article:published_time')
        if date_meta:
            date = date_meta.get('content')
        else:
            date_meta = soup.find('meta', attrs={'name': 'date'})
            if date_meta:
                date = date_meta.get('content')
        
        return {
            'title': title,
            'site': site,
            'date': date,
        }
        
    except Exception as e:
        logger.warning(f"Error fetching metadata for {url}: {e}")
        return None


def find_duplicate_refs(content: str) -> List[Tuple[str, List[int]]]:
    """
    Find duplicate references in content.
    
    Args:
        content: Wikicode content.
        
    Returns:
        List of tuples (normalized_ref_content, positions) for duplicates.
    """
    ref_pattern = re.compile(r'<ref[^>]*>(.*?)</ref>', re.IGNORECASE | re.DOTALL)
    
    ref_contents: Dict[str, List[int]] = {}
    
    for match in ref_pattern.finditer(content):
        ref_content = match.group(1).strip()
        # Normalize for comparison
        normalized = re.sub(r'\s+', ' ', ref_content)
        
        if normalized not in ref_contents:
            ref_contents[normalized] = []
        ref_contents[normalized].append(match.start())
    
    # Return only duplicates (appearing more than once)
    duplicates = [
        (normalized, positions)
        for normalized, positions in ref_contents.items()
        if len(positions) > 1
    ]
    
    return duplicates


def normalize_isbn(isbn: str) -> str:
    """
    Normalize ISBN format (remove hyphens, convert to uppercase).
    
    Args:
        isbn: ISBN string.
        
    Returns:
        Normalized ISBN string.
    """
    return re.sub(r'[\s-]', '', isbn.upper())


def extract_urls_from_refs(content: str) -> List[str]:
    """
    Extract all URLs from <ref> tags.
    
    Args:
        content: Wikicode content.
        
    Returns:
        List of URLs found in references.
    """
    ref_pattern = re.compile(r'<ref[^>]*>(.*?)</ref>', re.IGNORECASE | re.DOTALL)
    url_pattern = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+', re.IGNORECASE)
    
    urls = []
    for match in ref_pattern.finditer(content):
        ref_content = match.group(1)
        for url_match in url_pattern.finditer(ref_content):
            urls.append(url_match.group())
    
    return urls


def is_social_media_url(url: str) -> bool:
    """
    Check if a URL is from a social media platform.
    
    Args:
        url: URL to check.
        
    Returns:
        True if social media URL, False otherwise.
    """
    social_domains = {
        'twitter.com', 'x.com', 'facebook.com', 'instagram.com',
        'tiktok.com', 'linkedin.com', 'youtube.com', 'threads.net',
        'vk.com', 'telegram.org', 'whatsapp.com'
    }
    
    parsed = urlparse(url)
    return parsed.netloc.lower() in social_domains


def is_wikipedia_url(url: str) -> bool:
    """
    Check if a URL is from Wikipedia.
    
    Args:
        url: URL to check.
        
    Returns:
        True if Wikipedia URL, False otherwise.
    """
    parsed = urlparse(url)
    return parsed.netloc.endswith('.wikipedia.org')


def extract_language_from_wikipedia_url(url: str) -> Optional[str]:
    """
    Extract language code from a Wikipedia URL.
    
    Args:
        url: Wikipedia URL.
        
    Returns:
        Language code (e.g., 'fr', 'en') or None.
    """
    parsed = urlparse(url)
    if parsed.netloc.endswith('.wikipedia.org'):
        # Extract language from subdomain
        parts = parsed.netloc.split('.')
        if len(parts) >= 2:
            return parts[0]
    return None
