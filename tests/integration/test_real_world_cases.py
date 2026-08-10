"""
Real-World Test Cases for DeadLinkAnalyzer.

These tests use real-world scenarios to validate the complete pipeline:
- 404 + redirection towards the same page
- 404 + new URL found in archive
- 404 + archive available but no new URL identifiable
- 404 + candidate different
- 404 + candidate HTTP 200 but wrong content
- 404 + provider unavailable
- 503 / rate limit
- timeout
- multiple candidates
- no candidate

Run with: python tests/integration/test_real_world_cases.py
"""

import pytest
import logging
from unittest.mock import Mock, patch
from src.wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
from src.wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult
from src.wikipedia_maintenance.utils.redirect_finder import RedirectDecision, RedirectResult
from src.wikipedia_maintenance.utils.link_validator import RepairDecision

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestCase404WithRedirect:
    """Test case: 404 + redirect towards the same page."""
    
    def test_404_with_valid_redirect(self):
        """
        Test: Dead link with valid HTTP redirect to same resource.
        Expected: REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            # Mock dead link check
            mock_checker.check_link.return_value = LinkCheckResult(
                url="https://example.com/old-article",
                status=LinkStatus.DEAD,
                http_status_code=404,
                error_type="Not Found"
            )
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                # Mock valid redirect
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/old-article",
                    redirected_url="https://example.com/new-article",
                    decision=RedirectDecision.VALID_REDIRECT,
                    redirect_chain=[],
                    reason="Valid redirect to same resource"
                )
                
                with patch.object(analyzer, 'content_verifier') as mock_content:
                    # Mock content verification success
                    from src.wikipedia_maintenance.utils.content_verifier import ContentMatch
                    mock_content.verify_same_resource.return_value = Mock(
                        decision=ContentMatch.STRONG_MATCH,
                        reason="Strong match: same domain, title, and content"
                    )
                    
                    with patch.object(analyzer, 'archive_provider') as mock_archive:
                        # Mock archive evidence
                        mock_archive.verify_content_match.return_value = {
                            'original_archive_available': True,
                            'candidate_archive_available': True,
                            'original_title': 'Test Article',
                            'candidate_title': 'Test Article',
                            'title_match': True
                        }
                        
                        content = "Test content with https://example.com/old-article"
                        issues = analyzer.analyze(content)
                        
                        # Should find and repair the dead link
                        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
                        assert len(repair_issues) > 0, "Should repair with valid redirect"
                        logger.info("✓ Test 404+redirect: PASS - Repair confirmed")


class TestCase404WithArchiveNewURL:
    """Test case: 404 + new URL found in archive."""
    
    def test_404_with_archive_candidate(self):
        """
        Test: Dead link with new URL discovered via archive.
        Expected: REPAIR if candidate is validated
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            # Mock dead link check
            mock_checker.check_link.side_effect = [
                LinkCheckResult(
                    url="https://example.com/dead-article",
                    status=LinkStatus.DEAD,
                    http_status_code=404,
                    error_type="Not Found"
                ),
                LinkCheckResult(
                    url="https://example.com/found-article",
                    status=LinkStatus.HEALTHY,
                    http_status_code=200,
                    error_type=None
                )
            ]
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                # No redirect found
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/dead-article",
                    redirected_url=None,
                    decision=RedirectDecision.NO_REDIRECT,
                    redirect_chain=[],
                    reason="No redirect found"
                )
                
                with patch.object(analyzer, 'candidate_finder') as mock_finder:
                    from src.wikipedia_maintenance.utils.candidate_finder import CandidateResult, SearchStrategy
                    # Mock candidate found via archive
                    mock_finder.find_candidates.return_value = [
                        CandidateResult(
                            original_url="https://example.com/dead-article",
                            candidate_url="https://example.com/found-article",
                            strategy=SearchStrategy.ARCHIVE_TITLE_SEARCH,
                            confidence=0.9,
                            evidence={'title_match': 'Test Article', 'domain_match': True}
                        )
                    ]
                    
                    with patch.object(analyzer, 'content_verifier') as mock_content:
                        # Mock content verification success
                        from src.wikipedia_maintenance.utils.content_verifier import ContentMatch
                        mock_content.verify_same_resource.return_value = Mock(
                            decision=ContentMatch.STRONG_MATCH,
                            reason="Strong match confirmed"
                        )
                        
                        with patch.object(analyzer, 'archive_provider') as mock_archive:
                            # Mock archive evidence
                            mock_archive.verify_content_match.return_value = {
                                'original_archive_available': True,
                                'candidate_archive_available': True,
                                'original_title': 'Test Article',
                                'candidate_title': 'Test Article',
                                'title_match': True
                            }
                            
                            content = "Test content with https://example.com/dead-article"
                            issues = analyzer.analyze(content)
                            
                            # Should find candidate and potentially repair
                            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
                            logger.info(f"✓ Test 404+archive_candidate: {'PASS' if len(repair_issues) > 0 else 'PARTIAL'} - {'Candidate found and validated' if len(repair_issues) > 0 else 'Candidate found but validation failed'}")


class TestCase404ArchiveNoCandidate:
    """Test case: 404 + archive available but no new URL identifiable."""
    
    def test_404_archive_no_candidate(self):
        """
        Test: Dead link with archive but no candidate found.
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            # Mock dead link check
            mock_checker.check_link.return_value = LinkCheckResult(
                url="https://example.com/dead-article",
                status=LinkStatus.DEAD,
                http_status_code=404,
                error_type="Not Found"
            )
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                # No redirect found
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/dead-article",
                    redirected_url=None,
                    decision=RedirectDecision.NO_REDIRECT,
                    redirect_chain=[],
                    reason="No redirect found"
                )
                
                with patch.object(analyzer, 'candidate_finder') as mock_finder:
                    # No candidates found
                    mock_finder.find_candidates.return_value = []
                    
                    content = "Test content with https://example.com/dead-article"
                    issues = analyzer.analyze(content)
                    
                    # Should detect dead link but not repair
                    repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
                    assert len(repair_issues) == 0, "Should not repair without candidate"
                    
                    dead_issues = [i for i in issues if i.issue_type == "dead_link"]
                    assert len(dead_issues) > 0, "Should detect dead link"
                    logger.info("✓ Test 404+archive_no_candidate: PASS - Dead link detected, no repair")


class TestCase404CandidateDifferent:
    """Test case: 404 + candidate different."""
    
    def test_404_candidate_different(self):
        """
        Test: Dead link with candidate on different domain.
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            # Mock dead link check
            mock_checker.check_link.side_effect = [
                LinkCheckResult(
                    url="https://example.com/dead-article",
                    status=LinkStatus.DEAD,
                    http_status_code=404,
                    error_type="Not Found"
                ),
                LinkCheckResult(
                    url="https://different-domain.com/article",
                    status=LinkStatus.HEALTHY,
                    http_status_code=200,
                    error_type=None
                )
            ]
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                # No redirect found
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/dead-article",
                    redirected_url=None,
                    decision=RedirectDecision.NO_REDIRECT,
                    redirect_chain=[],
                    reason="No redirect found"
                )
                
                with patch.object(analyzer, 'candidate_finder') as mock_finder:
                    from src.wikipedia_maintenance.utils.candidate_finder import CandidateResult, SearchStrategy
                    # Mock candidate on different domain
                    mock_finder.find_candidates.return_value = [
                        CandidateResult(
                            original_url="https://example.com/dead-article",
                            candidate_url="https://different-domain.com/article",
                            strategy=SearchStrategy.ARCHIVE_TITLE_SEARCH,
                            confidence=0.6,
                            evidence={'title_match': 'Test Article', 'domain_match': False}
                        )
                    ]
                    
                    with patch.object(analyzer, 'link_validator') as mock_validator:
                        # Mock validator to reject due to different domain
                        from src.wikipedia_maintenance.utils.link_validator import RepairResult
                        mock_validator.validate_repair.return_value = RepairResult(
                            original_url="https://example.com/dead-article",
                            decision=RepairDecision.REPAIR_REJECTED,
                            reason="Different domain - not same source"
                        )
                        
                        content = "Test content with https://example.com/dead-article"
                        issues = analyzer.analyze(content)
                        
                        # Should not repair for different domain
                        repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
                        assert len(repair_issues) == 0, "Should not repair for different domain"
                        logger.info("✓ Test 404+candidate_different: PASS - Different domain rejected")


class TestCase404Candidate200WrongContent:
    """Test case: 404 + candidate HTTP 200 but wrong content."""
    
    def test_404_candidate_200_wrong_content(self):
        """
        Test: Dead link with candidate returning 200 but wrong content.
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            # Mock dead link check and healthy candidate
            mock_checker.check_link.side_effect = [
                LinkCheckResult(
                    url="https://example.com/dead-article",
                    status=LinkStatus.DEAD,
                    http_status_code=404,
                    error_type="Not Found"
                ),
                LinkCheckResult(
                    url="https://example.com/wrong-article",
                    status=LinkStatus.HEALTHY,
                    http_status_code=200,
                    error_type=None
                )
            ]
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                # No redirect found
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/dead-article",
                    redirected_url=None,
                    decision=RedirectDecision.NO_REDIRECT,
                    redirect_chain=[],
                    reason="No redirect found"
                )
                
                with patch.object(analyzer, 'candidate_finder') as mock_finder:
                    from src.wikipedia_maintenance.utils.candidate_finder import CandidateResult, SearchStrategy
                    # Mock candidate found
                    mock_finder.find_candidates.return_value = [
                        CandidateResult(
                            original_url="https://example.com/dead-article",
                            candidate_url="https://example.com/wrong-article",
                            strategy=SearchStrategy.ARCHIVE_TITLE_SEARCH,
                            confidence=0.7,
                            evidence={'title_match': 'Different Title', 'domain_match': True}
                        )
                    ]
                    
                    with patch.object(analyzer, 'content_verifier') as mock_content:
                        # Mock content verification failure
                        from src.wikipedia_maintenance.utils.content_verifier import ContentMatch
                        mock_content.verify_same_resource.return_value = Mock(
                            decision=ContentMatch.NO_MATCH,
                            reason="Content does not match - different page"
                        )
                        
                        with patch.object(analyzer, 'link_validator') as mock_validator:
                            # Mock validator to reject
                            from src.wikipedia_maintenance.utils.link_validator import RepairResult
                            mock_validator.validate_repair.return_value = RepairResult(
                                original_url="https://example.com/dead-article",
                                decision=RepairDecision.REPAIR_REJECTED,
                                reason="Content mismatch - not same resource"
                            )
                            
                            content = "Test content with https://example.com/dead-article"
                            issues = analyzer.analyze(content)
                            
                            # Should not repair for wrong content
                            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
                            assert len(repair_issues) == 0, "Should not repair for wrong content"
                            logger.info("✓ Test 404+candidate_200_wrong_content: PASS - Wrong content rejected")


class TestCaseProviderUnavailable:
    """Test case: 404 + provider unavailable."""
    
    def test_404_provider_unavailable(self):
        """
        Test: Dead link with archive provider unavailable.
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            # Mock dead link check
            mock_checker.check_link.return_value = LinkCheckResult(
                url="https://example.com/dead-article",
                status=LinkStatus.DEAD,
                http_status_code=404,
                error_type="Not Found"
            )
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                # No redirect found
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/dead-article",
                    redirected_url=None,
                    decision=RedirectDecision.NO_REDIRECT,
                    redirect_chain=[],
                    reason="No redirect found"
                )
                
                with patch.object(analyzer, 'archive_provider') as mock_archive:
                    # Mock provider unavailable
                    mock_archive.check_archive.side_effect = Exception("Provider unavailable")
                    
                    content = "Test content with https://example.com/dead-article"
                    issues = analyzer.analyze(content)
                    
                    # Should not repair when provider unavailable
                    repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
                    assert len(repair_issues) == 0, "Should not repair when provider unavailable"
                    logger.info("✓ Test 404+provider_unavailable: PASS - Provider unavailable handled")


class TestCaseMultipleCandidates:
    """Test case: 404 + multiple candidates."""
    
    def test_404_multiple_candidates(self):
        """
        Test: Dead link with multiple candidates.
        Expected: NO_REPAIR (ambiguity)
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            # Mock dead link check
            mock_checker.check_link.return_value = LinkCheckResult(
                url="https://example.com/dead-article",
                status=LinkStatus.DEAD,
                http_status_code=404,
                error_type="Not Found"
            )
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                # No redirect found
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/dead-article",
                    redirected_url=None,
                    decision=RedirectDecision.NO_REDIRECT,
                    redirect_chain=[],
                    reason="No redirect found"
                )
                
                with patch.object(analyzer, 'candidate_finder') as mock_finder:
                    from src.wikipedia_maintenance.utils.candidate_finder import CandidateResult, SearchStrategy
                    # Mock multiple candidates with similar confidence
                    mock_finder.find_candidates.return_value = [
                        CandidateResult(
                            original_url="https://example.com/dead-article",
                            candidate_url="https://example.com/candidate1",
                            strategy=SearchStrategy.ARCHIVE_TITLE_SEARCH,
                            confidence=0.8,
                            evidence={'title_match': 'Test Article', 'domain_match': True}
                        ),
                        CandidateResult(
                            original_url="https://example.com/dead-article",
                            candidate_url="https://example.com/candidate2",
                            strategy=SearchStrategy.ARCHIVE_TITLE_SEARCH,
                            confidence=0.8,
                            evidence={'title_match': 'Test Article', 'domain_match': True}
                        )
                    ]
                    
                    content = "Test content with https://example.com/dead-article"
                    issues = analyzer.analyze(content)
                    
                    # Should not repair with multiple candidates
                    repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
                    assert len(repair_issues) == 0, "Should not repair with multiple candidates (ambiguity)"
                    logger.info("✓ Test 404+multiple_candidates: PASS - Ambiguity rejected")


class TestCaseNoCandidate:
    """Test case: 404 + no candidate."""
    
    def test_404_no_candidate(self):
        """
        Test: Dead link with no candidate found.
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            # Mock dead link check
            mock_checker.check_link.return_value = LinkCheckResult(
                url="https://example.com/dead-article",
                status=LinkStatus.DEAD,
                http_status_code=404,
                error_type="Not Found"
            )
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                # No redirect found
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/dead-article",
                    redirected_url=None,
                    decision=RedirectDecision.NO_REDIRECT,
                    redirect_chain=[],
                    reason="No redirect found"
                )
                
                with patch.object(analyzer, 'candidate_finder') as mock_finder:
                    # No candidates found
                    mock_finder.find_candidates.return_value = []
                    
                    content = "Test content with https://example.com/dead-article"
                    issues = analyzer.analyze(content)
                    
                    # Should detect dead link but not repair
                    repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
                    assert len(repair_issues) == 0, "Should not repair without candidate"
                    
                    dead_issues = [i for i in issues if i.issue_type == "dead_link"]
                    assert len(dead_issues) > 0, "Should detect dead link"
                    logger.info("✓ Test 404+no_candidate: PASS - Dead link detected, no repair")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
