"""
Unit tests for LinkValidator - fail-closed behavior verification.

These tests verify that the LinkValidator correctly rejects repairs
when proofs are insufficient, ensuring fail-closed behavior.
"""

import pytest
from src.wikipedia_maintenance.utils.link_validator import (
    LinkValidator,
    RepairDecision,
    ProofType,
    ProofEvidence,
    RepairResult
)
from src.wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult
from src.wikipedia_maintenance.utils.redirect_finder import RedirectDecision, RedirectResult


class TestLinkValidatorFailClosed:
    """Test fail-closed behavior of LinkValidator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = LinkValidator()
    
    def test_healthy_link_no_action(self):
        """Test that healthy links result in NO_ACTION."""
        check_result = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            error_type=None
        )
        
        result = self.validator.validate_repair(check_result)
        
        assert result.decision == RepairDecision.NO_ACTION
        assert "healthy" in result.reason.lower()
    
    def test_temporary_error_no_action(self):
        """Test that temporary errors result in NO_ACTION."""
        check_result = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.TEMPORARY_ERROR,
            http_status_code=503,
            error_type="Service Unavailable"
        )
        
        result = self.validator.validate_repair(check_result)
        
        assert result.decision == RepairDecision.NO_ACTION
        assert "temporary" in result.reason.lower()
    
    def test_rate_limited_no_action(self):
        """Test that rate limited links result in NO_ACTION."""
        check_result = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.RATE_LIMITED,
            http_status_code=429,
            error_type="Too Many Requests"
        )
        
        result = self.validator.validate_repair(check_result)
        
        assert result.decision == RepairDecision.NO_ACTION
        assert "rate limited" in result.reason.lower()
    
    def test_unknown_status_rejected(self):
        """Test that unknown status results in REPAIR_REJECTED."""
        check_result = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.UNKNOWN,
            http_status_code=None,
            error_type="Unknown error"
        )
        
        result = self.validator.validate_repair(check_result)
        
        assert result.decision == RepairDecision.REPAIR_REJECTED
        assert "unknown" in result.reason.lower()
    
    def test_review_required_rejected(self):
        """Test that ambiguous HTTP codes result in REPAIR_REJECTED."""
        check_result = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.REVIEW_REQUIRED,
            http_status_code=403,
            error_type="Forbidden"
        )
        
        result = self.validator.validate_repair(check_result)
        
        assert result.decision == RepairDecision.REPAIR_REJECTED
        assert "ambiguous" in result.reason.lower()
    
    def test_dead_link_no_redirect_no_replacement(self):
        """Test that dead links without redirect result in DEAD_NO_REPLACEMENT."""
        check_result = LinkCheckResult(
            url="https://example.com/dead-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        result = self.validator.validate_repair(check_result)
        
        assert result.decision == RepairDecision.DEAD_NO_REPLACEMENT
        assert "no valid replacement" in result.reason.lower()
    
    def test_dead_link_invalid_redirect_rejected(self):
        """Test that dead links with invalid redirect result in REPAIR_REJECTED."""
        check_result = LinkCheckResult(
            url="https://example.com/dead-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        redirect_result = RedirectResult(
            original_url="https://example.com/dead-article",
            redirected_url="https://different-domain.com/article",
            decision=RedirectDecision.INVALID_REDIRECT,
            redirect_chain=[],
            reason="Different domain"
        )
        
        result = self.validator.validate_repair(check_result, redirect_result)
        
        assert result.decision == RepairDecision.REPAIR_REJECTED
        assert "invalid" in result.reason.lower()
    
    def test_dead_link_insufficient_proofs_rejected(self):
        """Test that dead links with insufficient proofs result in REPAIR_REJECTED."""
        check_result = LinkCheckResult(
            url="https://example.com/dead-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        redirect_result = RedirectResult(
            original_url="https://example.com/dead-article",
            redirected_url="https://example.com/new-article",
            decision=RedirectDecision.VALID_REDIRECT,
            redirect_chain=[],
            reason="Valid redirect"
        )
        
        # No archive evidence, no reference title
        result = self.validator.validate_repair(
            check_result, 
            redirect_result,
            reference_title=None,
            archive_evidence=None
        )
        
        # Should be rejected due to insufficient proofs
        assert result.decision == RepairDecision.REPAIR_REJECTED
        assert "insufficient proofs" in result.reason.lower()
    
    def test_proof_evidence_structure(self):
        """Test that proof evidence is properly structured."""
        check_result = LinkCheckResult(
            url="https://example.com/dead-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        result = self.validator.validate_repair(check_result)
        
        # Verify proofs list exists
        assert result.proofs is not None
        assert isinstance(result.proofs, list)
        
        # Verify each proof has correct structure
        for proof in result.proofs:
            assert isinstance(proof, ProofEvidence)
            assert hasattr(proof, 'proof_type')
            assert hasattr(proof, 'confirmed')
            assert hasattr(proof, 'details')
    
    def test_original_page_proof_without_archive(self):
        """Test that original page proof fails without archive evidence."""
        check_result = LinkCheckResult(
            url="https://example.com/dead-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        proof = self.validator._verify_original_page_exists(
            archive_evidence=None,
            reference_title=None
        )
        
        assert proof.proof_type == ProofType.ORIGINAL_PAGE_EXISTS
        assert proof.confirmed == False
        assert proof.details['archive_available'] == False
    
    def test_original_page_proof_with_archive(self):
        """Test that original page proof succeeds with archive evidence."""
        archive_evidence = {
            'original_archive_available': True,
            'original_archive_url': 'https://web.archive.org/web/20200101/https://example.com/article',
            'original_archive_date': '20200101'
        }
        
        proof = self.validator._verify_original_page_exists(
            archive_evidence=archive_evidence,
            reference_title="Test Article"
        )
        
        assert proof.proof_type == ProofType.ORIGINAL_PAGE_EXISTS
        assert proof.confirmed == True
        assert proof.details['archive_available'] == True
        assert proof.details['title_available'] == True
    
    def test_candidate_page_proof_without_url(self):
        """Test that candidate page proof fails without candidate URL."""
        check_result = LinkCheckResult(
            url="https://example.com/dead-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        proof = self.validator._verify_candidate_page_exists(
            candidate_url=None,
            check_result=check_result
        )
        
        assert proof.proof_type == ProofType.CANDIDATE_PAGE_EXISTS
        assert proof.confirmed == False
        assert proof.details['candidate_accessible'] == False
    
    def test_candidate_page_proof_with_url(self):
        """Test that candidate page proof succeeds with candidate URL."""
        check_result = LinkCheckResult(
            url="https://example.com/dead-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        proof = self.validator._verify_candidate_page_exists(
            candidate_url="https://example.com/new-article",
            check_result=check_result
        )
        
        assert proof.proof_type == ProofType.CANDIDATE_PAGE_EXISTS
        assert proof.confirmed == True
        assert proof.details['candidate_accessible'] == True
    
    def test_same_resource_proof_insufficient_evidence(self):
        """Test that same resource proof fails with insufficient evidence."""
        check_result = LinkCheckResult(
            url="https://example.com/dead-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        redirect_result = RedirectResult(
            original_url="https://example.com/dead-article",
            redirected_url="https://example.com/new-article",
            decision=RedirectDecision.VALID_REDIRECT,
            redirect_chain=[],
            reason="Valid redirect"
        )
        
        proof = self.validator._verify_same_resource(
            check_result=check_result,
            redirect_result=redirect_result,
            reference_title=None,
            archive_evidence=None
        )
        
        assert proof.proof_type == ProofType.SAME_RESOURCE_CONFIRMED
        # Should fail due to insufficient evidence (only redirect_consistent is True)
        assert proof.confirmed == False
    
    def test_same_resource_proof_sufficient_evidence(self):
        """Test that same resource proof succeeds with sufficient evidence."""
        check_result = LinkCheckResult(
            url="https://example.com/dead-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        redirect_result = RedirectResult(
            original_url="https://example.com/dead-article",
            redirected_url="https://example.com/new-article",
            decision=RedirectDecision.VALID_REDIRECT,
            redirect_chain=[],
            reason="Valid redirect"
        )
        
        archive_evidence = {
            'original_title': 'Test Article',
            'candidate_title': 'Test Article'
        }
        
        proof = self.validator._verify_same_resource(
            check_result=check_result,
            redirect_result=redirect_result,
            reference_title='Test Article',
            archive_evidence=archive_evidence
        )
        
        assert proof.proof_type == ProofType.SAME_RESOURCE_CONFIRMED
        # Should succeed with domain_match, title_match, redirect_consistent
        assert proof.confirmed == True


class TestLinkValidatorProofRequirements:
    """Test that all three proofs are required for repair."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = LinkValidator()
    
    def test_all_proofs_required_for_replacement(self):
        """Test that all three proofs must be confirmed for replacement."""
        check_result = LinkCheckResult(
            url="https://example.com/dead-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        redirect_result = RedirectResult(
            original_url="https://example.com/dead-article",
            redirected_url="https://example.com/new-article",
            decision=RedirectDecision.VALID_REDIRECT,
            redirect_chain=[],
            reason="Valid redirect"
        )
        
        # Test with no archive evidence (original page proof fails)
        result = self.validator.validate_repair(
            check_result,
            redirect_result,
            reference_title=None,
            archive_evidence=None
        )
        
        assert result.decision != RepairDecision.REPLACEMENT_CONFIRMED
        
        # Test with archive evidence but no title match
        archive_evidence = {
            'original_archive_available': True,
            'original_archive_url': 'https://web.archive.org/web/20200101/https://example.com/article',
            'original_archive_date': '20200101',
            'original_title': 'Different Title',
            'candidate_title': 'Test Article'
        }
        
        result = self.validator.validate_repair(
            check_result,
            redirect_result,
            reference_title='Different Title',
            archive_evidence=archive_evidence
        )
        
        # Should still be rejected due to title mismatch
        assert result.decision != RepairDecision.REPLACEMENT_CONFIRMED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
