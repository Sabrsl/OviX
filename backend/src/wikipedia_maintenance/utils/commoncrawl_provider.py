"""
Common Crawl Archive Provider.

This module implements the Common Crawl archive provider using the CDXJ index
for searching archived web content and discovering candidate replacement URLs.

Common Crawl CDXJ documentation:
- CDX API: https://index.commoncrawl.org/[CC-MAIN-YYYY-WW]-index
- Rate limit: Can return 503 if too many requests from same IP
- Requires HTTPS, proper User-Agent, no excessive parallel requests
- Returns JSON with urlkey, timestamp, url, mime, status, digest, length, offset, filename
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


class CommonCrawlStatus(Enum):
    """Status of Common Crawl API."""
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass
class CommonCrawlSearchResult:
    """Result from Common Crawl CDXJ search."""
    urlkey: str
    timestamp: str
    url: str
    mime: str
    status: str
    digest: str
    length: str
    offset: str
    filename: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'urlkey': self.urlkey,
            'timestamp': self.timestamp,
            'url': self.url,
            'mime': self.mime,
            'status': self.status,
            'digest': self.digest,
            'length': self.length,
            'offset': self.offset,
            'filename': self.filename
        }


class CommonCrawlProvider(BaseArchiveProvider):
    """
    Common Crawl archive provider using CDXJ index.
    
    Uses Common Crawl CDXJ index to search for archived content
    and discover candidate replacement URLs.
    
    CDX API endpoint: https://index.commoncrawl.org/[CC-MAIN-YYYY-WW]-index
    Rate limit: Can return 503 if too many requests from same IP
    """
    
    CDX_API_BASE = "https://index.commoncrawl.org"
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    
    # Recent crawls to check (most recent first)
    DEFAULT_CRAWLS = [
        "CC-MAIN-2025-43",
        "CC-MAIN-2025-33",
        "CC-MAIN-2025-23",
        "CC-MAIN-2025-14",
        "CC-MAIN-2024-51",
        "CC-MAIN-2024-43",
        "CC-MAIN-2024-33",
    ]
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES, 
                 crawls: Optional[List[str]] = None):
        """
        Initialize Common Crawl provider.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            crawls: List of crawl IDs to search (default: recent crawls)
        """
        super().__init__()
        self.timeout = timeout
        self.max_retries = max_retries
        self.crawls = crawls or self.DEFAULT_CRAWLS
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return "CommonCrawl"
    
    def check_archive(self, url: str) -> ArchiveResult:
        """
        Check if URL is archived in Common Crawl.
        
        Args:
            url: URL to check
            
        Returns:
            ArchiveResult with availability status
        """
        try:
            # Search for URL in Common Crawl
            search_results = self._search_url(url, max_results=1)
            
            if search_results and len(search_results) > 0:
                # Get the most recent result
                most_recent = search_results[0]
                
                # Construct archive URL (WARC file access)
                archive_url = self._construct_archive_url(most_recent)
                
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.AVAILABLE,
                    archive_url=archive_url,
                    archive_date=most_recent.timestamp,
                    metadata={
                        'crawl': self._get_crawl_from_filename(most_recent.filename),
                        'mime_type': most_recent.mime,
                        'status_code': most_recent.status,
                        'digest': most_recent.digest,
                        'total_results': len(search_results),
                        'note': 'archive_url is a CDX API reference URL, not HTML content. Content retrieval requires WARC file access.'
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
        Get content snapshot from Common Crawl.
        
        Note: This requires fetching from S3 which may be complex.
        For now, this returns None as content retrieval from Common Crawl
        requires HTTP range requests to WARC files.
        
        Args:
            url: URL to get snapshot for
            
        Returns:
            HTML content or None (not implemented for Common Crawl)
        """
        # Content retrieval from Common Crawl requires HTTP range requests
        # to S3 WARC files, which is complex. For now, we use Common Crawl
        # primarily for metadata and candidate discovery, not content.
        self._logger.warning("Content snapshot not implemented for Common Crawl (requires WARC file access)")
        return None
    
    def search_by_url(self, url: str, max_results: int = 10) -> List[CommonCrawlSearchResult]:
        """
        Search archived content by URL in Common Crawl.
        
        Args:
            url: URL to search for
            max_results: Maximum number of results
            
        Returns:
            List of CommonCrawlSearchResult
        """
        return self._search_url(url, max_results=max_results)
    
    def search_by_domain(self, domain: str, max_results: int = 10) -> List[CommonCrawlSearchResult]:
        """
        Search archived content by domain in Common Crawl.
        
        Args:
            domain: Domain to search for
            max_results: Maximum number of results
            
        Returns:
            List of CommonCrawlSearchResult
        """
        try:
            # Convert domain to SURT format for CDX search
            surt_domain = self._domain_to_surt(domain)
            
            # Search for domain pattern
            query = f"{surt_domain}*"
            
            results = []
            for crawl in self.crawls:
                crawl_results = self._search_cdx(crawl, query, max_results=max_results)
                results.extend(crawl_results)
                
                if len(results) >= max_results:
                    break
            
            return results[:max_results]
            
        except Exception as e:
            self._logger.error(f"Error searching by domain {domain}: {e}")
            return []
    
    def _search_url(self, url: str, max_results: int = 10) -> List[CommonCrawlSearchResult]:
        """
        Search for URL in Common Crawl CDXJ index.
        
        Args:
            url: URL to search for
            max_results: Maximum number of results
            
        Returns:
            List of CommonCrawlSearchResult
        """
        results = []
        
        for crawl in self.crawls:
            try:
                # Add delay between requests to avoid rate limiting
                time.sleep(1)
                
                crawl_results = self._search_cdx(crawl, url, max_results=max_results)
                results.extend(crawl_results)
                
                if len(results) >= max_results:
                    break
                    
            except Exception as e:
                self._logger.warning(f"Error searching crawl {crawl}: {e}")
                continue
        
        return results[:max_results]
    
    def _search_cdx(self, crawl: str, query: str, max_results: int = 10) -> List[CommonCrawlSearchResult]:
        """
        Search Common Crawl CDX index for a specific crawl.
        
        Args:
            crawl: Crawl ID (e.g., CC-MAIN-2025-43)
            query: Search query (URL or pattern)
            max_results: Maximum number of results
            
        Returns:
            List of CommonCrawlSearchResult
        """
        try:
            cdx_url = f"{self.CDX_API_BASE}/{crawl}-index"
            
            params = {
                'url': query,
                'output': 'json',
                'limit': max_results
            }
            
            response = self._make_request(cdx_url, params)
            
            if response and len(response) >= 2:
                # First row is headers, skip it
                return self._parse_cdx_results(response[1:])
            
            return []
            
        except Exception as e:
            self._logger.error(f"Error searching CDX for {crawl}: {e}")
            return []
    
    def _make_request(self, url: str, params: Dict[str, Any]) -> Optional[List]:
        """
        Make request to Common Crawl CDX API with retry logic.
        
        Args:
            url: CDX API endpoint
            params: Query parameters
            
        Returns:
            JSON response or None
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                    headers={
                        'User-Agent': 'WikipediaMaintenanceTool/1.0 (Archive Research)'
                    }
                )
                
                # Handle rate limiting (503)
                if response.status_code == 503:
                    self._logger.warning(f"Rate limited by Common Crawl (attempt {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        sleep_time = self.RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                        self._logger.info(f"Sleeping for {sleep_time}s before retry")
                        time.sleep(sleep_time)
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
    
    def _parse_cdx_results(self, items: List[List]) -> List[CommonCrawlSearchResult]:
        """
        Parse CDX results from Common Crawl API.
        
        CDX format: urlkey, timestamp, original, mimetype, statuscode, digest, length, offset, filename
        
        Args:
            items: Response items from CDX API
            
        Returns:
            List of CommonCrawlSearchResult
        """
        results = []
        
        for item in items:
            try:
                # Ensure item has enough fields
                if len(item) < 9:
                    continue
                
                result = CommonCrawlSearchResult(
                    urlkey=item[0],
                    timestamp=item[1],
                    url=item[2],
                    mime=item[3],
                    status=item[4],
                    digest=item[5],
                    length=item[6],
                    offset=item[7],
                    filename=item[8]
                )
                results.append(result)
            except Exception as e:
                self._logger.warning(f"Error parsing CDX result item: {e}")
                continue
        
        return results
    
    def _construct_archive_url(self, result: CommonCrawlSearchResult) -> str:
        """
        Construct archive URL from CDX result.
        
        Note: This is a simplified URL. Actual content retrieval requires
        HTTP range requests to S3 WARC files.
        
        Args:
            result: CDX search result
            
        Returns:
            Archive URL (for reference only)
        """
        # Return a reference URL that points to the CDX record
        # Actual content retrieval requires WARC file access
        return f"https://index.commoncrawl.org/{self._get_crawl_from_filename(result.filename)}-index?url={result.url}"
    
    def _get_crawl_from_filename(self, filename: str) -> str:
        """
        Extract crawl ID from filename.
        
        Args:
            filename: WARC filename
            
        Returns:
            Crawl ID
        """
        # Filename format: crawl-data/CC-MAIN-2025-43/segments/...
        parts = filename.split('/')
        if len(parts) >= 2:
            return parts[1]
        return "unknown"
    
    def _domain_to_surt(self, domain: str) -> str:
        """
        Convert domain to SURT (Sort-friendly URI Reordering Transform) format.
        
        Args:
            domain: Domain name
            
        Returns:
            SURT format domain
        """
        # Simple SURT conversion (reverse domain components)
        parts = domain.split('.')
        reversed_parts = list(reversed(parts))
        return ','.join(reversed_parts) + ')'
    
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
                'original_title': None,  # Common Crawl doesn't provide titles
                'candidate_title': None,  # Common Crawl doesn't provide titles
                'original_archive_url': original_results[0].url if original_results else None,
                'candidate_archive_url': candidate_results[0].url if candidate_results else None,
                'title_match': False,
                'digest_match': False
            }
            
            # Check digest match (content fingerprint)
            if original_results and candidate_results:
                result['digest_match'] = (
                    original_results[0].digest == candidate_results[0].digest
                )
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error verifying content match: {e}")
            return {
                'original_archive_available': False,
                'candidate_archive_available': False,
                'error': str(e)
            }
