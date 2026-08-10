"""
False Positive Tests for DeadLinkAnalyzer.

These tests verify that the system REJECTS repairs in dangerous scenarios.
ALL these tests MUST result in NO_REPAIR.

Critical scenarios:
- Same domain but different article
- Similar title but different article
- Same topic but different page
- Similar URL but different content
- Candidate HTTP 200 but wrong resource
- Candidate found in archive but currently different
- Multiple plausible candidates
- Old archive and current candidate contradictory
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import Mock, patch
from src.wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
from src.wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult
from src.wikipedia_maintenance.utils.redirect_finder import RedirectDecision, RedirectResult
from src.wikipedia_maintenance.utils.link_validator import RepairDecision
from src.wikipedia_maintenance.utils.content_verifier import ContentMatch


class TestFalsePositiveSameDomainDifferentArticle:
    """Test: Same domain but different article."""
    
    def test_same_domain_different_article(self):
        """
        Scenario: Dead link on example.com/old-article
        Candidate: example.com/new-article (same domain, different content)
        
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            mock_checker.check_link.side_effect = [
                LinkCheckResult(url="https://example.com/old-article", status=LinkStatus.DEAD, http_status_code=404, error_type="Not Found"),
                LinkCheckResult(url="https://example.com/new-article", status=LinkStatus.HEALTHY, http_status_code=200, error_type=None)
            ]
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/old-article",
                    redirected_url="https://example.com/new-article",
                    decision=RedirectDecision.VALID_REDIRECT,
                    reason="Valid redirect"
                )
            
            with patch.object(analyzer, 'content_verifier') as mock_content:
                # Content verifier should detect different content
                mock_content.verify_same_resource.return_value = Mock(
                    decision=ContentMatch.NO_MATCH,
                    reason="Content does not match - different article"
                )
            
            with patch.object(analyzer, 'archive_provider') as mock_archive:
                mock_archive.verify_content_match.return_value = {
                    'original_archive_available': True,
                    'candidate_archive_available': True,
                    'original_title': 'Old Article Title',
                    'candidate_title': 'New Article Title',
                    'title_match': False  # Different titles
                }
            
            content = "Test with https://example.com/old-article"
            issues = analyzer.analyze(content)
            
            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
            assert len(repair_issues) == 0, "Should NOT repair same domain different article"
            print("✓ PASS: Same domain different article rejected")


class TestFalsePositiveSimilarTitleDifferentArticle:
    """Test: Similar title but different article."""
    
    def test_similar_title_different_article(self):
        """
        Scenario: Dead link with title "Article Title"
        Candidate with title "Article Title - Updated" (similar but different)
        
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            mock_checker.check_link.side_effect = [
                LinkCheckResult(url="https://example.com/old-article", status=LinkStatus.DEAD, http_status_code=404, error_type="Not Found"),
                LinkCheckResult(url="https://example.com/new-article", status=LinkStatus.HEALTHY, http_status_code=200, error_type=None)
            ]
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/old-article",
                    redirected_url="https://example.com/new-article",
                    decision=RedirectDecision.VALID_REDIRECT,
                    reason="Valid redirect"
                )
            
            with patch.object(analyzer, 'content_verifier') as mock_content:
                mock_content.verify_same_resource.return_value = Mock(
                    decision=ContentMatch.NO_MATCH,
                    reason="Content does not match despite similar title"
                )
            
            with patch.object(analyzer, 'archive_provider') as mock_archive:
                # Similar but different titles
                mock_archive.verify_content_match.return_value = {
                    'original_archive_available': True,
                    'candidate_archive_available': True,
                    'original_title': 'Article Title',
                    'candidate_title': 'Article Title - Updated',
                    'title_match': False  # Not exact match
                }
            
            content = "Test with https://example.com/old-article"
            issues = analyzer.analyze(content)
            
            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
            assert len(repair_issues) == 0, "Should NOT repair similar title different article"
            print("✓ PASS: Similar title different article rejected")


class TestFalsePositiveSameTopicDifferentPage:
    """Test: Same topic but different page."""
    
    def test_same_topic_different_page(self):
        """
        Scenario: Dead link about "Climate Change"
        Candidate about "Climate Change" but different article (e.g., news vs research)
        
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            mock_checker.check_link.side_effect = [
                LinkCheckResult(url="https://example.com/climate-change-research", status=LinkStatus.DEAD, http_status_code=404, error_type="Not Found"),
                LinkCheckResult(url="https://example.com/climate-change-news", status=LinkStatus.HEALTHY, http_status_code=200, error_type=None)
            ]
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/climate-change-research",
                    redirected_url="https://example.com/climate-change-news",
                    decision=RedirectDecision.VALID_REDIRECT,
                    reason="Valid redirect"
                )
            
            with patch.object(analyzer, 'content_verifier') as mock_content:
                mock_content.verify_same_resource.return_value = Mock(
                    decision=ContentMatch.WEAK_MATCH,  # Only weak match
                    reason="Same topic but different content type"
                )
            
            with patch.object(analyzer, 'archive_provider') as mock_archive:
                mock_archive.verify_content_match.return_value = {
                    'original_archive_available': True,
                    'candidate_archive_available': True,
                    'original_title': 'Climate Change Research Paper',
                    'candidate_title': 'Climate Change News Article',
                    'title_match': False
                }
            
            content = "Test with https://example.com/climate-change-research"
            issues = analyzer.analyze(content)
            
            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
            assert len(repair_issues) == 0, "Should NOT repair same topic different page"
            print("✓ PASS: Same topic different page rejected")


class TestFalsePositiveSimilarURLDifferentContent:
    """Test: Similar URL but different content."""
    
    def test_similar_url_different_content(self):
        """
        Scenario: Dead link /article/123
        Candidate /article/124 (similar URL, different content)
        
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            mock_checker.check_link.side_effect = [
                LinkCheckResult(url="https://example.com/article/123", status=LinkStatus.DEAD, http_status_code=404, error_type="Not Found"),
                LinkCheckResult(url="https://example.com/article/124", status=LinkStatus.HEALTHY, http_status_code=200, error_type=None)
            ]
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/article/123",
                    redirected_url="https://example.com/article/124",
                    decision=RedirectDecision.VALID_REDIRECT,
                    reason="Valid redirect"
                )
            
            with patch.object(analyzer, 'content_verifier') as mock_content:
                mock_content.verify_same_resource.return_value = Mock(
                    decision=ContentMatch.NO_MATCH,
                    reason="Different content despite similar URL"
                )
            
            with patch.object(analyzer, 'archive_provider') as mock_archive:
                mock_archive.verify_content_match.return_value = {
                    'original_archive_available': True,
                    'candidate_archive_available': True,
                    'original_title': 'Article 123',
                    'candidate_title': 'Article 124',
                    'title_match': False
                }
            
            content = "Test with https://example.com/article/123"
            issues = analyzer.analyze(content)
            
            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
            assert len(repair_issues) == 0, "Should NOT repair similar URL different content"
            print("✓ PASS: Similar URL different content rejected")


class TestFalsePositiveCandidate200WrongResource:
    """Test: Candidate HTTP 200 but wrong resource."""
    
    def test_candidate_200_wrong_resource(self):
        """
        Scenario: Candidate returns HTTP 200 but is completely wrong resource
        (e.g., homepage instead of specific article)
        
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            mock_checker.check_link.side_effect = [
                LinkCheckResult(url="https://example.com/specific-article", status=LinkStatus.DEAD, http_status_code=404, error_type="Not Found"),
                LinkCheckResult(url="https://example.com/", status=LinkStatus.HEALTHY, http_status_code=200, error_type=None)  # Homepage
            ]
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/specific-article",
                    redirected_url="https://example.com/",
                    decision=RedirectDecision.VALID_REDIRECT,
                    reason="Valid redirect"
                )
            
            with patch.object(analyzer, 'content_verifier') as mock_content:
                mock_content.verify_same_resource.return_value = Mock(
                    decision=ContentMatch.NO_MATCH,
                    reason="Homepage is not the specific article"
                )
            
            with patch.object(analyzer, 'archive_provider') as mock_archive:
                mock_archive.verify_content_match.return_value = {
                    'original_archive_available': True,
                    'candidate_archive_available': True,
                    'original_title': 'Specific Article Title',
                    'candidate_title': 'Homepage',
                    'title_match': False
                }
            
            content = "Test with https://example.com/specific-article"
            issues = analyzer.analyze(content)
            
            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
            assert len(repair_issues) == 0, "Should NOT repair HTTP 200 wrong resource"
            print("✓ PASS: HTTP 200 wrong resource rejected")


class TestFalsePositiveArchiveCandidateCurrentlyDifferent:
    """Test: Candidate found in archive but currently different."""
    
    def test_archive_candidate_currently_different(self):
        """
        Scenario: Archive shows page moved to new URL, but current page at that URL
        has completely changed (e.g., domain repurposing)
        
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            mock_checker.check_link.side_effect = [
                LinkCheckResult(url="https://oldsite.com/article", status=LinkStatus.DEAD, http_status_code=404, error_type="Not Found"),
                LinkCheckResult(url="https://newsite.com/article", status=LinkStatus.HEALTHY, http_status_code=200, error_type=None)
            ]
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://oldsite.com/article",
                    redirected_url="https://newsite.com/article",
                    decision=RedirectDecision.VALID_REDIRECT,
                    reason="Valid redirect"
                )
            
            with patch.object(analyzer, 'content_verifier') as mock_content:
                mock_content.verify_same_resource.return_value = Mock(
                    decision=ContentMatch.NO_MATCH,
                    reason="Domain repurposed - completely different content"
                )
            
            with patch.object(analyzer, 'archive_provider') as mock_archive:
                # Archive shows old content, but current is different
                mock_archive.verify_content_match.return_value = {
                    'original_archive_available': True,
                    'candidate_archive_available': True,
                    'original_title': 'Original Article',
                    'candidate_title': 'Different Content',
                    'title_match': False,
                    'note': 'Archive evidence contradicts current content'
                }
            
            content = "Test with https://oldsite.com/article"
            issues = analyzer.analyze(content)
            
            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
            assert len(repair_issues) == 0, "Should NOT repair archive candidate currently different"
            print("✓ PASS: Archive candidate currently different rejected")


class TestFalsePositiveMultiplePlausibleCandidates:
    """Test: Multiple plausible candidates."""
    
    def test_multiple_plausible_candidates(self):
        """
        Scenario: Multiple candidates with similar confidence
        (ambiguity - cannot determine correct one)
        
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            mock_checker.check_link.return_value = LinkCheckResult(
                url="https://example.com/dead-article",
                status=LinkStatus.DEAD,
                http_status_code=404,
                error_type="Not Found"
            )
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/dead-article",
                    redirected_url=None,
                    decision=RedirectDecision.NO_REDIRECT,
                    reason="No redirect found"
                )
            
            with patch.object(analyzer, 'candidate_finder') as mock_finder:
                from src.wikipedia_maintenance.utils.candidate_finder import CandidateResult, SearchStrategy
                # Multiple candidates with similar confidence
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
            
            content = "Test with https://example.com/dead-article"
            issues = analyzer.analyze(content)
            
            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
            assert len(repair_issues) == 0, "Should NOT repair with multiple candidates (ambiguity)"
            print("✓ PASS: Multiple plausible candidates rejected")


class TestFalsePositiveOldArchiveCurrentCandidateContradictory:
    """Test: Old archive and current candidate contradictory."""
    
    def test_old_archive_current_candidate_contradictory(self):
        """
        Scenario: Archive from 10 years ago shows one thing,
        current candidate shows completely different content
        
        Expected: NO_REPAIR
        """
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        with patch.object(analyzer, 'link_checker') as mock_checker:
            mock_checker.check_link.side_effect = [
                LinkCheckResult(url="https://example.com/old-article", status=LinkStatus.DEAD, http_status_code=404, error_type="Not Found"),
                LinkCheckResult(url="https://example.com/new-article", status=LinkStatus.HEALTHY, http_status_code=200, error_type=None)
            ]
            
            with patch.object(analyzer, 'redirect_finder') as mock_redirect:
                mock_redirect.find_redirect.return_value = RedirectResult(
                    original_url="https://example.com/old-article",
                    redirected_url="https://example.com/new-article",
                    decision=RedirectDecision.VALID_REDIRECT,
                    reason="Valid redirect"
                )
            
            with patch.object(analyzer, 'content_verifier') as mock_content:
                mock_content.verify_same_resource.return_value = Mock(
                    decision=ContentMatch.NO_MATCH,
                    reason="Archive from 2014 contradicts current content"
                )
            
            with patch.object(analyzer, 'archive_provider') as mock_archive:
                mock_archive.verify_content_match.return_value = {
                    'original_archive_available': True,
                    'original_archive_date': '20140101',  # 10 years old
                    'candidate_archive_available': True,
                    'original_title': 'Old Article from 2014',
                    'candidate_title': 'New Article',
                    'title_match': False,
                    'contradiction': 'Archive evidence contradicts current content'
                }
            
            content = "Test with https://example.com/old-article"
            issues = analyzer.analyze(content)
            
            repair_issues = [i for i in issues if i.extra.get('repair_decision') == 'replacement_confirmed']
            assert len(repair_issues) == 0, "Should NOT repair with contradictory evidence"
            print("✓ PASS: Old archive current candidate contradictory rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
