"""
Fail-Closed Regression Tests for DeadLinkAnalyzer.

These tests verify that the DeadLinkAnalyzer NEVER makes automatic repairs
when conditions are not met, ensuring fail-closed behavior.

Critical scenarios that must result in NO_REPAIR:
- API unavailable
- Ambiguous candidates
- Insufficient proofs
- Multiple equally plausible candidates
- Contradictory evidence
- Incomplete analysis
- Bad candidate
- Different domain
- Different title
- Content mismatch
"""

import pytest
from unittest.mock import Mock, patch
from src.wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
from src.wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult
from src.wikipedia_maintenance.utils.redirect_finder import RedirectDecision, RedirectResult
from src.wikipedia_maintenance.utils.link_validator import RepairDecision


class TestFailClosedAPIUnavailable:
    """Test that API unavailability results in NO_REPAIR."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = DeadLinkAnalyzer()
        self.analyzer.enable_auto_repair = True
    
    @patch('src.wikipedia_maintenance.analyzers.dead_links.ArchiveProvider')
    def test_archive_api_timeout_no_repair(self, mock_archive_provider):
        """Test that archive API timeout results in NO_REPAIR."""
        # Mock archive provider to timeout
        mock_archive_provider.return_value.check_archive.side_effect = TimeoutError("API timeout")
        
        content = "Test content with https://example.com/dead-link"
        
        issues = self.analyzer.analyze(content)
        
        # Should not repair when archive API times out
        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
        assert len(repair_issues) == 0
    
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkChecker')
    def test_link_checker_timeout_no_repair(self, mock_link_checker):
        """Test that link checker timeout results in NO_REPAIR."""
        # Mock link checker to timeout
        mock_link_checker.return_value.check_link.side_effect = TimeoutError("Connection timeout")
        
        content = "Test content with https://example.com/dead-link"
        
        issues = self.analyzer.analyze(content)
        
        # Should not repair when link checker times out
        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
        assert len(repair_issues) == 0


class TestFailClosedAmbiguousCandidates:
    """Test that ambiguous candidates result in NO_REPAIR."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = DeadLinkAnalyzer()
        self.analyzer.enable_auto_repair = True
    
    @patch('src.wikipedia_maintenance.analyzers.dead_links.CandidateFinder')
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkChecker')
    def test_multiple_candidates_no_repair(self, mock_link_checker, mock_candidate_finder):
        """Test that multiple candidates result in NO_REPAIR."""
        # Mock multiple candidates with similar confidence
        from src.wikipedia_maintenance.utils.candidate_finder import CandidateResult, SearchStrategy
        
        candidates = [
            CandidateResult(
                original_url="https://example.com/dead",
                candidate_url="https://example.com/candidate1",
                strategy=SearchStrategy.TITLE_SEARCH,
                confidence=0.8,
                evidence={}
            ),
            CandidateResult(
                original_url="https://example.com/dead",
                candidate_url="https://example.com/candidate2",
                strategy=SearchStrategy.TITLE_SEARCH,
                confidence=0.8,
                evidence={}
            )
        ]
        
        mock_candidate_finder.return_value.find_candidates.return_value = candidates
        
        # Mock link checker to return healthy for candidates
        mock_link_checker.return_value.check_link.return_value = LinkCheckResult(
            url="https://example.com/candidate1",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            error_type=None
        )
        
        # Mock dead link
        mock_link_checker.return_value.check_link.side_effect = [
            LinkCheckResult(
                url="https://example.com/dead",
                status=LinkStatus.DEAD,
                http_status_code=404,
                error_type="Not Found"
            ),
            LinkCheckResult(
                url="https://example.com/candidate1",
                status=LinkStatus.HEALTHY,
                http_status_code=200,
                error_type=None
            )
        ]
        
        content = "Test content with https://example.com/dead"
        
        issues = self.analyzer.analyze(content)
        
        # Should not repair when multiple candidates exist
        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
        assert len(repair_issues) == 0


class TestFailClosedInsufficientProofs:
    """Test that insufficient proofs result in NO_REPAIR."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = DeadLinkAnalyzer()
        self.analyzer.enable_auto_repair = True
    
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkValidator')
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkChecker')
    def test_no_archive_evidence_no_repair(self, mock_link_checker, mock_validator):
        """Test that missing archive evidence results in NO_REPAIR."""
        # Mock validator to reject due to insufficient proofs
        from src.wikipedia_maintenance.utils.link_validator import RepairResult
        
        mock_validator.return_value.validate_repair.return_value = RepairResult(
            original_url="https://example.com/dead",
            decision=RepairDecision.REPAIR_REJECTED,
            reason="Insufficient proofs - failed: original_page_exists"
        )
        
        # Mock dead link
        mock_link_checker.return_value.check_link.return_value = LinkCheckResult(
            url="https://example.com/dead",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        content = "Test content with https://example.com/dead"
        
        issues = self.analyzer.analyze(content)
        
        # Should not repair without archive evidence
        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
        assert len(repair_issues) == 0
    
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkValidator')
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkChecker')
    def test_no_title_match_no_repair(self, mock_link_checker, mock_validator):
        """Test that missing title match results in NO_REPAIR."""
        # Mock validator to reject due to missing title match
        from src.wikipedia_maintenance.utils.link_validator import RepairResult
        
        mock_validator.return_value.validate_repair.return_value = RepairResult(
            original_url="https://example.com/dead",
            decision=RepairDecision.REPAIR_REJECTED,
            reason="Insufficient proofs - failed: same_resource_confirmed"
        )
        
        # Mock dead link
        mock_link_checker.return_value.check_link.return_value = LinkCheckResult(
            url="https://example.com/dead",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        content = "Test content with https://example.com/dead"
        
        issues = self.analyzer.analyze(content)
        
        # Should not repair without title match
        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
        assert len(repair_issues) == 0


class TestFailClosedBadCandidate:
    """Test that bad candidates result in NO_REPAIR."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = DeadLinkAnalyzer()
        self.analyzer.enable_auto_repair = True
    
    @patch('src.wikipedia_maintenance.analyzers.dead_links.CandidateFinder')
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkChecker')
    def test_candidate_different_domain_no_repair(self, mock_link_checker, mock_candidate_finder):
        """Test that candidate on different domain results in NO_REPAIR."""
        from src.wikipedia_maintenance.utils.candidate_finder import CandidateResult, SearchStrategy
        
        # Candidate on different domain
        candidates = [
            CandidateResult(
                original_url="https://example.com/dead",
                candidate_url="https://different-domain.com/article",
                strategy=SearchStrategy.TITLE_SEARCH,
                confidence=0.8,
                evidence={}
            )
        ]
        
        mock_candidate_finder.return_value.find_candidates.return_value = candidates
        
        # Mock dead link
        mock_link_checker.return_value.check_link.return_value = LinkCheckResult(
            url="https://example.com/dead",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        content = "Test content with https://example.com/dead"
        
        issues = self.analyzer.analyze(content)
        
        # Should not repair for different domain
        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
        assert len(repair_issues) == 0
    
    @patch('src.wikipedia_maintenance.analyzers.dead_links.CandidateFinder')
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkChecker')
    def test_candidate_unhealthy_no_repair(self, mock_link_checker, mock_candidate_finder):
        """Test that unhealthy candidate results in NO_REPAIR."""
        from src.wikipedia_maintenance.utils.candidate_finder import CandidateResult, SearchStrategy
        
        candidates = [
            CandidateResult(
                original_url="https://example.com/dead",
                candidate_url="https://example.com/candidate",
                strategy=SearchStrategy.TITLE_SEARCH,
                confidence=0.8,
                evidence={}
            )
        ]
        
        mock_candidate_finder.return_value.find_candidates.return_value = candidates
        
        # Mock dead link and unhealthy candidate
        mock_link_checker.return_value.check_link.side_effect = [
            LinkCheckResult(
                url="https://example.com/dead",
                status=LinkStatus.DEAD,
                http_status_code=404,
                error_type="Not Found"
            ),
            LinkCheckResult(
                url="https://example.com/candidate",
                status=LinkStatus.DEAD,
                http_status_code=404,
                error_type="Not Found"
            )
        ]
        
        content = "Test content with https://example.com/dead"
        
        issues = self.analyzer.analyze(content)
        
        # Should not repair for unhealthy candidate
        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
        assert len(repair_issues) == 0


class TestFailClosedIncompleteAnalysis:
    """Test that incomplete analysis results in NO_REPAIR."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = DeadLinkAnalyzer()
        self.analyzer.enable_auto_repair = True
    
    def test_max_checks_limit_no_repair(self):
        """Test that reaching max checks limit results in NO_REPAIR."""
        # Set very low max checks
        self.analyzer.max_checks_per_article = 1
        
        # Create content with multiple URLs
        content = """
        Test content with https://example.com/link1
        and https://example.com/link2
        and https://example.com/link3
        """
        
        # Mock link checker to return dead for all
        with patch.object(self.analyzer, 'link_checker') as mock_checker:
            mock_checker.check_link.return_value = LinkCheckResult(
                url="https://example.com/link1",
                status=LinkStatus.DEAD,
                http_status_code=404,
                error_type="Not Found"
            )
            
            issues = self.analyzer.analyze(content)
            
            # Should not repair when analysis is incomplete
            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
            assert len(repair_issues) == 0


class TestFailClosedAutoRepairDisabled:
    """Test that disabled auto-repair results in NO_REPAIR."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = DeadLinkAnalyzer()
        self.analyzer.enable_auto_repair = False  # Auto-repair disabled
    
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkChecker')
    def test_auto_repair_disabled_no_repair(self, mock_link_checker):
        """Test that disabled auto-repair results in NO_REPAIR."""
        # Mock dead link
        mock_link_checker.return_value.check_link.return_value = LinkCheckResult(
            url="https://example.com/dead",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        content = "Test content with https://example.com/dead"
        
        issues = self.analyzer.analyze(content)
        
        # Should not repair when auto-repair is disabled
        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
        assert len(repair_issues) == 0
        
        # Should still detect the dead link
        dead_issues = [i for i in issues if i.issue_type == "dead_link"]
        assert len(dead_issues) > 0
        assert dead_issues[0].extra.get('repair_status') == 'AUTO_REPAIR_DISABLED'


class TestFailClosedContradictoryEvidence:
    """Test that contradictory evidence results in NO_REPAIR."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = DeadLinkAnalyzer()
        self.analyzer.enable_auto_repair = True
    
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkValidator')
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkChecker')
    def test_title_mismatch_no_repair(self, mock_link_checker, mock_validator):
        """Test that title mismatch results in NO_REPAIR."""
        # Mock validator to reject due to title mismatch
        from src.wikipedia_maintenance.utils.link_validator import RepairResult
        
        mock_validator.return_value.validate_repair.return_value = RepairResult(
            original_url="https://example.com/dead",
            decision=RepairDecision.REPAIR_REJECTED,
            reason="Title mismatch between original and candidate"
        )
        
        # Mock dead link
        mock_link_checker.return_value.check_link.return_value = LinkCheckResult(
            url="https://example.com/dead",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        content = "Test content with https://example.com/dead"
        
        issues = self.analyzer.analyze(content)
        
        # Should not repair with title mismatch
        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
        assert len(repair_issues) == 0


class TestFailClosedSafeURLReplacement:
    """Test that SafeURLReplacer rejects non-minimal diffs."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = DeadLinkAnalyzer()
        self.analyzer.enable_auto_repair = True
    
    @patch('src.wikipedia_maintenance.analyzers.dead_links.SafeURLReplacer')
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkValidator')
    @patch('src.wikipedia_maintenance.analyzers.dead_links.LinkChecker')
    def test_non_minimal_diff_no_repair(self, mock_link_checker, mock_validator, mock_replacer):
        """Test that non-minimal diff results in NO_REPAIR."""
        # Mock validator to approve repair
        from src.wikipedia_maintenance.utils.link_validator import RepairResult, RepairDecision
        
        mock_validator.return_value.validate_repair.return_value = RepairResult(
            original_url="https://example.com/dead",
            decision=RepairDecision.REPLACEMENT_CONFIRMED,
            replacement_url="https://example.com/new",
            reason="All proofs confirmed"
        )
        
        # Mock safe URL replacer to reject diff
        mock_replacer.return_value.replace_exact_occurrence.return_value = Mock(
            success=False,
            reason="Non-minimal diff detected"
        )
        
        # Mock dead link
        mock_link_checker.return_value.check_link.return_value = LinkCheckResult(
            url="https://example.com/dead",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        
        content = "Test content with https://example.com/dead"
        
        issues = self.analyzer.analyze(content)
        
        # Should not repair with non-minimal diff
        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
        assert len(repair_issues) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
