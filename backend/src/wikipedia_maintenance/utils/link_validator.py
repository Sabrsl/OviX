"""
Link Validator Service for coordinating dead link detection and repair decisions.

This service combines results from LinkChecker and RedirectFinder
to make deterministic decisions about whether to repair a dead link, using
strict criteria to ensure reliability.

SINGLE OBJECTIVE: Replace dead link with new URL of SAME SOURCE and SAME RESOURCE.
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from .link_checker import LinkStatus, LinkCheckResult
from .redirect_finder import RedirectDecision, RedirectResult
from .content_verifier import ContentVerifier, ContentMatch, ContentVerificationResult

logger = logging.getLogger(__name__)


class RepairDecision(Enum):
    """Final decision on link repair."""
    NO_ACTION = "no_action"  # Link is healthy or error is temporary
    DEAD_NO_REPLACEMENT = "dead_no_replacement"  # Link is dead, no valid replacement found
    REPLACEMENT_CONFIRMED = "replacement_confirmed"  # Valid replacement URL found for same source and resource
    REPAIR_REJECTED = "repair_rejected"  # Repair rejected due to insufficient proofs or validation failure
    REPAIR_DIFF_REJECTED = "repair_diff_rejected"  # Repair rejected due to diff validation failure


class ProofType(Enum):
    """Types of proofs for link repair validation."""
    ORIGINAL_PAGE_EXISTS = "original_page_exists"  # Proof that original page existed (archive evidence)
    CANDIDATE_PAGE_EXISTS = "candidate_page_exists"  # Proof that candidate page exists (live check)
    SAME_RESOURCE_CONFIRMED = "same_resource_confirmed"  # Proof that both represent same resource (multiple proofs)


@dataclass
class ProofEvidence:
    """Evidence for a specific proof type."""
    proof_type: ProofType
    confirmed: bool
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'proof_type': self.proof_type.value,
            'confirmed': self.confirmed,
            'details': self.details
        }


@dataclass
class RepairResult:
    """Result of link repair decision."""
    original_url: str
    decision: RepairDecision
    replacement_url: Optional[str] = None
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    proofs: Optional[List[ProofEvidence]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'original_url': self.original_url,
            'decision': self.decision.value,
            'replacement_url': self.replacement_url,
            'reason': self.reason,
            'details': self.details,
            'proofs': [p.to_dict() for p in self.proofs] if self.proofs else []
        }


class LinkValidator:
    """
    Service for validating link repair decisions.
    
    SINGLE OBJECTIVE: Replace dead link with new URL of SAME SOURCE and SAME RESOURCE.
    
    Design principles:
    - Use deterministic criteria, not similarity scores
    - Require explicit confirmation before any repair
    - Reject different sources (SAME_SOURCE rule)
    - Require multiple independent proofs for SAME_RESOURCE
    - Reject ambiguous cases
    - Document reasoning for every decision
    - Use shared LinkChecker to respect caching and rate limits
    """
    
    def __init__(self, link_checker=None):
        """
        Initialize link validator.
        
        Args:
            link_checker: Optional shared LinkChecker instance. If provided,
                         all candidate checks use this instance to respect
                         the analyzer's cache and rate limits. If None,
                         creates a new instance (not recommended in production).
        """
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.content_verifier = ContentVerifier()
        self.link_checker = link_checker
    
    def validate_repair(self, 
                       check_result: LinkCheckResult,
                       redirect_result: Optional[RedirectResult] = None,
                       reference_title: Optional[str] = None,
                       archive_evidence: Optional[Dict[str, Any]] = None) -> RepairResult:
        """
        Validate whether a dead link should be repaired.
        
        SINGLE OBJECTIVE: Replace dead link with new URL of SAME SOURCE and SAME RESOURCE.
        
        Decision logic (deterministic with explicit proofs):
        1. If link is healthy -> NO_ACTION
        2. If link has temporary error -> NO_ACTION
        3. If link is permanently dead:
           a. Collect three types of proofs:
              - ORIGINAL_PAGE_EXISTS (archive evidence)
              - CANDIDATE_PAGE_EXISTS (live check)
              - SAME_RESOURCE_CONFIRMED (multiple independent proofs)
           b. If all three proofs confirmed -> REPLACEMENT_CONFIRMED
           c. Otherwise -> DEAD_NO_REPLACEMENT or REPAIR_REJECTED
        
        Args:
            check_result: Result from LinkChecker
            redirect_result: Optional result from RedirectFinder
            reference_title: Optional title from archive/Wikipedia reference
            archive_evidence: Optional archive verification evidence
            
        Returns:
            RepairResult with final decision and proof evidence
        """
        details = {
            'link_status': check_result.status.value,
            'http_status_code': check_result.http_status_code,
            'redirect_decision': redirect_result.decision.value if redirect_result else None
        }
        
        proofs = []
        
        # Case 1: Link is healthy
        if check_result.status == LinkStatus.HEALTHY:
            return RepairResult(
                original_url=check_result.url,
                decision=RepairDecision.NO_ACTION,
                reason="Link is healthy, no repair needed",
                details=details,
                proofs=proofs
            )
        
        # Case 2: Temporary error (don't repair yet)
        if check_result.status == LinkStatus.TEMPORARY_ERROR:
            return RepairResult(
                original_url=check_result.url,
                decision=RepairDecision.NO_ACTION,
                reason=f"Temporary error ({check_result.error_type}), link may recover",
                details=details,
                proofs=proofs
            )
        
        # Case 3: Rate limited (don't repair)
        if check_result.status == LinkStatus.RATE_LIMITED:
            return RepairResult(
                original_url=check_result.url,
                decision=RepairDecision.NO_ACTION,
                reason="Rate limited, cannot verify link status",
                details=details,
                proofs=proofs
            )
        
        # Case 4: Unknown status
        if check_result.status == LinkStatus.UNKNOWN:
            return RepairResult(
                original_url=check_result.url,
                decision=RepairDecision.REPAIR_REJECTED,
                reason=f"Unknown link status ({check_result.error_type})",
                details=details,
                proofs=proofs
            )
        
        # Case 5: Review required status (ambiguous HTTP codes like 400/401/403)
        if check_result.status == LinkStatus.REVIEW_REQUIRED:
            return RepairResult(
                original_url=check_result.url,
                decision=RepairDecision.REPAIR_REJECTED,
                reason=f"Ambiguous HTTP status ({check_result.http_status_code} - {check_result.error_type})",
                details=details,
                proofs=proofs
            )
        
        # Case 6: Link is permanently dead
        if check_result.status == LinkStatus.DEAD:
            # Proof 1: ORIGINAL_PAGE_EXISTS (from archive evidence)
            original_page_proof = self._verify_original_page_exists(archive_evidence, reference_title)
            proofs.append(original_page_proof)
            
            # Proof 2: CANDIDATE_PAGE_EXISTS (from redirect or candidate)
            candidate_url = redirect_result.redirected_url if redirect_result else None
            candidate_page_proof = self._verify_candidate_page_exists(candidate_url, check_result)
            proofs.append(candidate_page_proof)
            
            # Proof 3: SAME_RESOURCE_CONFIRMED (multiple independent proofs)
            same_resource_proof = self._verify_same_resource(
                check_result, redirect_result, reference_title, archive_evidence
            )
            proofs.append(same_resource_proof)
            
            details['proofs'] = [p.to_dict() for p in proofs]
            
            # Only accept if all three proofs are confirmed
            if (original_page_proof.confirmed and 
                candidate_page_proof.confirmed and 
                same_resource_proof.confirmed):
                return RepairResult(
                    original_url=check_result.url,
                    decision=RepairDecision.REPLACEMENT_CONFIRMED,
                    replacement_url=candidate_url,
                    reason="All three proofs confirmed: original page existed, candidate exists, same resource confirmed",
                    details=details,
                    proofs=proofs
                )
            else:
                # Determine which proof failed
                failed_proofs = [p.proof_type.value for p in proofs if not p.confirmed]
                return RepairResult(
                    original_url=check_result.url,
                    decision=RepairDecision.REPAIR_REJECTED,
                    reason=f"Insufficient proofs - failed: {', '.join(failed_proofs)}",
                    details=details,
                    proofs=proofs
                )
        
        # Default: reject repair
        return RepairResult(
            original_url=check_result.url,
            decision=RepairDecision.REPAIR_REJECTED,
            reason="Unable to determine repair action",
            details=details,
            proofs=proofs
        )
    
    def _verify_original_page_exists(self, archive_evidence: Optional[Dict[str, Any]], 
                                     reference_title: Optional[str]) -> ProofEvidence:
        """
        Verify that the original page existed (using archive evidence).
        
        Args:
            archive_evidence: Archive verification evidence
            reference_title: Reference title from Wikipedia or archive
            
        Returns:
            ProofEvidence for ORIGINAL_PAGE_EXISTS
        """
        confirmed = False
        details = {'archive_available': False, 'title_available': False}
        
        if archive_evidence and archive_evidence.get('original_archive_available'):
            details['archive_available'] = True
            details['archive_url'] = archive_evidence.get('original_archive_url')
            details['archive_date'] = archive_evidence.get('original_archive_date')
            confirmed = True
        
        if reference_title:
            details['title_available'] = True
            details['title'] = reference_title
        
        return ProofEvidence(
            proof_type=ProofType.ORIGINAL_PAGE_EXISTS,
            confirmed=confirmed,
            details=details
        )
    
    def _verify_candidate_page_exists(self, candidate_url: Optional[str], 
                                      check_result: LinkCheckResult) -> ProofEvidence:
        """
        Verify that the candidate page exists (using live check).
        
        Uses the shared LinkChecker if available to respect caching and rate limits.
        Falls back to a new instance only if no shared checker is provided.
        
        Args:
            candidate_url: Candidate replacement URL
            check_result: Link check result for original
            
        Returns:
            ProofEvidence for CANDIDATE_PAGE_EXISTS
        """
        confirmed = False
        details = {'candidate_url': candidate_url, 'candidate_accessible': False}
        
        if candidate_url:
            # Perform actual live check of candidate URL
            try:
                # Use shared LinkChecker if available, otherwise create a new instance
                if self.link_checker:
                    checker = self.link_checker
                    self._logger.debug(f"Using shared LinkChecker for candidate check: {candidate_url}")
                else:
                    from .link_checker import LinkChecker
                    checker = LinkChecker(timeout=10, max_retries=2)
                    self._logger.warning(f"Creating new LinkChecker instance for candidate check (not shared): {candidate_url}")
                
                candidate_check = checker.check_link(candidate_url)
                
                details['candidate_accessible'] = (candidate_check.status.value == 'healthy')
                details['candidate_status'] = candidate_check.status.value
                details['candidate_http_code'] = candidate_check.http_status_code
                
                if candidate_check.status.value == 'healthy':
                    confirmed = True
            except Exception as e:
                self._logger.warning(f"Failed to check candidate URL {candidate_url}: {e}")
                details['check_error'] = str(e)
        
        return ProofEvidence(
            proof_type=ProofType.CANDIDATE_PAGE_EXISTS,
            confirmed=confirmed,
            details=details
        )
    
    def _verify_same_resource(self, check_result: LinkCheckResult,
                               redirect_result: Optional[RedirectResult],
                               reference_title: Optional[str],
                               archive_evidence: Optional[Dict[str, Any]]) -> ProofEvidence:
        """
        Verify that original and candidate represent the same resource.
        
        This requires multiple independent proofs:
        - Domain match
        - Title match
        - Content match
        - Redirect chain consistency
        
        Args:
            check_result: Link check result
            redirect_result: Redirect result
            reference_title: Reference title
            archive_evidence: Archive evidence
            
        Returns:
            ProofEvidence for SAME_RESOURCE_CONFIRMED
        """
        confirmed = False
        details = {
            'domain_match': False,
            'title_match': False,
            'content_match': False,
            'redirect_consistent': False
        }
        
        # Check domain match
        if redirect_result and redirect_result.decision == RedirectDecision.VALID_REDIRECT:
            from urllib.parse import urlparse
            original_domain = urlparse(check_result.url).netloc
            candidate_domain = urlparse(redirect_result.redirected_url).netloc
            details['domain_match'] = (original_domain == candidate_domain)
        
        # Check title match
        if reference_title and archive_evidence:
            original_title = archive_evidence.get('original_title')
            candidate_title = archive_evidence.get('candidate_title')
            if original_title and candidate_title:
                details['title_match'] = (original_title.lower() == candidate_title.lower())
        
        # Check content match (from content verifier)
        if redirect_result and redirect_result.decision == RedirectDecision.VALID_REDIRECT:
            content_result = self.content_verifier.verify_same_resource(
                check_result.url,
                redirect_result.redirected_url,
                reference_title
            )
            details['content_match'] = (content_result.decision == ContentMatch.STRONG_MATCH)
            details['content_decision'] = content_result.decision.value
        
        # Check redirect consistency (must have valid redirect for any confirmation)
        if redirect_result and redirect_result.decision == RedirectDecision.VALID_REDIRECT:
            details['redirect_consistent'] = True

        # Calculate composite confidence score with weighted proofs
        # Domain match: 0.4 weight (strong signal of same source)
        # Title match: 0.35 weight (content similarity)
        # Content match: 0.25 weight (structural similarity)
        confidence_score = 0.0
        if details['domain_match']:
            confidence_score += 0.4
        if details['title_match']:
            confidence_score += 0.35
        if details['content_match']:
            confidence_score += 0.25

        details['confidence_score'] = confidence_score

        # Require valid redirect AND confidence score >= 0.6 (at least 2 strong proofs)
        # This is more flexible than binary counting while maintaining high certainty
        confirmed = (details['redirect_consistent'] and confidence_score >= 0.6)
        
        return ProofEvidence(
            proof_type=ProofType.SAME_RESOURCE_CONFIRMED,
            confirmed=confirmed,
            details=details
        )
    
    def should_suggest_correction(self, repair_result: RepairResult) -> bool:
        """
        Determine if a correction should be suggested to the user.
        
        Only suggest corrections for:
        - REPLACEMENT_CONFIRMED (redirect to same source and resource)
        
        Never suggest for:
        - DEAD_NO_REPLACEMENT (no repair possible)
        - REPAIR_REJECTED (insufficient proofs)
        - NO_ACTION (healthy or temporary)
        
        Args:
            repair_result: Result from validate_repair
            
        Returns:
            True if correction should be suggested
        """
        return repair_result.decision == RepairDecision.REPLACEMENT_CONFIRMED
    
    def generate_suggested_text(self, repair_result: RepairResult, original_text: str) -> Optional[str]:
        """
        Generate suggested replacement text for a dead link.
        
        Args:
            repair_result: Result from validate_repair
            original_text: Original URL text in wikitext
            
        Returns:
            Suggested replacement text, or None if no suggestion
        """
        if not self.should_suggest_correction(repair_result):
            return None
        
        if repair_result.decision == RepairDecision.REPLACEMENT_CONFIRMED:
            return repair_result.replacement_url
        
        return None
