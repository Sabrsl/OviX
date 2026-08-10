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

from .api_throttler import get_global_throttler

logger = logging.getLogger(__name__)


class ArchiveAvailability(Enum):
    """Availability status of archive."""
    AVAILABLE = "available"  # Archive exists and is accessible
    NOT_AVAILABLE = "not_available"  # No archive found
    CHECK_FAILED = "check_failed"  # Archive check failed (network, API error)
    ACCESS_DENIED = "access_denied"  # Archive exists but access denied


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
        self.api_throttler = get_global_throttler()
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
            self._logger.warning(f"HTTP error for {url}: {e.code}")
            return None
        except urllib.error.URLError as e:
            self._logger.warning(f"URL error for {url}: {e.reason}")
            return None
        except Exception as e:
            self._logger.error(f"Unexpected error for {url}: {e}")
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
        cdx_url = f"{self.CDX_API_URL}?url={clean_url}&output=json&limit=1"
        
        # Retry logic for timeout cases
        max_retries = 2
        for attempt in range(max_retries):
            response = self._make_request(cdx_url)
            
            if response:
                break  # Success, exit retry loop
            
            if attempt < max_retries - 1:
                self._logger.warning(f"Wayback API request failed (attempt {attempt + 1}/{max_retries}), retrying...")
                import time
                time.sleep(2)  # Wait before retry
            else:
                self._logger.error(f"Wayback API request failed after {max_retries} attempts")
        
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
        
        return self._make_request(archive_url)
    
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
        
        # Retry logic for timeout cases
        max_retries = 2
        for attempt in range(max_retries):
            response = self._make_request(search_url)
            
            if response:
                break  # Success, exit retry loop
            
            if attempt < max_retries - 1:
                self._logger.warning(f"Archive.org API request failed (attempt {attempt + 1}/{max_retries}), retrying...")
                import time
                time.sleep(2)  # Wait before retry
            else:
                self._logger.error(f"Archive.org API request failed after {max_retries} attempts")
        
        if not response:
            return ArchiveResult(
                original_url=url,
                availability=ArchiveAvailability.CHECK_FAILED,
                reason="Archive.org search API request failed after retries",
                provider=self.get_provider_name()
            )
        
        try:
            data = json.loads(response)
            
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
        return self._make_request(archive_url)
    
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


class ArchiveProvider:
    """
    Main archive provider that coordinates multiple archive services.
    
    This provider is used for:
    - RESEARCH AND VERIFICATION (primary use)
    - AUTOMATIC LINK REPLACEMENT as fallback when no redirect is available (secondary use)
    
    Coordinates multiple archive services (Wayback Machine, Archive.org, etc.)
    with retry logic and enhanced fallback capabilities.
    """
    
    def __init__(self):
        """Initialize archive provider with available services."""
        self.providers = [
            WaybackProvider(),
            ArchiveOrgProvider(),  # Additional archive.org direct search
            # Future: CommonCrawlProvider(), etc.
        ]
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def check_archive(self, url: str) -> ArchiveResult:
        """
        Check archive availability across all providers with enhanced fallback logic.
        
        Args:
            url: URL to check
            
        Returns:
            ArchiveResult from first successful provider
        """
        # Try each provider in order
        for provider in self.providers:
            try:
                self._logger.info(f"Trying provider {provider.get_provider_name()} for {url}")
                result = provider.check_archive(url)
                
                if result.availability == ArchiveAvailability.AVAILABLE:
                    self._logger.info(f"Archive found via {provider.get_provider_name()}: {result.archive_url}")
                    return result
                elif result.availability == ArchiveAvailability.CHECK_FAILED:
                    self._logger.warning(f"Provider {provider.get_provider_name()} check failed: {result.reason}")
                    # Continue to next provider on check failure
                    continue
                else:
                    self._logger.info(f"Provider {provider.get_provider_name()} found no archive: {result.reason}")
                    # Continue to next provider if no archive found
                    continue
                    
            except Exception as e:
                self._logger.warning(f"Provider {provider.get_provider_name()} failed with exception: {e}")
                continue
        
        # All providers failed
        self._logger.warning(f"No archive found for {url} in any provider")
        return ArchiveResult(
            original_url=url,
            availability=ArchiveAvailability.NOT_AVAILABLE,
            reason="No archive found in any provider (Wayback, Archive.org)",
            provider="ArchiveProvider"
        )
    
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
