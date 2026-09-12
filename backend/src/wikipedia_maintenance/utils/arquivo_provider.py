"""
Arquivo.pt Archive Provider.

This module implements the Arquivo.pt archive provider for searching
archived web content and discovering candidate replacement URLs.

Arquivo.pt API documentation:
- Text Search API: https://arquivo.pt/textsearch
- Rate limit: 250 requests/60s per IP
- Supports URL search and full-text search
- Returns JSON with metadata including link to archived content
"""

import logging
import time
import requests
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from urllib.parse import quote

from .archive_provider import BaseArchiveProvider, ArchiveResult, ArchiveAvailability

logger = logging.getLogger(__name__)


class ArquivoAPIStatus(Enum):
    """Status of Arquivo.pt API."""
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass
class ArquivoSearchResult:
    """Result from Arquivo.pt search."""
    title: str
    url: str
    link_to_archive: str
    timestamp: str
    mime_type: str
    status_code: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'title': self.title,
            'url': self.url,
            'link_to_archive': self.link_to_archive,
            'timestamp': self.timestamp,
            'mime_type': self.mime_type,
            'status_code': self.status_code
        }


class ArquivoProvider(BaseArchiveProvider):
    """
    Arquivo.pt archive provider.
    
    Uses Arquivo.pt Text Search API to search for archived content
    and discover candidate replacement URLs.
    
    API endpoint: https://arquivo.pt/textsearch
    Rate limit: 250 requests/60s per IP
    """
    
    API_BASE_URL = "https://arquivo.pt/textsearch"
    DEFAULT_TIMEOUT = 10
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES):
        """
        Initialize Arquivo.pt provider.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        super().__init__()
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_request_time = 0
        self._request_count = 0
        self._rate_limit_window = 60  # 60 seconds
        self._rate_limit_max = 250  # 250 requests per 60s
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return "Arquivo.pt"
    
    def check_archive(self, url: str) -> ArchiveResult:
        """
        Check if URL is archived in Arquivo.pt.
        
        Args:
            url: URL to check
            
        Returns:
            ArchiveResult with availability status
        """
        try:
            # Search for URL in Arquivo.pt
            search_results = self._search_url(url)
            
            if search_results and len(search_results) > 0:
                # Get the most recent result
                most_recent = search_results[0]
                
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.AVAILABLE,
                    archive_url=most_recent.link_to_archive,
                    archive_date=most_recent.timestamp,
                    metadata={
                        'title': most_recent.title,
                        'mime_type': most_recent.mime_type,
                        'status_code': most_recent.status_code,
                        'total_results': len(search_results)
                    }
                )
            else:
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.NOT_AVAILABLE,
                    archive_url=None,
                    archive_date=None,
                    metadata={'reason': 'No archived versions found'}
                )
                
        except Exception as e:
            self._logger.error(f"Error checking archive for {url}: {e}")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.ERROR,
                archive_url=None,
                archive_date=None,
                metadata={'error': str(e)}
            )
    
    def get_content_snapshot(self, url: str) -> Optional[str]:
        """
        Get content snapshot from Arquivo.pt.
        
        Args:
            url: URL to get snapshot for
            
        Returns:
            HTML content or None if not available
        """
        try:
            # First, get the archive URL
            search_results = self._search_url(url)
            
            if not search_results:
                return None
            
            # Get the most recent archive URL
            archive_url = search_results[0].link_to_archive
            
            # Fetch the archived content
            response = requests.get(archive_url, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.text
            else:
                self._logger.warning(f"Failed to fetch archive content: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self._logger.error(f"Error getting content snapshot: {e}")
            return None
    
    def search_by_title(self, title: str, domain: Optional[str] = None, max_results: int = 10) -> List[ArquivoSearchResult]:
        """
        Search archived content by title.
        
        Args:
            title: Title to search for
            domain: Optional domain filter
            max_results: Maximum number of results
            
        Returns:
            List of ArquivoSearchResult
        """
        try:
            # Build search query
            query = title
            if domain:
                query = f"site:{domain} {title}"
            
            results = self._search_text(query, max_results=max_results)
            return results
            
        except Exception as e:
            self._logger.error(f"Error searching by title: {e}")
            return []
    
    def search_by_url(self, url: str, max_results: int = 10) -> List[ArquivoSearchResult]:
        """
        Search archived content by URL.
        
        Args:
            url: URL to search for
            max_results: Maximum number of results
            
        Returns:
            List of ArquivoSearchResult
        """
        return self._search_url(url, max_results=max_results)
    
    def _search_url(self, url: str, max_results: int = 10) -> List[ArquivoSearchResult]:
        """
        Search for URL in Arquivo.pt.
        
        Args:
            url: URL to search for
            max_results: Maximum number of results
            
        Returns:
            List of ArquivoSearchResult
        """
        try:
            # Apply rate limiting
            self._apply_rate_limit()
            
            # Build query for exact URL search
            query = f'linkTo:"{url}"'
            
            params = {
                'q': query,
                'maxItems': max_results,
                'fields': 'title,linkTo,linkToArchive,timestamp,mimeType,statusCode'
            }
            
            response = self._make_request(params)
            
            if response:
                # Handle both dictionary with 'responseItems' key and direct list response
                if isinstance(response, dict) and 'responseItems' in response:
                    return self._parse_search_results(response['responseItems'])
                elif isinstance(response, list):
                    return self._parse_search_results(response)
            
            return []
            
        except Exception as e:
            self._logger.error(f"Error searching URL {url}: {e}")
            return []
    
    def _search_text(self, query: str, max_results: int = 10) -> List[ArquivoSearchResult]:
        """
        Search archived content by text query.
        
        Args:
            query: Text query
            max_results: Maximum number of results
            
        Returns:
            List of ArquivoSearchResult
        """
        try:
            # Apply rate limiting
            self._apply_rate_limit()
            
            params = {
                'q': query,
                'maxItems': max_results,
                'fields': 'title,linkTo,linkToArchive,timestamp,mimeType,statusCode'
            }
            
            response = self._make_request(params)
            
            if response:
                # Handle both dictionary with 'responseItems' key and direct list response
                if isinstance(response, dict) and 'responseItems' in response:
                    return self._parse_search_results(response['responseItems'])
                elif isinstance(response, list):
                    return self._parse_search_results(response)
            
            return []
            
        except Exception as e:
            self._logger.error(f"Error searching text '{query}': {e}")
            return []
    
    def _make_request(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Make request to Arquivo.pt API with retry logic.
        
        Args:
            params: Query parameters
            
        Returns:
            JSON response or None
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    self.API_BASE_URL,
                    params=params,
                    timeout=self.timeout,
                    headers={
                        'User-Agent': 'WikipediaMaintenanceTool/1.0 (Archive Research)'
                    }
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    self._logger.warning(f"Rate limited by Arquivo.pt (attempt {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.RETRY_DELAY * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        raise Exception("Rate limited after max retries")
                
                # Handle other errors
                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                
                return response.json()
                
            except requests.exceptions.Timeout:
                self._logger.warning(f"Timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                else:
                    raise Exception("Timeout after max retries")
                    
            except Exception as e:
                self._logger.error(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                else:
                    raise
        
        return None
    
    def _parse_search_results(self, items: List[Dict[str, Any]]) -> List[ArquivoSearchResult]:
        """
        Parse search results from Arquivo.pt API.
        
        Args:
            items: Response items from API
            
        Returns:
            List of ArquivoSearchResult
        """
        results = []
        
        # Ensure items is a list
        if not isinstance(items, list):
            self._logger.warning(f"Expected list of items, got {type(items).__name__}")
            return []
        
        for item in items:
            try:
                # Ensure item is a dictionary
                if not isinstance(item, dict):
                    self._logger.warning(f"Expected dict item, got {type(item).__name__}")
                    continue
                    
                result = ArquivoSearchResult(
                    title=item.get('title', ''),
                    url=item.get('linkTo', ''),
                    link_to_archive=item.get('linkToArchive', ''),
                    timestamp=item.get('timestamp', ''),
                    mime_type=item.get('mimeType', ''),
                    status_code=item.get('statusCode', '')
                )
                results.append(result)
            except Exception as e:
                self._logger.warning(f"Error parsing result item: {e}")
                continue
        
        return results
    
    def _apply_rate_limit(self):
        """Apply rate limiting to respect API limits."""
        current_time = time.time()
        
        # Reset counter if window expired
        if current_time - self._last_request_time > self._rate_limit_window:
            self._request_count = 0
            self._last_request_time = current_time
        
        # Check if we're approaching rate limit
        if self._request_count >= self._rate_limit_max:
            sleep_time = self._rate_limit_window - (current_time - self._last_request_time)
            if sleep_time > 0:
                self._logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
                self._request_count = 0
                self._last_request_time = time.time()
        
        self._request_count += 1
    
    def verify_content_match(self, original_url: str, candidate_url: str) -> Dict[str, Any]:
        """
        Verify if candidate URL matches original using archive evidence.
        
        Args:
            original_url: Original dead URL
            candidate_url: Candidate replacement URL
            
        Returns:
            Dictionary with verification results
        """
        try:
            # Search for original URL in archive
            original_results = self._search_url(original_url, max_results=1)
            
            # Search for candidate URL in archive
            candidate_results = self._search_url(candidate_url, max_results=1)
            
            result = {
                'original_archive_available': len(original_results) > 0,
                'candidate_archive_available': len(candidate_results) > 0,
                'original_title': original_results[0].title if original_results else None,
                'candidate_title': candidate_results[0].title if candidate_results else None,
                'original_archive_url': original_results[0].link_to_archive if original_results else None,
                'candidate_archive_url': candidate_results[0].link_to_archive if candidate_results else None,
                'title_match': False
            }
            
            # Check title match
            if result['original_title'] and result['candidate_title']:
                result['title_match'] = (
                    result['original_title'].lower() == result['candidate_title'].lower()
                )
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error verifying content match: {e}")
            return {
                'original_archive_available': False,
                'candidate_archive_available': False,
                'error': str(e)
            }
