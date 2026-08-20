"""
Archive Provider for research and verification.

This service provides access to web archives (Wayback Machine, Archive.org, CommonCrawl, etc.)
for content verification and candidate discovery.

Archives are used to:
- Verify that candidate URLs match original content
- Discover URL structure patterns and redirect history
- Provide evidence for content verification
- Find candidate replacement URLs for dead links

Archives are NOT used to:
- Automatically replace dead links with archive URLs directly
- Generate archive URL-based repairs without validation

The distinction: Archives help FIND candidates and VERIFY them, but don't directly replace
links with archive URLs. Candidates must pass live validation before being used.
"""

import logging
import urllib.request
import urllib.error
import json
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .api_throttler import get_link_check_throttler
from .retry_handler import RetryHandler, RetryConfig, RetryStrategy

logger = logging.getLogger(__name__)


class ArchiveAvailability(Enum):
    """Availability status of archive."""
    AVAILABLE = "available"  # Archive exists and is accessible
    NOT_AVAILABLE = "not_available"  # No archive found (confirmed by reliable provider)
    CHECK_FAILED = "check_failed"  # Archive check failed (network, API error)
    ACCESS_DENIED = "access_denied"  # Archive exists but access denied
    PROVIDER_UNAVAILABLE = "provider_unavailable"  # All providers failed technically (503, timeout, etc.) - NOT the same as no archive
    ENVIRONMENT_ERROR = "environment_error"  # Local environment error (SSL, DNS, etc.) - provider not actually tested


@dataclass
class ArchiveResult:
    """Result of archive lookup."""
    original_url: str
    availability: ArchiveAvailability
    archive_url: Optional[str] = None
    archive_date: Optional[str] = None
    content_snapshot: Optional[str] = None
    title: Optional[str] = None
    reason: Optional[str] = None
    provider: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'original_url': self.original_url,
            'availability': self.availability.value,
            'archive_url': self.archive_url,
            'archive_date': self.archive_date,
            'title': self.title,
            'reason': self.reason,
            'provider': self.provider,
            'metadata': self.metadata
        }


class BaseArchiveProvider(ABC):
    """
    Base class for archive providers.
    
    Archive providers are used for RESEARCH AND VERIFICATION.
    They can be used for automatic link replacement as a fallback when
    no redirect is available, subject to validation criteria.
    
    Note: The ArchiveProvider coordinator class uses BaseArchiveProvider
    implementations for research, verification, and as a fallback repair
    mechanism when no live redirect is found.
    """
    
    USER_AGENT = "WikipediaMaintenanceTool/1.0 (Archive Research)"
    DEFAULT_TIMEOUT = 30  # Increased from 15 to 30 to handle slow archive APIs
    
    def __init__(self, timeout: int = None):
        """
        Initialize archive provider.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.api_throttler = get_link_check_throttler()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name."""
        pass
    
    @abstractmethod
    def check_archive(self, url: str) -> ArchiveResult:
        """
        Check if archive exists for URL.
        
        Args:
            url: URL to check
            
        Returns:
            ArchiveResult with availability information
        """
        pass
    
    @abstractmethod
    def get_content_snapshot(self, url: str, archive_date: str = None) -> Optional[str]:
        """
        Get content snapshot from archive.
        
        Args:
            url: Original URL
            archive_date: Specific archive date (optional)
            
        Returns:
            Content snapshot or None if not available
        """
        pass
    
    def _make_request(self, url: str) -> Optional[str]:
        """
        Make HTTP request with throttling.
        
        Args:
            url: URL to request
            
        Returns:
            Response content or None if failed
        """
        try:
            self.api_throttler.wait_if_needed()
            
            request = urllib.request.Request(
                url,
                headers={'User-Agent': self.USER_AGENT}
            )
            
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read().decode('utf-8', errors='ignore')
                
        except urllib.error.HTTPError as e:
            # Enhanced logging with specific error types
            if e.code == 429:
                self._logger.warning(f"ARCHIVE_RATE_LIMITED | url={url} | provider={self.get_provider_name()} | error=429")
            elif e.code == 503:
                self._logger.warning(f"ARCHIVE_SERVICE_UNAVAILABLE | url={url} | provider={self.get_provider_name()} | error=503")
            elif e.code == 404:
                self._logger.info(f"ARCHIVE_NOT_FOUND | url={url} | provider={self.get_provider_name()} | error=404")
            else:
                self._logger.warning(f"ARCHIVE_HTTP_ERROR | url={url} | provider={self.get_provider_name()} | error={e.code}")
            return None
        except urllib.error.URLError as e:
            # Distinguish between timeout and other URL errors
            import socket
            import ssl
            if isinstance(e.reason, socket.timeout):
                self._logger.warning(f"ARCHIVE_TIMEOUT | url={url} | provider={self.get_provider_name()} | error=timeout")
            elif isinstance(e.reason, ConnectionRefusedError):
                self._logger.warning(f"ARCHIVE_CONNECTION_REFUSED | url={url} | provider={self.get_provider_name()} | error=connection_refused")
            elif isinstance(e.reason, ssl.SSLCertVerificationError):
                # SSL certificate error is an environment error, not a provider failure
                self._logger.error(f"ARCHIVE_SSL_ERROR | url={url} | provider={self.get_provider_name()} | error=ssl_certificate_verification_failed")
                # Return a special marker for environment errors
                return "SSL_ERROR"
            elif "CERTIFICATE_VERIFY_FAILED" in str(e.reason):
                # Catch SSL errors that might not be in the exception type
                self._logger.error(f"ARCHIVE_SSL_ERROR | url={url} | provider={self.get_provider_name()} | error=certificate_verify_failed")
                return "SSL_ERROR"
            else:
                self._logger.warning(f"ARCHIVE_URL_ERROR | url={url} | provider={self.get_provider_name()} | error={e.reason}")
            return None
        except Exception as e:
            self._logger.error(f"ARCHIVE_UNEXPECTED_ERROR | url={url} | provider={self.get_provider_name()} | error={e}")
            return None


class WaybackProvider(BaseArchiveProvider):
    """
    Wayback Machine archive provider.
    
    Uses Internet Archive CDX API and Wayback Machine API.
    """
    
    CDX_API_URL = "https://web.archive.org/cdx/search/cdx"
    WAYBACK_API_URL = "https://web.archive.org/web/timemap/json"
    
    def get_provider_name(self) -> str:
        return "WaybackMachine"
    
    def check_archive(self, url: str) -> ArchiveResult:
        """
        Check if Wayback Machine has archive for URL with retry logic.
        
        Args:
            url: URL to check
            
        Returns:
            ArchiveResult with availability information
        """
        # Clean URL (with validation for invalid percent-encoding)
        try:
            clean_url = self._clean_url(url)
        except ValueError as e:
            self._logger.warning(f"URL validation failed: {e}")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason=f"Invalid URL syntax: {e}",
                provider=self.get_provider_name()
            )
        
        # Query CDX API with retry logic
        # NOTE: filter=statuscode:200 excludes snapshots whose ORIGINAL crawl
        # response was not 2xx (e.g. a 302 to an access-restricted page that
        # Wayback still serves as HTTP 200). Without this filter, a snapshot
        # of an error/redirect page can be proposed as if it were the real content.
        cdx_url = f"{self.CDX_API_URL}?url={clean_url}&output=json&limit=1&filter=statuscode:200"
        
        # Retry logic for timeout cases (increased to 3 for high-reliability provider)
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            max_delay=8.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retry_on_exceptions=(Exception,)
        )
        retry_handler = RetryHandler(retry_config)
        
        def make_cdx_request():
            response = self._make_request(cdx_url)
            if response == "SSL_ERROR":
                raise ValueError("SSL_ERROR")
            return response
        
        try:
            response = retry_handler.execute_with_retry(make_cdx_request)
        except ValueError as e:
            if str(e) == "SSL_ERROR":
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.ENVIRONMENT_ERROR,
                    reason="SSL certificate verification failed - environment error",
                    provider=self.get_provider_name()
                )
            response = None
        
        if not response:
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason="CDX API request failed after retries",
                provider=self.get_provider_name()
            )
        
        try:
            data = json.loads(response)
            
            # CDX API returns [field_names, [record1, record2, ...]]
            if len(data) < 2:
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.NOT_AVAILABLE,
                    reason="No archive found",
                    provider=self.get_provider_name()
                )
            
            # Get most recent snapshot
            # CDX API returns: [field_names, [field1, field2, ...]] for single record
            # OR: [field_names, [[record1_fields], [record2_fields], ...]] for multiple records
            if isinstance(data[1], list) and len(data[1]) > 0 and isinstance(data[1][0], list):
                # Multiple records case
                records = data[1]
                first_record = records[0]
            else:
                # Single record case - data[1] is already the record fields
                first_record = data[1]
            
            if not first_record or len(first_record) < 2:
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.NOT_AVAILABLE,
                    reason="Invalid record format",
                    provider=self.get_provider_name()
                )
            
            # Use field names to find timestamp field instead of assuming position
            field_names = data[0] if len(data) > 0 else []
            timestamp_field_index = None
            for i, field_name in enumerate(field_names):
                if field_name == 'timestamp':
                    timestamp_field_index = i
                    break
            
            if timestamp_field_index is None:
                self._logger.error(f"CDX response missing timestamp field. Field names: {field_names}")
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.CHECK_FAILED,
                    reason="CDX response missing timestamp field",
                    provider=self.get_provider_name()
                )
            
            archive_date = first_record[timestamp_field_index] if timestamp_field_index < len(first_record) else None
            
            # Validate archive_date format (should be 14 digits: YYYYMMDDHHMMSS)
            if archive_date and (not archive_date.isdigit() or len(archive_date) != 14):
                self._logger.error(f"Invalid archive_date format: '{archive_date}' (expected 14 digits). Full record: {first_record}")
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.CHECK_FAILED,
                    reason=f"Invalid archive_date format: {archive_date}",
                    provider=self.get_provider_name()
                )
            
            # Construct archive URL - clean_url is already validated and properly formatted
            archive_url = f"https://web.archive.org/web/{archive_date}/{clean_url}" if archive_date else None
            
            # Convert record list to dict for easier access
            record_dict = {}
            for i, field_name in enumerate(field_names):
                if i < len(first_record):
                    record_dict[field_name] = first_record[i]
            
            # Defense in depth: even though the CDX query above already filters on
            # statuscode:200, don't rely solely on the remote API applying that
            # filter correctly. Re-check the field locally and reject anything
            # that isn't a clean 2xx original response.
            orig_statuscode = record_dict.get('statuscode')
            if orig_statuscode and not str(orig_statuscode).startswith('2'):
                self._logger.warning(
                    f"WAYBACK_REJECTED_BAD_STATUSCODE | url={url} | statuscode={orig_statuscode}"
                )
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.NOT_AVAILABLE,
                    reason=f"Archived snapshot has non-2xx original status: {orig_statuscode}",
                    provider=self.get_provider_name()
                )
            
            self._logger.info(f"WAYBACK_ARCHIVE_FOUND | url={url} | archive_date={archive_date}")
            
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.AVAILABLE,
                archive_url=archive_url,
                archive_date=archive_date,
                provider=self.get_provider_name(),
                metadata={'raw_record': record_dict, 'raw_fields': first_record}
            )
            
        except (json.JSONDecodeError, IndexError) as e:
            self._logger.error(f"Failed to parse CDX response for {url}: {e}")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason=f"Failed to parse CDX response: {e}",
                provider=self.get_provider_name()
            )
    
    def get_content_snapshot(self, url: str, archive_date: str = None) -> Optional[str]:
        """
        Get content snapshot from Wayback Machine.
        
        Args:
            url: Original URL
            archive_date: Specific archive date (YYYYMMDDHHMMSS format)
            
        Returns:
            Content snapshot or None if not available
        """
        # Clean URL (with validation for invalid percent-encoding)
        try:
            clean_url = self._clean_url(url)
        except ValueError as e:
            self._logger.warning(f"URL validation failed: {e}")
            return None
        
        if archive_date:
            archive_url = f"https://web.archive.org/web/{archive_date}/{clean_url}"
        else:
            # Get most recent snapshot
            check_result = self.check_archive(url)
            if check_result.availability != ArchiveAvailability.AVAILABLE:
                return None
            archive_url = check_result.archive_url
        
        # Retry logic with exponential backoff for content snapshot
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            max_delay=8.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retry_on_exceptions=(Exception,)
        )
        retry_handler = RetryHandler(retry_config)
        
        def make_snapshot_request():
            return self._make_request(archive_url)
        
        try:
            response = retry_handler.execute_with_retry(make_snapshot_request)
        except Exception:
            response = None
        
        return response
    
    def _clean_url(self, url: str) -> str:
        """
        Clean URL for Wayback Machine API.
        
        Args:
            url: URL to clean
            
        Returns:
            Cleaned URL
        """
        # Remove fragments
        if '#' in url:
            url = url.split('#')[0]
        
        # Ensure protocol
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        
        # FIX: Validate that all percent-encoding sequences are valid
        # Each '%' must be followed by exactly 2 hexadecimal digits
        # This prevents corrupted URLs like '...pdf%/langue=it' from being used
        import re
        invalid_percent = re.search(r'%(?![0-9A-Fa-f]{2})', url)
        if invalid_percent:
            self._logger.warning(f"URL contains invalid percent-encoding: {url} - rejecting")
            raise ValueError(f"Invalid percent-encoding in URL: {url}")
        
        return url


class ArchiveOrgProvider(BaseArchiveProvider):
    """
    Archive.org (Internet Archive) direct search provider.
    
    Uses archive.org search API for additional archive discovery.
    """
    
    SEARCH_API_URL = "https://archive.org/advancedsearch.php"
    
    def get_provider_name(self) -> str:
        return "Archive.org"
    
    def check_archive(self, url: str) -> ArchiveResult:
        """
        Check if archive.org has archive for URL using search API with retry logic.
        
        Args:
            url: URL to check
            
        Returns:
            ArchiveResult with availability information
        """
        # Clean URL (with validation for invalid percent-encoding)
        try:
            clean_url = self._clean_url(url)
        except ValueError as e:
            self._logger.warning(f"URL validation failed: {e}")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason=f"Invalid URL syntax: {e}",
                provider=self.get_provider_name()
            )
        
        # Build search query for exact URL
        query = f'url:"{clean_url}"'
        search_url = f"{self.SEARCH_API_URL}?q={query}&fl[]=identifier&fl[]=title&fl[]=date&output=json&rows=1"
        
        # Retry logic for timeout cases (increased to 3 for high-reliability provider)
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            max_delay=8.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retry_on_exceptions=(Exception,)
        )
        retry_handler = RetryHandler(retry_config)
        
        def make_search_request():
            response = self._make_request(search_url)
            if response == "SSL_ERROR":
                raise ValueError("SSL_ERROR")
            return response
        
        try:
            response = retry_handler.execute_with_retry(make_search_request)
        except ValueError as e:
            if str(e) == "SSL_ERROR":
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.ENVIRONMENT_ERROR,
                    reason="SSL certificate verification failed - environment error",
                    provider=self.get_provider_name()
                )
            response = None
        
        if not response:
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason="Archive.org search API request failed after retries",
                provider=self.get_provider_name()
            )
        
        # Check if response is HTML (error page) instead of JSON
        if response.strip().startswith('<'):
            self._logger.warning(f"ARCHIVE_ORG_HTML_RESPONSE | url={url} | response_starts_with_html")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason="Archive.org returned HTML error page instead of JSON",
                provider=self.get_provider_name()
            )
        
        try:
            data = json.loads(response)
            self._logger.info(f"ARCHIVE_ORG_RESPONSE_PARSED | url={url} | response_length={len(response)} | data_keys={list(data.keys())}")
            
            # Check if response is an error page (HTTP 502, etc.)
            if 'error' in data or 'status' in data:
                self._logger.warning(f"ARCHIVE_ORG_ERROR_RESPONSE | url={url} | error_data={data}")
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.CHECK_FAILED,
                    reason=f"Archive.org returned error response: {data}",
                    provider=self.get_provider_name()
                )
            
            # Check if response has empty docs array (genuine NOT_AVAILABLE)
            if 'response' in data and 'docs' in data['response'] and len(data['response']['docs']) == 0:
                self._logger.info(f"ARCHIVE_ORG_NO_RESULTS | url={url} | docs_array_empty")
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.NOT_AVAILABLE,
                    reason="No archive found in archive.org (empty docs array)",
                    provider=self.get_provider_name()
                )
            
            # Archive.org search API returns {"response":{"docs":[...]}}
            if 'response' in data and 'docs' in data['response'] and len(data['response']['docs']) > 0:
                doc = data['response']['docs'][0]
                identifier = doc.get('identifier', '')
                
                if identifier:
                    archive_url = f"https://archive.org/details/{identifier}"
                    archive_date = doc.get('date', 'unknown')
                    
                    self._logger.info(f"ARCHIVE_ORG_FOUND | url={url} | identifier={identifier} | date={archive_date}")
                    
                    return ArchiveResult(
                        original_url=url,
                        availability=ArchiveAvailability.AVAILABLE,
                        archive_url=archive_url,
                        archive_date=archive_date,
                        provider=self.get_provider_name(),
                        metadata={'identifier': identifier, 'raw_doc': doc}
                    )
            
            # Response was valid JSON but no results - this is a genuine NOT_AVAILABLE
            self._logger.info(f"ARCHIVE_ORG_NO_RESULTS | url={url} | response_valid_but_no_docs")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.NOT_AVAILABLE,
                reason="No archive found in archive.org",
                provider=self.get_provider_name()
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            self._logger.error(f"Failed to parse archive.org response for {url}: {e}")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason=f"Failed to parse archive.org response: {e}",
                provider=self.get_provider_name()
            )
    
    def get_content_snapshot(self, url: str, archive_date: str = None) -> Optional[str]:
        """
        Get content snapshot from archive.org.
        
        Args:
            url: Original URL
            archive_date: Specific archive date (not used for archive.org)
            
        Returns:
            Content snapshot or None if not available
        """
        # First get the archive URL
        check_result = self.check_archive(url)
        if check_result.availability != ArchiveAvailability.AVAILABLE:
            return None
        
        # Try to fetch from the archive.org details page
        archive_url = check_result.archive_url
        
        # Retry logic with exponential backoff for content snapshot
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            max_delay=8.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retry_on_exceptions=(Exception,)
        )
        retry_handler = RetryHandler(retry_config)
        
        def make_snapshot_request():
            return self._make_request(archive_url)
        
        try:
            response = retry_handler.execute_with_retry(make_snapshot_request)
        except Exception:
            response = None
        
        return response
    
    def _clean_url(self, url: str) -> str:
        """
        Clean URL for archive.org search.
        
        Args:
            url: URL to clean
            
        Returns:
            Cleaned URL
        """
        # Remove fragments
        if '#' in url:
            url = url.split('#')[0]
        
        # Ensure protocol
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        
        # FIX: Validate that all percent-encoding sequences are valid
        # Each '%' must be followed by exactly 2 hexadecimal digits
        # This prevents corrupted URLs like '...pdf%/langue=it' from being used
        import re
        invalid_percent = re.search(r'%(?![0-9A-Fa-f]{2})', url)
        if invalid_percent:
            self._logger.warning(f"URL contains invalid percent-encoding: {url} - rejecting")
            raise ValueError(f"Invalid percent-encoding in URL: {url}")
        
        return url


class ArquivoProvider(BaseArchiveProvider):
    """
    Arquivo.pt (Portuguese Web Archive) provider.
    
    Uses Arquivo.pt API for archive discovery.
    """
    
    CDX_API_URL = "https://arquivo.pt/textsearch"
    
    def get_provider_name(self) -> str:
        return "Arquivo.pt"
    
    def check_archive(self, url: str) -> ArchiveResult:
        """
        Check if Arquivo.pt has archive for URL with retry logic.
        
        Args:
            url: URL to check
            
        Returns:
            ArchiveResult with availability information
        """
        # Clean URL (with validation for invalid percent-encoding)
        try:
            clean_url = self._clean_url(url)
        except ValueError as e:
            self._logger.warning(f"URL validation failed: {e}")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason=f"Invalid URL syntax: {e}",
                provider=self.get_provider_name()
            )
        
        # Build search query for exact URL
        query = f'url:"{clean_url}"'
        search_url = f"{self.CDX_API_URL}?q={query}&fields=originalURL,timestamp,domain&maxItems=1"
        
        # Retry logic for timeout cases
        max_retries = 2
        for attempt in range(max_retries):
            response = self._make_request(search_url)
            
            if response == "SSL_ERROR":
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.ENVIRONMENT_ERROR,
                    reason="SSL certificate verification failed - environment error",
                    provider=self.get_provider_name()
                )
            
            if response:
                break  # Success, exit retry loop
            
            if attempt < max_retries - 1:
                self._logger.warning(f"Arquivo.pt API request failed (attempt {attempt + 1}/{max_retries}), retrying...")
                import time
                time.sleep(2)  # Wait before retry
            else:
                self._logger.error(f"Arquivo.pt API request failed after {max_retries} attempts")
        
        if not response:
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason="Arquivo.pt API request failed after retries",
                provider=self.get_provider_name()
            )
        
        # Check if response is HTML (error page) instead of JSON
        if response.strip().startswith('<'):
            self._logger.warning(f"ARQUIVO_HTML_RESPONSE | url={url} | response_starts_with_html")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason="Arquivo.pt returned HTML error page instead of JSON",
                provider=self.get_provider_name()
            )
        
        try:
            data = json.loads(response)
            self._logger.info(f"ARQUIVO_RESPONSE_PARSED | url={url} | response_length={len(response)} | data_keys={list(data.keys())}")
            
            # Check if response is an error page
            if 'error' in data or 'status' in data:
                self._logger.warning(f"ARQUIVO_ERROR_RESPONSE | url={url} | error_data={data}")
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.CHECK_FAILED,
                    reason=f"Arquivo.pt returned error response: {data}",
                    provider=self.get_provider_name()
                )
            
            # Check if response has empty responseItems array (genuine NOT_AVAILABLE)
            if 'responseItems' in data and len(data['responseItems']) == 0:
                self._logger.info(f"ARQUIVO_NO_RESULTS | url={url} | responseItems_empty")
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.NOT_AVAILABLE,
                    reason="No archive found in Arquivo.pt (empty responseItems array)",
                    provider=self.get_provider_name()
                )
            
            # Arquivo.pt returns {"responseItems":[...]}
            if 'responseItems' in data and len(data['responseItems']) > 0:
                item = data['responseItems'][0]
                original_url = item.get('originalURL', '')
                timestamp = item.get('timestamp', '')
                
                if original_url and timestamp:
                    # Convert timestamp to archive URL format
                    # Arquivo.pt uses format: https://arquivo.pt/wayback/YYYYMMDDHHMMSS/http://...
                    archive_url = f"https://arquivo.pt/wayback/{timestamp}/{original_url}"
                    
                    self._logger.info(f"ARQUIVO_ARCHIVE_FOUND | url={url} | timestamp={timestamp}")
                    
                    return ArchiveResult(
                        original_url=url,
                        availability=ArchiveAvailability.AVAILABLE,
                        archive_url=archive_url,
                        archive_date=timestamp,
                        provider=self.get_provider_name(),
                        metadata={'raw_item': item}
                    )
            
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.NOT_AVAILABLE,
                reason="No archive found in Arquivo.pt",
                provider=self.get_provider_name()
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            self._logger.error(f"Failed to parse Arquivo.pt response for {url}: {e}")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason=f"Failed to parse Arquivo.pt response: {e}",
                provider=self.get_provider_name()
            )
    
    def get_content_snapshot(self, url: str, archive_date: str = None) -> Optional[str]:
        """
        Get content snapshot from Arquivo.pt.
        
        Args:
            url: Original URL
            archive_date: Specific archive date (YYYYMMDDHHMMSS format)
            
        Returns:
            Content snapshot or None if not available
        """
        # First get the archive URL
        check_result = self.check_archive(url)
        if check_result.availability != ArchiveAvailability.AVAILABLE:
            return None
        
        # Try to fetch from the archive URL
        archive_url = check_result.archive_url
        return self._make_request(archive_url)
    
    def _clean_url(self, url: str) -> str:
        """
        Clean URL for Arquivo.pt search.
        
        Args:
            url: URL to clean
            
        Returns:
            Cleaned URL
        """
        # Remove fragments
        if '#' in url:
            url = url.split('#')[0]
        
        # Ensure protocol
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        
        # Validate percent-encoding
        import re
        invalid_percent = re.search(r'%(?![0-9A-Fa-f]{2})', url)
        if invalid_percent:
            self._logger.warning(f"URL contains invalid percent-encoding: {url} - rejecting")
            raise ValueError(f"Invalid percent-encoding in URL: {url}")
        
        return url


class UKWebArchiveProvider(BaseArchiveProvider):
    """
    UK Web Archive provider.
    
    Uses UK Web Archive API for archive discovery.
    """
    
    SEARCH_API_URL = "https://www.webarchive.org.uk/act/wayback/search"
    
    def get_provider_name(self) -> str:
        return "UKWebArchive"
    
    def check_archive(self, url: str) -> ArchiveResult:
        """
        Check if UK Web Archive has archive for URL with retry logic.
        
        Args:
            url: URL to check
            
        Returns:
            ArchiveResult with availability information
        """
        # Clean URL (with validation for invalid percent-encoding)
        try:
            clean_url = self._clean_url(url)
        except ValueError as e:
            self._logger.warning(f"URL validation failed: {e}")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason=f"Invalid URL syntax: {e}",
                provider=self.get_provider_name()
            )
        
        # Build search query for exact URL
        search_url = f"{self.SEARCH_API_URL}?url={clean_url}&matchType=domain&limit=1"
        
        # Retry logic for timeout cases
        max_retries = 2
        for attempt in range(max_retries):
            response = self._make_request(search_url)
            
            if response == "SSL_ERROR":
                return ArchiveResult(
                    original_url=url,
                    availability=ArchiveAvailability.ENVIRONMENT_ERROR,
                    reason="SSL certificate verification failed - environment error",
                    provider=self.get_provider_name()
                )
            
            if response:
                break  # Success, exit retry loop
            
            if attempt < max_retries - 1:
                self._logger.warning(f"UK Web Archive API request failed (attempt {attempt + 1}/{max_retries}), retrying...")
                import time
                time.sleep(2)  # Wait before retry
            else:
                self._logger.error(f"UK Web Archive API request failed after {max_retries} attempts")
        
        if not response:
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason="UK Web Archive API request failed after retries",
                provider=self.get_provider_name()
            )
        
        try:
            data = json.loads(response)
            
            # UK Web Archive returns {"results":[...]}
            if 'results' in data and len(data['results']) > 0:
                result = data['results'][0]
                timestamp = result.get('timestamp', '')
                
                if timestamp:
                    # UK Web Archive uses format: https://www.webarchive.org.uk/wayback/archive/YYYYMMDDHHMMSS/http://...
                    archive_url = f"https://www.webarchive.org.uk/wayback/archive/{timestamp}/{clean_url}"
                    
                    self._logger.info(f"UKWA_ARCHIVE_FOUND | url={url} | timestamp={timestamp}")
                    
                    return ArchiveResult(
                        original_url=url,
                        availability=ArchiveAvailability.AVAILABLE,
                        archive_url=archive_url,
                        archive_date=timestamp,
                        provider=self.get_provider_name(),
                        metadata={'raw_result': result}
                    )
            
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.NOT_AVAILABLE,
                reason="No archive found in UK Web Archive",
                provider=self.get_provider_name()
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            self._logger.error(f"Failed to parse UK Web Archive response for {url}: {e}")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason=f"Failed to parse UK Web Archive response: {e}",
                provider=self.get_provider_name()
            )
    
    def get_content_snapshot(self, url: str, archive_date: str = None) -> Optional[str]:
        """
        Get content snapshot from UK Web Archive.
        
        Args:
            url: Original URL
            archive_date: Specific archive date (YYYYMMDDHHMMSS format)
            
        Returns:
            Content snapshot or None if not available
        """
        # First get the archive URL
        check_result = self.check_archive(url)
        if check_result.availability != ArchiveAvailability.AVAILABLE:
            return None
        
        # Try to fetch from the archive URL
        archive_url = check_result.archive_url
        return self._make_request(archive_url)
    
    def _clean_url(self, url: str) -> str:
        """
        Clean URL for UK Web Archive search.
        
        Args:
            url: URL to clean
            
        Returns:
            Cleaned URL
        """
        # Remove fragments
        if '#' in url:
            url = url.split('#')[0]
        
        # Ensure protocol
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        
        # Validate percent-encoding
        import re
        invalid_percent = re.search(r'%(?![0-9A-Fa-f]{2})', url)
        if invalid_percent:
            self._logger.warning(f"URL contains invalid percent-encoding: {url} - rejecting")
            raise ValueError(f"Invalid percent-encoding in URL: {url}")
        
        return url


# MementoAggregatorProvider removed - service decommissioned on September 5, 2025
# The LANL Memento Aggregator (timetravel.mementoweb.org) is no longer operational


class CommonCrawlProvider(BaseArchiveProvider):
    """
    Common Crawl provider.
    
    Uses Common Crawl Index API for archive discovery.
    Common Crawl provides free web crawl data accessible via their Index API.
    """
    
    CC_INDEX_API = "https://index.commoncrawl.org/collinfo.json"
    
    def __init__(self, timeout: int = None):
        """
        Initialize Common Crawl provider.
        
        Args:
            timeout: Request timeout in seconds
        """
        super().__init__(timeout)
        self._index_urls = []
        self._load_index_urls()
    
    def _load_index_urls(self):
        """Load available Common Crawl index URLs."""
        try:
            response = self._make_request(self.CC_INDEX_API)
            if response:
                import json
                data = json.loads(response)
                # Get the most recent index
                if isinstance(data, list) and len(data) > 0:
                    # Sort by id to get the most recent
                    data.sort(key=lambda x: x.get('id', ''), reverse=True)
                    for index in data[:3]:  # Use the 3 most recent indexes
                        index_name = index.get('id', '')
                        if index_name:
                            self._index_urls.append(f"https://index.commoncrawl.org/{index_name}-index")
                    self._logger.info(f"COMMONCRAWL_INDEXES_LOADED | count={len(self._index_urls)}")
            else:
                self._logger.warning("COMMONCRAWL_INDEX_LOAD_FAILED | response=None")
        except Exception as e:
            self._logger.warning(f"COMMONCRAWL_INDEX_LOAD_FAILED | error={e}")
        
        # Always use fallback if no indexes loaded
        if not self._index_urls:
            self._logger.info("COMMONCRAWL_USING_FALLBACK_INDEXES")
            self._index_urls = [
                "https://index.commoncrawl.org/CC-MAIN-2024-18-index",
                "https://index.commoncrawl.org/CC-MAIN-2024-10-index"
            ]
            self._logger.info(f"COMMONCRAWL_FALLBACK_INDEXES | count={len(self._index_urls)}")
    
    def get_provider_name(self) -> str:
        return "CommonCrawl"
    
    def check_archive(self, url: str) -> ArchiveResult:
        """
        Check if Common Crawl has archive for URL with retry logic.
        
        Args:
            url: URL to check
            
        Returns:
            ArchiveResult with availability information
        """
        # Clean URL (with validation for invalid percent-encoding)
        try:
            clean_url = self._clean_url(url)
        except ValueError as e:
            self._logger.warning(f"URL validation failed: {e}")
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason=f"Invalid URL syntax: {e}",
                provider=self.get_provider_name()
            )
        
        # Try each index in order (most recent first)
        for index_url in self._index_urls:
            try:
                # Common Crawl CDX API format
                cdx_url = f"{index_url}?url={clean_url}&output=json&limit=1"
                
                # Retry logic for timeout cases
                max_retries = 2
                for attempt in range(max_retries):
                    response = self._make_request(cdx_url)
                    
                    if response == "SSL_ERROR":
                        return ArchiveResult(
                            original_url=url,
                            availability=ArchiveAvailability.ENVIRONMENT_ERROR,
                            reason="SSL certificate verification failed - environment error",
                            provider=self.get_provider_name()
                        )
                    
                    if response:
                        break  # Success, exit retry loop
                    
                    if attempt < max_retries - 1:
                        self._logger.warning(f"Common Crawl API request failed (attempt {attempt + 1}/{max_retries}), retrying...")
                        import time
                        time.sleep(2)  # Wait before retry
                    else:
                        self._logger.error(f"Common Crawl API request failed after {max_retries} attempts")
                        continue
                
                if not response:
                    continue  # Try next index
                
                try:
                    data = json.loads(response)
                    
                    # Common Crawl CDX API returns [field_names, [record1, record2, ...]]
                    if len(data) < 2:
                        continue  # No results in this index
                    
                    # Get most recent snapshot
                    if isinstance(data[1], list) and len(data[1]) > 0 and isinstance(data[1][0], list):
                        records = data[1]
                        first_record = records[0]
                    else:
                        first_record = data[1]
                    
                    if not first_record or len(first_record) < 2:
                        continue
                    
                    # Find timestamp field
                    field_names = data[0] if len(data) > 0 else []
                    timestamp_field_index = None
                    for i, field_name in enumerate(field_names):
                        if field_name == 'timestamp':
                            timestamp_field_index = i
                            break
                    
                    if timestamp_field_index is None:
                        continue
                    
                    archive_date = first_record[timestamp_field_index] if timestamp_field_index < len(first_record) else None
                    
                    if archive_date:
                        # Common Crawl doesn't provide direct archive URLs like Wayback
                        # We return the metadata and the user can construct the WARC URL if needed
                        # For now, we return None for archive_url since Common Crawl requires
                        # downloading WARC files which is more complex
                        self._logger.info(f"COMMONCRAWL_ARCHIVE_FOUND | url={url} | timestamp={archive_date}")
                        
                        return ArchiveResult(
                            original_url=url,
                            availability=ArchiveAvailability.AVAILABLE,
                            archive_url=None,  # Common Crawl requires WARC file access
                            archive_date=archive_date,
                            provider=self.get_provider_name(),
                            metadata={'raw_record': first_record, 'index_url': index_url}
                        )
                    
                except (json.JSONDecodeError, IndexError) as e:
                    self._logger.error(f"Failed to parse Common Crawl response for {url}: {e}")
                    continue
                
            except Exception as e:
                self._logger.warning(f"Common Crawl index {index_url} failed: {e}")
                continue
        
        # All indexes failed
        return ArchiveResult(
            original_url=url,
            availability=ArchiveAvailability.NOT_AVAILABLE,
            reason="No archive found in Common Crawl indexes",
            provider=self.get_provider_name()
        )
    
    def get_content_snapshot(self, url: str, archive_date: str = None) -> Optional[str]:
        """
        Get content snapshot from Common Crawl.
        
        Note: Common Crawl requires downloading WARC files which is complex.
        This implementation returns None as Common Crawl is primarily used
        for URL discovery, not direct content access.
        
        Args:
            url: Original URL
            archive_date: Specific archive date (not used)
            
        Returns:
            None (Common Crawl requires WARC file access)
        """
        self._logger.warning("Common Crawl content snapshots require WARC file access - not implemented")
        return None
    
    def _clean_url(self, url: str) -> str:
        """
        Clean URL for Common Crawl search.
        
        Args:
            url: URL to clean
            
        Returns:
            Cleaned URL
        """
        # Remove fragments
        if '#' in url:
            url = url.split('#')[0]
        
        # Ensure protocol
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        
        # Validate percent-encoding
        import re
        invalid_percent = re.search(r'%(?![0-9A-Fa-f]{2})', url)
        if invalid_percent:
            self._logger.warning(f"URL contains invalid percent-encoding: {url} - rejecting")
            raise ValueError(f"Invalid percent-encoding in URL: {url}")
        
        return url


class ArchiveProvider:
    """
    Main archive provider that coordinates multiple archive services.
    
    This provider is used for:
    - RESEARCH AND VERIFICATION (primary use)
    - AUTOMATIC LINK REPLACEMENT as fallback when no redirect is available (secondary use)
    
    Coordinates multiple archive services (Wayback Machine, Archive.org, Arquivo.pt, UK Web Archive, etc.)
    with retry logic and enhanced fallback capabilities.
    """
    
    def __init__(self):
        """Initialize archive provider with available services."""
        self.providers = [
            WaybackProvider(),
            ArchiveOrgProvider(),  # Additional archive.org direct search
            ArquivoProvider(),  # Portuguese Web Archive - moved to parallel pool
            # UKWebArchiveProvider(),  # DISABLED: SSL certificate verification fails systematically (100% failure rate)
            # CommonCrawlProvider(),  # DISABLED: Fails systematically (0/4 stability tests), needs endpoint/format fix
            # MementoAggregatorProvider(),  # REMOVED: Service decommissioned on September 5, 2025 (LANL Memento Aggregator)
        ]
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._cache: Dict[str, ArchiveResult] = {}  # Cache for archive check results
    
    def check_all_providers(self, url: str) -> List[ArchiveResult]:
        """
        Check archive availability across all providers and return all available results.
        
        Unlike check_archive(), this method does NOT use early exit and returns
        all available archives from all providers, enabling multi-provider verification fallback.
        
        Args:
            url: URL to check
            
        Returns:
            List of ArchiveResult from all providers that found an archive
        """
        self._logger.info(f"ARCHIVE_SEARCH_ALL | url={url}")
        
        available_results = []
        
        for provider in self.providers:
            provider_name = provider.get_provider_name()
            
            try:
                self._logger.info(f"ARCHIVE_PROVIDER | provider={provider_name} | status=CHECKING")
                result = provider.check_archive(url)
                
                if result.availability == ArchiveAvailability.AVAILABLE:
                    self._logger.info(f"ARCHIVE_CANDIDATE | provider={provider_name} | url={url} | archive_url={result.archive_url} | archive_date={result.archive_date}")
                    available_results.append(result)
                elif result.availability == ArchiveAvailability.CHECK_FAILED:
                    self._logger.warning(f"ARCHIVE_PROVIDER | provider={provider_name} | status=CHECK_FAILED | error={result.reason}")
                elif result.availability == ArchiveAvailability.NOT_AVAILABLE:
                    self._logger.info(f"ARCHIVE_PROVIDER | provider={provider_name} | status=NOT_AVAILABLE | reason={result.reason}")
                elif result.availability == ArchiveAvailability.ENVIRONMENT_ERROR:
                    self._logger.error(f"ARCHIVE_PROVIDER | provider={provider_name} | status=ENVIRONMENT_ERROR | error={result.reason}")
                else:
                    self._logger.info(f"ARCHIVE_PROVIDER | provider={provider_name} | status={result.availability.value} | reason={result.reason}")
            except Exception as e:
                self._logger.error(f"ARCHIVE_PROVIDER | provider={provider_name} | status=CHECK_FAILED | exception={e}")
        
        self._logger.info(f"ARCHIVE_SEARCH_ALL_COMPLETE | url={url} | available_count={len(available_results)}")
        return available_results
    
    def check_archive(self, url: str) -> ArchiveResult:
        """
        Check archive availability across all providers with enhanced fallback logic.
        
        Collects results from all providers and selects the best archive if multiple are found.
        Uses cache to avoid redundant checks.
        
        Args:
            url: URL to check
            
        Returns:
            ArchiveResult from best provider, or aggregated result
        """
        # Check cache first
        if url in self._cache:
            cached_result = self._cache[url]
            self._logger.info(f"ARCHIVE_CACHE_HIT | url={url} | availability={cached_result.availability.value}")
            return cached_result
        
        self._logger.info(f"ARCHIVE_SEARCH | url={url}")
        
        providers_checked = []
        check_failed_count = 0
        not_available_count = 0
        environment_error_count = 0
        available_results = []  # Collect all available archives for comparison
        not_available_providers = []  # Track which providers confirmed absence
        
        # Separate high-reliability providers (Wayback, Archive.org) for parallel execution
        high_reliability_providers = []
        other_providers = []
        
        for provider in self.providers:
            provider_name = provider.get_provider_name()
            if provider_name in ['WaybackMachine', 'Archive.org', 'Arquivo.pt']:
                high_reliability_providers.append(provider)
            else:
                other_providers.append(provider)
        
        # Execute high-reliability providers in parallel with early exit on success
        if high_reliability_providers:
            from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
            
            with ThreadPoolExecutor(max_workers=len(high_reliability_providers)) as executor:
                future_to_provider = {
                    executor.submit(provider.check_archive, url): provider 
                    for provider in high_reliability_providers
                }
                
                # Early exit on first AVAILABLE result
                available_result = None
                while future_to_provider and not available_result:
                    done, pending = wait(future_to_provider.keys(), return_when=FIRST_COMPLETED)
                    
                    for future in done:
                        provider = future_to_provider.pop(future)
                        provider_name = provider.get_provider_name()
                        providers_checked.append(provider_name)
                        
                        try:
                            result = future.result()
                            
                            if result.availability == ArchiveAvailability.AVAILABLE:
                                self._logger.info(f"ARCHIVE_CANDIDATE | provider={provider_name} | url={url} | archive_url={result.archive_url} | archive_date={result.archive_date}")
                                available_results.append(result)
                                available_result = result
                                # Cancel pending futures (best-effort)
                                for p in pending:
                                    p.cancel()
                                break
                            elif result.availability == ArchiveAvailability.CHECK_FAILED:
                                check_failed_count += 1
                                self._logger.warning(f"ARCHIVE_PROVIDER | provider={provider_name} | status=CHECK_FAILED | error={result.reason}")
                            elif result.availability == ArchiveAvailability.NOT_AVAILABLE:
                                not_available_count += 1
                                not_available_providers.append(provider_name)
                                self._logger.info(f"ARCHIVE_PROVIDER | provider={provider_name} | status=NOT_AVAILABLE | reason={result.reason}")
                            elif result.availability == ArchiveAvailability.ENVIRONMENT_ERROR:
                                environment_error_count += 1
                                self._logger.error(f"ARCHIVE_PROVIDER | provider={provider_name} | status=ENVIRONMENT_ERROR | error={result.reason}")
                            else:
                                self._logger.info(f"ARCHIVE_PROVIDER | provider={provider_name} | status={result.availability.value} | reason={result.reason}")
                        except Exception as e:
                            check_failed_count += 1
                            self._logger.error(f"ARCHIVE_PROVIDER | provider={provider_name} | status=CHECK_FAILED | exception={e}")
        
        # Try other providers sequentially
        for provider in other_providers:
            provider_name = provider.get_provider_name()
            providers_checked.append(provider_name)
            
            try:
                self._logger.info(f"ARCHIVE_PROVIDER | provider={provider_name} | status=CHECKING")
                result = provider.check_archive(url)
                
                if result.availability == ArchiveAvailability.AVAILABLE:
                    self._logger.info(f"ARCHIVE_CANDIDATE | provider={provider_name} | url={url} | archive_url={result.archive_url} | archive_date={result.archive_date}")
                    available_results.append(result)
                    # Continue to check other providers - we might find a better one
                    continue
                elif result.availability == ArchiveAvailability.CHECK_FAILED:
                    check_failed_count += 1
                    self._logger.warning(f"ARCHIVE_PROVIDER | provider={provider_name} | status=CHECK_FAILED | error={result.reason}")
                    # Continue to next provider on check failure
                    continue
                elif result.availability == ArchiveAvailability.NOT_AVAILABLE:
                    not_available_count += 1
                    not_available_providers.append(provider_name)
                    self._logger.info(f"ARCHIVE_PROVIDER | provider={provider_name} | status=NOT_AVAILABLE | reason={result.reason}")
                    # Continue to next provider if no archive found
                    continue
                elif result.availability == ArchiveAvailability.ENVIRONMENT_ERROR:
                    environment_error_count += 1
                    self._logger.error(f"ARCHIVE_PROVIDER | provider={provider_name} | status=ENVIRONMENT_ERROR | error={result.reason}")
                    # Continue to next provider on environment error
                    continue
                else:
                    # ACCESS_DENIED or other statuses
                    self._logger.info(f"ARCHIVE_PROVIDER | provider={provider_name} | status={result.availability.value} | reason={result.reason}")
                    continue
                    
            except Exception as e:
                check_failed_count += 1
                self._logger.warning(f"ARCHIVE_PROVIDER | provider={provider_name} | status=EXCEPTION | error={e}")
                continue
        
        # If we found available archives, select the best one
        if available_results:
            best_result = self._select_best_archive(available_results, url)
            self._logger.info(f"ARCHIVE_SELECTED | provider={best_result.provider} | url={url} | archive_url={best_result.archive_url} | archive_date={best_result.archive_date} | confidence=high")
            # Cache the result
            self._cache[url] = best_result
            return best_result
        
        # All providers failed - determine the correct final status
        # CRITICAL: Distinguish between "no archive found" vs "providers failed technically"
        final_result = None
        
        # Provider reliability scores (higher = more reliable for confirming absence)
        provider_reliability = {
            'WaybackMachine': 5,  # Global coverage, most reliable
            'Archive.org': 4,     # Global coverage
            'Arquivo.pt': 2,      # Portugal-focused, now in parallel pool
            'CommonCrawl': 3,     # Global coverage (DISABLED)
            'UKWebArchive': 2,    # UK-focused (DISABLED)
        }
        
        # Calculate reliability-weighted decision
        total_reliability_score = sum(provider_reliability.get(p, 0) for p in not_available_providers)
        failed_providers_count = check_failed_count + environment_error_count
        
        self._logger.info(f"ARCHIVE_DECISION_METRICS | url={url} | not_available_providers={not_available_providers} | reliability_score={total_reliability_score} | failed_count={failed_providers_count} | total_providers={len(providers_checked)}")
        
        # Decision logic with reliability weighting
        if failed_providers_count == len(providers_checked):
            # All providers failed technically (503, timeout, SSL, etc.)
            # This is NOT the same as "no archive found"
            self._logger.warning(f"ARCHIVE_PROVIDER_UNAVAILABLE | url={url} | providers_checked={','.join(providers_checked)} | all_providers_failed_technically")
            final_result = ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.PROVIDER_UNAVAILABLE,
                reason=f"All archive providers failed technically ({', '.join(providers_checked)}) - cannot determine if archive exists",
                provider="ArchiveProvider"
            )
        elif not_available_count == 0:
            # No provider confirmed absence, but some failed technically
            # Cannot determine if archive exists
            self._logger.warning(f"ARCHIVE_PROVIDER_UNAVAILABLE | url={url} | providers_checked={','.join(providers_checked)} | no_provider_confirmed_absence")
            final_result = ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.PROVIDER_UNAVAILABLE,
                reason=f"No provider could confirm archive presence or absence ({', '.join(providers_checked)}) - {failed_providers_count} failed technically",
                provider="ArchiveProvider"
            )
        elif 'WaybackMachine' not in not_available_providers and 'Archive.org' not in not_available_providers:
            # Most reliable providers (Wayback, Archive.org) did not confirm absence
            # Cannot confidently declare absence even if lower-reliability providers did
            self._logger.warning(f"ARCHIVE_PROVIDER_UNAVAILABLE | url={url} | providers_checked={','.join(providers_checked)} | high_reliability_providers_did_not_confirm_absence")
            final_result = ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.PROVIDER_UNAVAILABLE,
                reason=f"High-reliability providers (Wayback, Archive.org) did not confirm absence - only {', '.join(not_available_providers)} confirmed absence, {failed_providers_count} failed technically, cannot confidently declare absence",
                provider="ArchiveProvider"
            )
        elif total_reliability_score < 3 and failed_providers_count > not_available_count:
            # Only low-reliability providers confirmed absence, and more providers failed than succeeded
            # Cannot confidently declare absence
            self._logger.warning(f"ARCHIVE_PROVIDER_UNAVAILABLE | url={url} | providers_checked={','.join(providers_checked)} | low_reliability_confirmation | reliability_score={total_reliability_score}")
            final_result = ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.PROVIDER_UNAVAILABLE,
                reason=f"Only low-reliability providers confirmed absence ({', '.join(not_available_providers)}) - {failed_providers_count} providers failed technically, cannot confidently declare absence",
                provider="ArchiveProvider"
            )
        else:
            # At least one reliable provider confirmed "no archive found" (NOT_AVAILABLE)
            # This means the archive truly doesn't exist
            self._logger.warning(f"ARCHIVE_NOT_FOUND | url={url} | providers_checked={','.join(providers_checked)} | not_available_providers={','.join(not_available_providers)} | reliability_score={total_reliability_score} | check_failed_count={check_failed_count} | environment_error_count={environment_error_count}")
            final_result = ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.NOT_AVAILABLE,
                reason=f"No archive found in any provider ({', '.join(providers_checked)}) - {not_available_count} providers confirmed absence ({', '.join(not_available_providers)}), {check_failed_count} failed technically, {environment_error_count} environment errors",
                provider="ArchiveProvider"
            )
        
        # Cache the result
        self._cache[url] = final_result
        return final_result
    
    def _select_best_archive(self, available_results: List[ArchiveResult], url: str) -> ArchiveResult:
        """
        Select the best archive from multiple available results.
        
        Selection criteria:
        1. Prefer archives with direct archive URLs (Common Crawl has None)
        2. Prefer more recent dates
        3. Prefer trusted providers (Wayback > Arquivo > UKWA > CommonCrawl)
        
        Args:
            available_results: List of available archive results
            url: Original URL (for logging)
            
        Returns:
            Best archive result
        """
        if not available_results:
            raise ValueError("No available results to select from")
        
        if len(available_results) == 1:
            return available_results[0]
        
        self._logger.info(f"ARCHIVE_SELECTION | url={url} | candidates={len(available_results)}")
        
        # Filter out results without archive URLs (like Common Crawl)
        with_urls = [r for r in available_results if r.archive_url]
        
        if with_urls:
            # Prefer archives with direct URLs
            candidates = with_urls
        else:
            # Fall back to all results if none have URLs
            candidates = available_results
        
        # Provider priority (higher = better)
        provider_priority = {
            'WaybackMachine': 4,
            'Arquivo.pt': 3,
            'UKWebArchive': 2,
            'Archive.org': 2,
            'CommonCrawl': 1
        }
        
        # Sort by provider priority, then by date (most recent first)
        candidates.sort(
            key=lambda r: (
                provider_priority.get(r.provider, 0),
                r.archive_date or ''
            ),
            reverse=True
        )
        
        best = candidates[0]
        self._logger.info(f"ARCHIVE_BEST_SELECTED | url={url} | provider={best.provider} | archive_date={best.archive_date} | reason=highest_priority_and_most_recent")
        
        return best
    
    def get_content_snapshot(self, url: str, provider_name: str = None) -> Optional[str]:
        """
        Get content snapshot from archive.
        
        Args:
            url: Original URL
            provider_name: Specific provider to use (optional)
            
        Returns:
            Content snapshot or None if not available
        """
        if provider_name:
            for provider in self.providers:
                if provider.get_provider_name() == provider_name:
                    return provider.get_content_snapshot(url)
        
        # Try all providers
        for provider in self.providers:
            try:
                content = provider.get_content_snapshot(url)
                if content:
                    return content
            except Exception as e:
                self._logger.warning(f"Provider {provider.get_provider_name()} failed: {e}")
                continue
        
        return None
    
    def verify_content_match(self, original_url: str, candidate_url: str) -> Dict[str, Any]:
        """
        Use archives to verify content match between original and candidate URLs.
        
        This is a RESEARCH/VERIFICATION function, not a replacement function.
        
        Args:
            original_url: Original dead URL
            candidate_url: Candidate replacement URL
            
        Returns:
            Dictionary with verification evidence
        """
        evidence = {
            'original_archive_available': False,
            'candidate_archive_available': False,
            'original_title': None,
            'candidate_title': None,
            'original_content_available': False,
            'candidate_content_available': False
        }
        
        # Check archive for original URL
        original_archive = self.check_archive(original_url)
        if original_archive.availability == ArchiveAvailability.AVAILABLE:
            evidence['original_archive_available'] = True
            evidence['original_archive_url'] = original_archive.archive_url
            evidence['original_archive_date'] = original_archive.archive_date
            
            # Try to get content
            original_content = self.get_content_snapshot(original_url)
            if original_content:
                evidence['original_content_available'] = True
                # Extract title (simplified)
                evidence['original_title'] = self._extract_title(original_content)
        
        # Check archive for candidate URL (if it was previously archived)
        candidate_archive = self.check_archive(candidate_url)
        if candidate_archive.availability == ArchiveAvailability.AVAILABLE:
            evidence['candidate_archive_available'] = True
            evidence['candidate_archive_url'] = candidate_archive.archive_url
            
            # Try to get content
            candidate_content = self.get_content_snapshot(candidate_url)
            if candidate_content:
                evidence['candidate_content_available'] = True
                evidence['candidate_title'] = self._extract_title(candidate_content)
        
        return evidence
    
    def _extract_title(self, html_content: str) -> Optional[str]:
        """
        Extract title from HTML content.
        
        Args:
            html_content: HTML content
            
        Returns:
            Title or None if not found
        """
        import re
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            return title_match.group(1).strip()
        return None