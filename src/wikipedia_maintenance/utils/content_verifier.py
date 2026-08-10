"""
Content Verifier Service for validating that two URLs represent the same resource.

This service performs content-based validation by comparing page titles,
metadata, and content to ensure that a replacement URL corresponds to the
same resource as the original dead link.
"""

import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from enum import Enum
from dataclasses import dataclass

from .api_throttler import get_global_throttler
from .archive_provider import ArchiveProvider

logger = logging.getLogger(__name__)


class ContentMatch(Enum):
    """Decision on content match."""
    STRONG_MATCH = "strong_match"  # Multiple strong indicators of same resource
    WEAK_MATCH = "weak_match"  # Some indicators but not conclusive
    NO_MATCH = "no_match"  # Clearly different content
    INDETERMINATE = "indeterminate"  # Unable to determine


@dataclass
class ContentVerificationResult:
    """Result of content verification."""
    original_url: str
    candidate_url: str
    decision: ContentMatch
    title_match: bool = False
    domain_match: bool = False
    path_similarity: float = 0.0
    content_similarity: float = 0.0
    reason: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'original_url': self.original_url,
            'candidate_url': self.candidate_url,
            'decision': self.decision.value,
            'title_match': self.title_match,
            'domain_match': self.domain_match,
            'path_similarity': self.path_similarity,
            'content_similarity': self.content_similarity,
            'reason': self.reason,
            'evidence': self.evidence
        }


class ContentVerifier:
    """
    Service for content-based verification of URL equivalence.
    
    Design principles:
    - Require multiple EXPLICIT proofs of same resource (not similarity scores)
    - Reject if any strong indicator of different content
    - Compare titles, metadata, and content
    - Use deterministic criteria, not similarity scores
    - SAME_SOURCE rule: domain must match exactly
    - SAME_RESOURCE rule: require multiple independent proofs
    """
    
    USER_AGENT = "WikipediaMaintenanceTool/1.0 (Content Verifier)"
    DEFAULT_TIMEOUT = 15
    
    def __init__(self, timeout: int = None):
        """
        Initialize content verifier.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.api_throttler = get_global_throttler()
        self.archive_provider = ArchiveProvider()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def verify_same_resource(self, original_url: str, candidate_url: str, 
                            reference_title: Optional[str] = None) -> ContentVerificationResult:
        """
        Verify that candidate URL represents the same resource as original URL.
        
        Requires multiple independent proofs:
        1. HTTP redirect chain (if available)
        2. Domain and path analysis
        3. Page title comparison
        4. Content/metadata comparison
        
        Args:
            original_url: Original dead URL
            candidate_url: Candidate replacement URL
            reference_title: Title from Wikipedia reference (optional, for comparison)
            
        Returns:
            ContentVerificationResult with decision
        """
        evidence = {}
        
        # Criterion 1: Check HTTP redirect chain
        redirect_proven = self._check_redirect_chain(original_url, candidate_url)
        evidence['redirect_proven'] = redirect_proven
        
        # Criterion 2: Domain and path analysis
        domain_match, path_similarity = self._analyze_domain_path(original_url, candidate_url)
        evidence['domain_match'] = domain_match
        evidence['path_similarity'] = path_similarity
        
        # Criterion 3: Fetch and compare page titles
        title_match = self._compare_titles(original_url, candidate_url, reference_title)
        evidence['title_match'] = title_match
        
        # Criterion 4: Content/metadata comparison (if titles match)
        content_similarity = 0.0
        if title_match or domain_match:
            content_similarity = self._compare_content(original_url, candidate_url)
            evidence['content_similarity'] = content_similarity
        
        # Criterion 5: Archive verification (for additional evidence)
        archive_evidence = self.archive_provider.verify_content_match(original_url, candidate_url)
        evidence['archive_verification'] = archive_evidence
        
        # Decision logic: require multiple EXPLICIT proofs (not similarity scores)
        proofs = []
        
        # Proof 1: SAME_SOURCE - domain must match exactly
        if domain_match:
            proofs.append("SAME_SOURCE_CONFIRMED")
        
        # Proof 2: SAME_RESOURCE - HTTP redirect chain
        if redirect_proven:
            proofs.append("REDIRECT_CHAIN_CONFIRMED")
        
        # Proof 3: SAME_RESOURCE - title match (explicit boolean, not similarity)
        if title_match:
            proofs.append("TITLE_MATCH_CONFIRMED")
        
        # Proof 4: SAME_RESOURCE - content match (high threshold for explicit proof)
        if content_similarity > 0.95:
            proofs.append("CONTENT_MATCH_CONFIRMED")
        
        # Proof 5: SAME_RESOURCE - archive evidence (additional proof, not required)
        if archive_evidence.get('original_archive_available') and archive_evidence.get('original_title'):
            if title_match and archive_evidence['original_title'] == archive_evidence.get('candidate_title'):
                proofs.append("ARCHIVE_TITLE_MATCH_CONFIRMED")
        
        # Rejection criteria (any of these = immediate rejection)
        if not domain_match:
            return ContentVerificationResult(
                original_url=original_url,
                candidate_url=candidate_url,
                decision=ContentMatch.NO_MATCH,
                title_match=title_match,
                domain_match=domain_match,
                path_similarity=path_similarity,
                content_similarity=content_similarity,
                reason="Different domain - violates SAME_SOURCE rule",
                evidence=evidence
            )
        
        if path_similarity < 0.5:
            return ContentVerificationResult(
                original_url=original_url,
                candidate_url=candidate_url,
                decision=ContentMatch.NO_MATCH,
                title_match=title_match,
                domain_match=domain_match,
                path_similarity=path_similarity,
                content_similarity=content_similarity,
                reason="Path too different - likely different resource",
                evidence=evidence
            )
        
        if title_match is False and reference_title:
            return ContentVerificationResult(
                original_url=original_url,
                candidate_url=candidate_url,
                decision=ContentMatch.NO_MATCH,
                title_match=False,
                domain_match=domain_match,
                path_similarity=path_similarity,
                content_similarity=content_similarity,
                reason="Titles don't match - violates SAME_RESOURCE rule",
                evidence=evidence
            )
        
        # Require explicit proofs: SAME_SOURCE + at least one SAME_RESOURCE proof
        has_same_source = "SAME_SOURCE_CONFIRMED" in proofs
        has_same_resource = any(p in proofs for p in ["REDIRECT_CHAIN_CONFIRMED", "TITLE_MATCH_CONFIRMED", "CONTENT_MATCH_CONFIRMED"])
        
        if has_same_source and has_same_resource and len(proofs) >= 2:
            return ContentVerificationResult(
                original_url=original_url,
                candidate_url=candidate_url,
                decision=ContentMatch.STRONG_MATCH,
                title_match=title_match,
                domain_match=domain_match,
                path_similarity=path_similarity,
                content_similarity=content_similarity,
                reason=f"Explicit proofs: {', '.join(proofs)}",
                evidence=evidence
            )
        
        # Only 1 proof - weak match
        if len(proofs) == 1:
            return ContentVerificationResult(
                original_url=original_url,
                candidate_url=candidate_url,
                decision=ContentMatch.WEAK_MATCH,
                title_match=title_match,
                domain_match=domain_match,
                path_similarity=path_similarity,
                content_similarity=content_similarity,
                reason=f"Only 1 explicit proof ({proofs[0]}) - insufficient for automatic replacement",
                evidence=evidence
            )
        
        # No proofs
        return ContentVerificationResult(
            original_url=original_url,
            candidate_url=candidate_url,
            decision=ContentMatch.INDETERMINATE,
            title_match=title_match,
            domain_match=domain_match,
            path_similarity=path_similarity,
            content_similarity=content_similarity,
            reason="Insufficient explicit proofs to determine if same resource",
            evidence=evidence
        )
    
    def _check_redirect_chain(self, original_url: str, candidate_url: str) -> bool:
        """
        Check if original URL actually redirects to candidate URL.
        
        Normalizes URLs before comparison to accept legitimate variants:
        - Domain case insensitivity
        - www. prefix normalization
        - Trailing slash normalization
        
        Args:
            original_url: Original URL
            candidate_url: Candidate URL
            
        Returns:
            True if redirect chain proven
        """
        self.api_throttler.wait_if_needed()
        
        try:
            request = urllib.request.Request(
                original_url,
                headers={'User-Agent': self.USER_AGENT},
                method='HEAD'
            )
            
            context = urllib.request.ssl.create_default_context()
            response = urllib.request.urlopen(request, timeout=self.timeout, context=context)
            
            final_url = response.url
            self.api_throttler.report_success()
            
            # Normalize URLs for comparison
            def normalize_url(url: str) -> str:
                parsed = urlparse(url)
                # Lowercase domain
                netloc = parsed.netloc.lower()
                # Remove www. prefix
                netloc = netloc.replace('www.', '')
                # Reconstruct with normalized netloc and stripped trailing slash
                path = parsed.path.rstrip('/')
                return f"{parsed.scheme}://{netloc}{path}"
            
            final_normalized = normalize_url(final_url)
            candidate_normalized = normalize_url(candidate_url)
            
            return final_normalized == candidate_normalized
            
        except Exception as e:
            self._logger.warning(f"Error checking redirect chain: {e}")
            return False
    
    def _analyze_domain_path(self, original_url: str, candidate_url: str) -> tuple[bool, float]:
        """
        Analyze domain and path similarity.
        
        Args:
            original_url: Original URL
            candidate_url: Candidate URL
            
        Returns:
            Tuple of (domain_match, path_similarity_0_to_1)
        """
        orig_parsed = urlparse(original_url)
        cand_parsed = urlparse(candidate_url)
        
        # Domain match (ignoring www and protocol)
        orig_domain = orig_parsed.netloc.replace('www.', '').replace('http://', '').replace('https://', '')
        cand_domain = cand_parsed.netloc.replace('www.', '').replace('http://', '').replace('https://', '')
        
        domain_match = orig_domain == cand_domain
        
        # Path similarity
        orig_path = orig_parsed.path.rstrip('/')
        cand_path = cand_parsed.path.rstrip('/')
        
        if orig_path == cand_path:
            path_similarity = 1.0
        elif cand_path.startswith(orig_path) or orig_path.startswith(cand_path):
            # One is prefix of the other
            shorter = min(len(orig_path), len(cand_path))
            longer = max(len(orig_path), len(cand_path))
            path_similarity = shorter / longer if longer > 0 else 0.0
        else:
            # Use simple character overlap
            set_orig = set(orig_path.lower())
            set_cand = set(cand_path.lower())
            intersection = set_orig & set_cand
            union = set_orig | set_cand
            path_similarity = len(intersection) / len(union) if union else 0.0
        
        return domain_match, path_similarity
    
    def _compare_titles(self, original_url: str, candidate_url: str, 
                       reference_title: Optional[str] = None) -> Optional[bool]:
        """
        Compare page titles.
        
        Args:
            original_url: Original URL
            candidate_url: Candidate URL
            reference_title: Title from Wikipedia reference
            
        Returns:
            True if titles match, False if they don't, None if unable to determine
        """
        # Try to fetch titles from both URLs
        original_title = self._fetch_page_title(original_url)
        candidate_title = self._fetch_page_title(candidate_url)
        
        if original_title and candidate_title:
            # Normalize for comparison
            orig_norm = self._normalize_title(original_title)
            cand_norm = self._normalize_title(candidate_title)
            
            if orig_norm == cand_norm:
                return True
            else:
                return False
        
        # If we have a reference title, compare with candidate
        if reference_title and candidate_title:
            ref_norm = self._normalize_title(reference_title)
            cand_norm = self._normalize_title(candidate_title)
            
            if ref_norm == cand_norm:
                return True
            else:
                return False
        
        # Unable to determine
        return None
    
    def _fetch_page_title(self, url: str) -> Optional[str]:
        """
        Fetch page title from URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            Page title or None
        """
        self.api_throttler.wait_if_needed()
        
        try:
            request = urllib.request.Request(
                url,
                headers={'User-Agent': self.USER_AGENT},
                method='GET'
            )
            
            context = urllib.request.ssl.create_default_context()
            response = urllib.request.urlopen(request, timeout=self.timeout, context=context)
            
            # Read first few KB to find title
            content = response.read(8192).decode('utf-8', errors='ignore')
            
            # Simple title extraction
            import re
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                # Remove common suffixes
                title = re.sub(r'\s*[-|]\s.*$', '', title)
                return title
            
            self.api_throttler.report_success()
            return None
            
        except Exception as e:
            self._logger.warning(f"Error fetching title from {url}: {e}")
            return None
    
    def _normalize_title(self, title: str) -> str:
        """
        Normalize title for comparison.
        
        Args:
            title: Title to normalize
            
        Returns:
            Normalized title
        """
        import re
        # Lowercase
        title = title.lower()
        # Remove punctuation
        title = re.sub(r'[^\w\s]', '', title)
        # Remove extra whitespace
        title = ' '.join(title.split())
        return title
    
    def _compare_content(self, original_url: str, candidate_url: str) -> float:
        """
        Compare content between two URLs.
        
        This uses text similarity metrics on extracted content.
        
        Args:
            original_url: Original URL
            candidate_url: Candidate URL
            
        Returns:
            Similarity score 0.0-1.0
        """
        try:
            # Try to fetch content from both URLs
            # For original (likely dead), try archive first
            original_content = self._fetch_content_for_comparison(original_url, prefer_archive=True)
            candidate_content = self._fetch_content_for_comparison(candidate_url, prefer_archive=False)
            
            if not original_content or not candidate_content:
                return 0.0
            
            # Extract meaningful text for comparison
            original_text = self._extract_meaningful_text(original_content)
            candidate_text = self._extract_meaningful_text(candidate_content)
            
            if not original_text or not candidate_text:
                return 0.0
            
            # Calculate similarity using simple text overlap
            similarity = self._calculate_text_similarity(original_text, candidate_text)
            
            return similarity
            
        except Exception as e:
            self._logger.warning(f"Error comparing content: {e}")
            return 0.0
    
    def _fetch_content_for_comparison(self, url: str, prefer_archive: bool = False) -> Optional[str]:
        """Fetch content from URL or archive."""
        try:
            import urllib.request
            from urllib.error import URLError, HTTPError
            
            # If prefer_archive and URL might be dead, try archive first
            if prefer_archive:
                try:
                    from .archive_provider import ArchiveProvider
                    archive = ArchiveProvider()
                    archive_result = archive.check_archive(url)
                    if archive_result.availability.value == 'available' and archive_result.archive_url:
                        # Try to fetch from archive
                        content = self._fetch_http_content(archive_result.archive_url)
                        if content:
                            return content
                except Exception as e:
                    self._logger.debug(f"Archive fetch failed for {url}: {e}")
            
            # Try direct fetch
            return self._fetch_http_content(url)
            
        except Exception as e:
            self._logger.debug(f"Failed to fetch content for {url}: {e}")
            return None
    
    def _fetch_http_content(self, url: str) -> Optional[str]:
        """Fetch HTTP content from URL."""
        try:
            import urllib.request
            from urllib.error import URLError, HTTPError
            
            request = urllib.request.Request(
                url,
                headers={'User-Agent': 'WikipediaMaintenanceTool/1.0 (Content Comparison)'},
                method='GET'
            )
            
            context = urllib.request.ssl.create_default_context()
            with urllib.request.urlopen(request, timeout=10, context=context) as response:
                return response.read().decode('utf-8', errors='ignore')
                
        except (URLError, HTTPError) as e:
            self._logger.debug(f"HTTP error fetching {url}: {e}")
            return None
        except Exception as e:
            self._logger.debug(f"Error fetching {url}: {e}")
            return None
    
    def _extract_meaningful_text(self, html_content: str) -> str:
        """Extract meaningful text from HTML for comparison."""
        try:
            import re
            
            # Remove script and style tags
            html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
            html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
            
            # Extract title
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else ''
            
            # Extract first paragraph(s)
            # Look for <p> tags
            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html_content, re.IGNORECASE | re.DOTALL)
            
            # Clean HTML tags from paragraphs
            clean_paragraphs = []
            for p in paragraphs[:3]:  # Take first 3 paragraphs
                clean_p = re.sub(r'<[^>]+>', '', p)
                clean_p = ' '.join(clean_p.split())
                if len(clean_p) > 50:  # Only substantial paragraphs
                    clean_paragraphs.append(clean_p)
            
            # Extract headings
            headings = re.findall(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html_content, re.IGNORECASE | re.DOTALL)
            clean_headings = []
            for h in headings[:5]:  # Take first 5 headings
                clean_h = re.sub(r'<[^>]+>', '', h)
                clean_h = ' '.join(clean_h.split())
                if clean_h:
                    clean_headings.append(clean_h)
            
            # Combine all meaningful text
            meaningful_parts = []
            if title:
                meaningful_parts.append(title)
            if clean_headings:
                meaningful_parts.extend(clean_headings)
            if clean_paragraphs:
                meaningful_parts.extend(clean_paragraphs)
            
            combined_text = ' '.join(meaningful_parts)
            return combined_text.strip()
            
        except Exception as e:
            self._logger.debug(f"Error extracting meaningful text: {e}")
            return ''
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using simple overlap metric."""
        try:
            if not text1 or not text2:
                return 0.0
            
            # Convert to lowercase and tokenize
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            
            if not words1 or not words2:
                return 0.0
            
            # Calculate Jaccard similarity
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            if not union:
                return 0.0
            
            similarity = len(intersection) / len(union)
            
            # Also check for significant word overlap in one direction
            overlap_in_1 = len(words1.intersection(words2)) / len(words1) if words1 else 0
            overlap_in_2 = len(words1.intersection(words2)) / len(words2) if words2 else 0
            
            # Use the maximum of the three metrics
            return max(similarity, overlap_in_1, overlap_in_2)
            
        except Exception as e:
            self._logger.debug(f"Error calculating similarity: {e}")
            return 0.0
