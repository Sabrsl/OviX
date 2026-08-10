"""
Candidate Finder - Search for current URLs based on archived content.

This module uses archive information (title, content) to search for current
URLs that may represent the same resource as a dead link.
"""

import logging
import re
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass
from urllib.parse import urlparse

from .link_checker import LinkChecker, LinkStatus
from .archive_provider import ArchiveProvider
from .content_verifier import ContentVerifier
from .arquivo_provider import ArquivoProvider
from .commoncrawl_provider import CommonCrawlProvider

logger = logging.getLogger(__name__)


class SearchStrategy(Enum):
    """Strategy used to find candidate."""
    ARCHIVE_REDIRECT = "archive_redirect"  # Found redirect in archive history
    ARCHIVE_TITLE_SEARCH = "archive_title_search"  # Found via title search in archive
    ARCHIVE_DOMAIN_SEARCH = "archive_domain_search"  # Found via domain search in archive
    ARCHIVE_CONTENT_SEARCH = "archive_content_search"  # Found via content search in archive


@dataclass
class CandidateResult:
    """Result of candidate search."""
    original_url: str
    candidate_url: str
    strategy: SearchStrategy
    confidence: float
    evidence: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'original_url': self.original_url,
            'candidate_url': self.candidate_url,
            'strategy': self.strategy.value,
            'confidence': self.confidence,
            'evidence': self.evidence
        }


class CandidateFinder:
    """
    Find candidate replacement URLs for dead links using real archive evidence.
    
    This module uses archive snapshots to discover actual indices for finding
    the new URL, NOT pattern generation. It searches:
    - Archive redirect history (if the page was moved)
    - Title search in archives (to find pages with same title)
    - Domain search in archives (to find related pages on same domain)
    - Content search in archives (to find pages with similar content)
    
    CRITICAL: A candidate responding with HTTP 200 is NOT sufficient proof.
    The candidate must be demonstrated to represent the same resource.
    """
    
    def __init__(self, timeout: int = 10):
        """
        Initialize candidate finder.
        
        Args:
            timeout: Timeout for HTTP requests
        """
        self.timeout = timeout
        self.archive_provider = ArchiveProvider()
        self.arquivo_provider = ArquivoProvider(timeout=timeout)
        self.commoncrawl_provider = CommonCrawlProvider(timeout=timeout)
        self.link_checker = LinkChecker(timeout=timeout)
        self.content_verifier = ContentVerifier()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def find_candidates(self, dead_url: str, max_candidates: int = 3) -> List[CandidateResult]:
        """
        Find candidate replacement URLs for a dead link using archive evidence.
        
        Args:
            dead_url: Dead URL to find replacement for
            max_candidates: Maximum number of candidates to return
            
        Returns:
            List of CandidateResult sorted by confidence
        """
        candidates = []
        
        # Step 1: Check archive for original URL to get metadata
        archive_result = self.archive_provider.check_archive(dead_url)
        
        if archive_result.availability.value != 'available':
            self._logger.warning(f"No archive available for {dead_url}")
            return candidates
        
        # Step 2: Get content snapshot to extract identifiers
        content_snapshot = self.archive_provider.get_content_snapshot(dead_url)
        
        if not content_snapshot:
            self._logger.warning(f"No content snapshot available for {dead_url}")
            return candidates
        
        # Step 3: Extract identifiers from archived content
        identifiers = self._extract_identifiers(content_snapshot, archive_result)
        
        if not identifiers.get('title'):
            self._logger.warning(f"No title found in archive for {dead_url}")
            return candidates
        
        # Step 4: Search for candidates using archive-driven strategies
        # Strategy 1: Search for redirect history in archives
        redirect_candidates = self._search_archive_redirect_history(dead_url, identifiers)
        candidates.extend(redirect_candidates)
        
        # Strategy 2: Search by title in Arquivo.pt
        if identifiers.get('title'):
            title_candidates = self._search_by_title_in_archive(dead_url, identifiers)
            candidates.extend(title_candidates)
        
        # Strategy 3: Search by domain in Common Crawl
        if identifiers.get('domain'):
            domain_candidates = self._search_by_domain_in_archive(dead_url, identifiers)
            candidates.extend(domain_candidates)
        
        # Step 5: Filter candidates that are actually accessible
        accessible_candidates = []
        for candidate in candidates:
            check_result = self.link_checker.check_link(candidate.candidate_url)
            if check_result.status == LinkStatus.HEALTHY:
                candidate.evidence['http_status'] = check_result.http_status_code
                accessible_candidates.append(candidate)
            else:
                self._logger.info(f"Candidate {candidate.candidate_url} not accessible: {check_result.status.value}")
        
        # Step 6: Deduplicate and sort by confidence
        accessible_candidates = self._deduplicate_candidates(accessible_candidates)
        accessible_candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        return accessible_candidates[:max_candidates]
    
    def _extract_identifiers(self, html_content: str, archive_result) -> Dict[str, Any]:
        """
        Extract identifiers from archived HTML content.
        
        Args:
            html_content: HTML content from archive
            archive_result: Archive result with metadata
            
        Returns:
            Dictionary with extracted identifiers
        """
        identifiers = {
            'title': None,
            'author': None,
            'date': None,
            'keywords': [],
            'domain': None,
            'path': None
        }
        
        # Extract domain and path from original URL
        if archive_result.original_url:
            parsed = urlparse(archive_result.original_url)
            identifiers['domain'] = parsed.netloc
            identifiers['path'] = parsed.path
        
        # Extract title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            identifiers['title'] = title_match.group(1).strip()
        
        # Extract author
        author_match = re.search(r'<meta[^>]*name=["\']author["\'][^>]*content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        if author_match:
            identifiers['author'] = author_match.group(1)
        
        # Extract date
        date_match = re.search(r'<meta[^>]*name=["\']date["\'][^>]*content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        if date_match:
            identifiers['date'] = date_match.group(1)
        
        # Extract keywords
        keywords_match = re.search(r'<meta[^>]*name=["\']keywords["\'][^>]*content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        if keywords_match:
            keywords_text = keywords_match.group(1)
            identifiers['keywords'] = [k.strip() for k in keywords_text.split(',')]
        
        return identifiers
    
    def _search_archive_redirect_history(self, dead_url: str, identifiers: Dict[str, Any]) -> List[CandidateResult]:
        """
        Search for redirect history in archives.
        
        If the page was moved, the archive may contain multiple versions
        with different URLs. We look for patterns that indicate a redirect.
        
        Args:
            dead_url: Dead URL
            identifiers: Extracted identifiers
            
        Returns:
            List of CandidateResult
        """
        candidates = []
        
        try:
            # Search for URL in Common Crawl to get all historical versions
            cdx_results = self.commoncrawl_provider.search_by_url(dead_url, max_results=10)
            
            # Look for URL patterns that suggest redirects
            seen_urls = set()
            
            for result in cdx_results:
                if result.url != dead_url and result.url not in seen_urls:
                    # Check if this URL is on the same domain (likely a redirect)
                    parsed_dead = urlparse(dead_url)
                    parsed_candidate = urlparse(result.url)
                    
                    if parsed_dead.netloc == parsed_candidate.netloc:
                        # Same domain, potential redirect
                        seen_urls.add(result.url)
                        
                        # Check if candidate is accessible
                        check_result = self.link_checker.check_link(result.url)
                        
                        if check_result.status == LinkStatus.HEALTHY:
                            candidates.append(CandidateResult(
                                original_url=dead_url,
                                candidate_url=result.url,
                                strategy=SearchStrategy.ARCHIVE_REDIRECT,
                                confidence=0.9,  # High confidence for same-domain redirect
                                evidence={
                                    'archive_timestamp': result.timestamp,
                                    'archive_status': result.status,
                                    'domain_match': True,
                                    'http_status': check_result.http_status_code
                                }
                            ))
            
        except Exception as e:
            self._logger.error(f"Error searching archive redirect history: {e}")
        
        return candidates
    
    def _search_by_title_in_archive(self, dead_url: str, identifiers: Dict[str, Any]) -> List[CandidateResult]:
        """
        Search for candidates by title in Arquivo.pt archive.
        
        Uses Arquivo.pt's text search API to find pages with the same title.
        
        Args:
            dead_url: Dead URL
            identifiers: Extracted identifiers
            
        Returns:
            List of CandidateResult
        """
        candidates = []
        
        try:
            if not identifiers.get('title'):
                return candidates
            
            # Search by title in Arquivo.pt
            arquivo_results = self.arquivo_provider.search_by_title(
                identifiers['title'],
                domain=identifiers.get('domain'),
                max_results=10
            )
            
            for result in arquivo_results:
                # Skip if it's the same URL
                if result.url == dead_url:
                    continue
                
                # Check if it's on the same domain (higher confidence)
                parsed_dead = urlparse(dead_url)
                parsed_candidate = urlparse(result.url)
                same_domain = (parsed_dead.netloc == parsed_candidate.netloc)
                
                # Check if candidate is accessible
                check_result = self.link_checker.check_link(result.url)
                
                if check_result.status == LinkStatus.HEALTHY:
                    # Calculate confidence based on title match and domain
                    confidence = 0.8 if same_domain else 0.6
                    
                    candidates.append(CandidateResult(
                        original_url=dead_url,
                        candidate_url=result.url,
                        strategy=SearchStrategy.ARCHIVE_TITLE_SEARCH,
                        confidence=confidence,
                        evidence={
                            'title_match': identifiers['title'],
                            'archive_title': result.title,
                            'archive_timestamp': result.timestamp,
                            'domain_match': same_domain,
                            'http_status': check_result.http_status_code
                        }
                    ))
            
        except Exception as e:
            self._logger.error(f"Error searching by title in archive: {e}")
        
        return candidates
    
    def _search_by_domain_in_archive(self, dead_url: str, identifiers: Dict[str, Any]) -> List[CandidateResult]:
        """
        Search for candidates by domain in Common Crawl archive.
        
        Uses Common Crawl's domain search to find related pages on the same domain.
        
        Args:
            dead_url: Dead URL
            identifiers: Extracted identifiers
            
        Returns:
            List of CandidateResult
        """
        candidates = []
        
        try:
            if not identifiers.get('domain'):
                return candidates
            
            # Search by domain in Common Crawl
            cc_results = self.commoncrawl_provider.search_by_domain(
                identifiers['domain'],
                max_results=20
            )
            
            # Filter results that might be related to the original page
            for result in cc_results:
                # Skip if it's the same URL
                if result.url == dead_url:
                    continue
                
                # Check if path is similar (same directory structure)
                parsed_dead = urlparse(dead_url)
                parsed_candidate = urlparse(result.url)
                
                path_similarity = self._calculate_path_similarity(
                    parsed_dead.path,
                    parsed_candidate.path
                )
                
                # Only consider if path is somewhat similar
                if path_similarity > 0.3:
                    # Check if candidate is accessible
                    check_result = self.link_checker.check_link(result.url)
                    
                    if check_result.status == LinkStatus.HEALTHY:
                        candidates.append(CandidateResult(
                            original_url=dead_url,
                            candidate_url=result.url,
                            strategy=SearchStrategy.ARCHIVE_DOMAIN_SEARCH,
                            confidence=0.5 * path_similarity,  # Moderate confidence based on path similarity
                            evidence={
                                'domain_match': True,
                                'path_similarity': path_similarity,
                                'archive_timestamp': result.timestamp,
                                'http_status': check_result.http_status_code
                            }
                        ))
            
        except Exception as e:
            self._logger.error(f"Error searching by domain in archive: {e}")
        
        return candidates
    
    def _search_by_content_patterns(self, dead_url: str, content: str, identifiers: Dict[str, Any]) -> List[CandidateResult]:
        """
        Search for candidates using content patterns.
        
        Args:
            dead_url: Dead URL
            content: Archived content
            identifiers: Extracted identifiers
            
        Returns:
            List of CandidateResult
        """
        # Placeholder for content-based search
        # This would require more sophisticated content analysis
        return []
    
    def _slugify(self, text: str) -> str:
        """
        Convert text to URL-friendly slug.
        
        Args:
            text: Text to slugify
            
        Returns:
            URL-friendly slug
        """
        # Convert to lowercase
        slug = text.lower()
        
        # Replace spaces and special characters with hyphens
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s]+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        return slug
    
    def _calculate_title_confidence(self, title: str, candidate_url: str) -> float:
        """
        Calculate confidence score for title-based candidate.
        
        Args:
            title: Original title
            candidate_url: Candidate URL
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        # Base confidence for title match
        confidence = 0.7
        
        # Boost if URL contains title words
        slug = self._slugify(title)
        if slug in candidate_url.lower():
            confidence += 0.2
        
        # Cap at 1.0
        return min(confidence, 1.0)
    
    def _calculate_path_similarity(self, path1: str, path2: str) -> float:
        """
        Calculate similarity between two URL paths.
        
        Args:
            path1: First path
            path2: Second path
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Split paths into components
        components1 = [c for c in path1.split('/') if c]
        components2 = [c for c in path2.split('/') if c]
        
        if not components1 or not components2:
            return 0.0
        
        # Calculate Jaccard similarity
        set1 = set(components1)
        set2 = set(components2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _deduplicate_candidates(self, candidates: List[CandidateResult]) -> List[CandidateResult]:
        """
        Remove duplicate candidates (same candidate URL).
        
        Args:
            candidates: List of candidates
            
        Returns:
            Deduplicated list, keeping highest confidence for each URL
        """
        seen_urls = {}
        
        for candidate in candidates:
            url = candidate.candidate_url
            if url not in seen_urls or candidate.confidence > seen_urls[url].confidence:
                seen_urls[url] = candidate
        
        return list(seen_urls.values())
