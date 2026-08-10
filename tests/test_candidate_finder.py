"""
Unit tests for CandidateFinder - URL pattern generation and candidate validation.

These tests verify that the CandidateFinder correctly generates candidates
using URL patterns and validates them appropriately.
"""

import pytest
from unittest.mock import Mock, patch
from src.wikipedia_maintenance.utils.candidate_finder import (
    CandidateFinder,
    CandidateResult,
    SearchStrategy
)
from src.wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult


class TestCandidateFinder:
    """Test CandidateFinder functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.finder = CandidateFinder(timeout=10)
    
    def test_slugify_simple_title(self):
        """Test slugification of simple title."""
        title = "Test Article Title"
        slug = self.finder._slugify(title)
        
        assert slug == "test-article-title"
        assert " " not in slug
        assert slug.islower()
    
    def test_slugify_with_special_chars(self):
        """Test slugification with special characters."""
        title = "Article: Test - 2024"
        slug = self.finder._slugify(title)
        
        assert slug == "article-test-2024"
        assert ":" not in slug
        assert "-" not in slug.replace("-", "")  # Only hyphens as separators
    
    def test_slugify_with_accents(self):
        """Test slugification with accented characters."""
        title = "Article Été"
        slug = self.finder._slugify(title)
        
        # Accents should be preserved in basic implementation
        assert "été" in slug.lower()
    
    def test_extract_identifiers_from_html(self):
        """Test extraction of identifiers from HTML."""
        html_content = """
        <html>
        <head>
            <title>Test Article</title>
            <meta name="author" content="John Doe">
            <meta name="date" content="2024-01-01">
            <meta name="keywords" content="test, article, sample">
        </head>
        <body>
            Content here
        </body>
        </html>
        """
        
        from src.wikipedia_maintenance.utils.archive_provider import ArchiveResult, ArchiveAvailability
        archive_result = ArchiveResult(
            original_url="https://example.com/article",
            availability=ArchiveAvailability.AVAILABLE,
            archive_url="https://web.archive.org/web/20200101/https://example.com/article",
            archive_date="20200101"
        )
        
        identifiers = self.finder._extract_identifiers(html_content, archive_result)
        
        assert identifiers['title'] == "Test Article"
        assert identifiers['author'] == "John Doe"
        assert identifiers['date'] == "2024-01-01"
        assert "test" in identifiers['keywords']
    
    def test_extract_identifiers_minimal_html(self):
        """Test extraction from minimal HTML."""
        html_content = "<html><body>Content</body></html>"
        
        from src.wikipedia_maintenance.utils.archive_provider import ArchiveResult, ArchiveAvailability
        archive_result = ArchiveResult(
            original_url="https://example.com/article",
            availability=ArchiveAvailability.AVAILABLE
        )
        
        identifiers = self.finder._extract_identifiers(html_content, archive_result)
        
        # Should return empty identifiers for missing metadata
        assert identifiers['title'] is None
        assert identifiers['author'] is None
    
    @patch('src.wikipedia_maintenance.utils.candidate_finder.LinkChecker')
    def test_search_by_title_with_healthy_candidate(self, mock_link_checker):
        """Test title search with healthy candidate."""
        # Mock link checker to return healthy status
        mock_check_result = LinkCheckResult(
            url="https://example.com/test-article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            error_type=None
        )
        mock_link_checker.return_value.check_link.return_value = mock_check_result
        
        title = "Test Article"
        identifiers = {'domain': 'example.com'}
        
        candidates = self.finder._search_by_title(
            "https://example.com/dead-article",
            title,
            identifiers
        )
        
        # Should find at least one candidate
        assert len(candidates) > 0
        assert all(c.strategy == SearchStrategy.TITLE_SEARCH for c in candidates)
        assert all(c.confidence > 0 for c in candidates)
    
    @patch('src.wikipedia_maintenance.utils.candidate_finder.LinkChecker')
    def test_search_by_title_no_healthy_candidates(self, mock_link_checker):
        """Test title search with no healthy candidates."""
        # Mock link checker to return dead status
        mock_check_result = LinkCheckResult(
            url="https://example.com/test-article",
            status=LinkStatus.DEAD,
            http_status_code=404,
            error_type="Not Found"
        )
        mock_link_checker.return_value.check_link.return_value = mock_check_result
        
        title = "Test Article"
        identifiers = {'domain': 'example.com'}
        
        candidates = self.finder._search_by_title(
            "https://example.com/dead-article",
            title,
            identifiers
        )
        
        # Should find no candidates
        assert len(candidates) == 0
    
    def test_search_by_title_no_domain(self):
        """Test title search without domain."""
        title = "Test Article"
        identifiers = {}  # No domain
        
        candidates = self.finder._search_by_title(
            "https://example.com/dead-article",
            title,
            identifiers
        )
        
        # Should find no candidates without domain
        assert len(candidates) == 0
    
    @patch('src.wikipedia_maintenance.utils.candidate_finder.LinkChecker')
    def test_search_by_domain_with_healthy_candidate(self, mock_link_checker):
        """Test domain search with healthy candidate."""
        # Mock link checker to return healthy status
        mock_check_result = LinkCheckResult(
            url="https://example.com/test-article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            error_type=None
        )
        mock_link_checker.return_value.check_link.return_value = mock_check_result
        
        identifiers = {'domain': 'example.com', 'title': 'Test Article'}
        
        candidates = self.finder._search_by_domain(
            "https://example.com/dead-article",
            "example.com",
            identifiers
        )
        
        # Should find candidates
        assert len(candidates) > 0
        assert all(c.strategy == SearchStrategy.DOMAIN_SEARCH for c in candidates)
        assert all(c.confidence == 0.5 for c in candidates)  # Moderate confidence
    
    def test_deduplicate_candidates(self):
        """Test candidate deduplication."""
        candidates = [
            CandidateResult(
                original_url="https://example.com/dead",
                candidate_url="https://example.com/new",
                strategy=SearchStrategy.TITLE_SEARCH,
                confidence=0.8,
                evidence={}
            ),
            CandidateResult(
                original_url="https://example.com/dead",
                candidate_url="https://example.com/new",
                strategy=SearchStrategy.DOMAIN_SEARCH,
                confidence=0.5,
                evidence={}
            ),
            CandidateResult(
                original_url="https://example.com/dead",
                candidate_url="https://example.com/another",
                strategy=SearchStrategy.TITLE_SEARCH,
                confidence=0.7,
                evidence={}
            )
        ]
        
        deduplicated = self.finder._deduplicate_candidates(candidates)
        
        # Should have 2 unique candidates
        assert len(deduplicated) == 2
        
        # Should keep highest confidence for duplicate URL
        new_candidate = next(c for c in deduplicated if c.candidate_url == "https://example.com/new")
        assert new_candidate.confidence == 0.8  # Higher confidence kept
    
    def test_calculate_title_confidence(self):
        """Test title confidence calculation."""
        title = "Test Article"
        
        # Candidate URL contains slug
        candidate_with_slug = "https://example.com/test-article"
        confidence = self.finder._calculate_title_confidence(title, candidate_with_slug)
        
        assert confidence > 0.7  # Boosted confidence
        
        # Candidate URL doesn't contain slug
        candidate_without_slug = "https://example.com/something-else"
        confidence = self.finder._calculate_title_confidence(title, candidate_without_slug)
        
        assert confidence == 0.7  # Base confidence
    
    def test_candidate_result_to_dict(self):
        """Test CandidateResult serialization."""
        candidate = CandidateResult(
            original_url="https://example.com/dead",
            candidate_url="https://example.com/new",
            strategy=SearchStrategy.TITLE_SEARCH,
            confidence=0.8,
            evidence={'title_match': 'Test Article'}
        )
        
        result_dict = candidate.to_dict()
        
        assert result_dict['original_url'] == "https://example.com/dead"
        assert result_dict['candidate_url'] == "https://example.com/new"
        assert result_dict['strategy'] == 'title_search'
        assert result_dict['confidence'] == 0.8
        assert result_dict['evidence']['title_match'] == 'Test Article'


class TestCandidateFinderFailClosed:
    """Test fail-closed behavior of CandidateFinder."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.finder = CandidateFinder(timeout=10)
    
    def test_no_candidates_without_archive(self):
        """Test that no candidates are found without archive."""
        # Mock archive provider to return no archive
        with patch.object(self.finder.archive_provider, 'check_archive') as mock_check:
            from src.wikipedia_maintenance.utils.archive_provider import ArchiveResult, ArchiveAvailability
            mock_check.return_value = ArchiveResult(
                original_url="https://example.com/dead",
                availability=ArchiveAvailability.NOT_AVAILABLE
            )
            
            candidates = self.finder.find_candidates("https://example.com/dead")
            
            assert len(candidates) == 0
    
    def test_no_candidates_without_title(self):
        """Test that no candidates are found without title."""
        # Mock archive provider to return archive without title
        with patch.object(self.finder.archive_provider, 'check_archive') as mock_check:
            from src.wikipedia_maintenance.utils.archive_provider import ArchiveResult, ArchiveAvailability
            mock_check.return_value = ArchiveResult(
                original_url="https://example.com/dead",
                availability=ArchiveAvailability.AVAILABLE,
                archive_url="https://web.archive.org/web/20200101/https://example.com/dead"
            )
            
            with patch.object(self.finder.archive_provider, 'get_content_snapshot') as mock_content:
                mock_content.return_value = "<html><body>No title</body></html>"
                
                candidates = self.finder.find_candidates("https://example.com/dead")
                
                # Should find no candidates without title
                assert len(candidates) == 0
    
    @patch('src.wikipedia_maintenance.utils.candidate_finder.LinkChecker')
    def test_candidates_sorted_by_confidence(self, mock_link_checker):
        """Test that candidates are sorted by confidence."""
        # Mock link checker to return healthy status
        mock_check_result = LinkCheckResult(
            url="https://example.com/test-article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            error_type=None
        )
        mock_link_checker.return_value.check_link.return_value = mock_check_result
        
        with patch.object(self.finder.archive_provider, 'check_archive') as mock_check:
            from src.wikipedia_maintenance.utils.archive_provider import ArchiveResult, ArchiveAvailability
            mock_check.return_value = ArchiveResult(
                original_url="https://example.com/dead",
                availability=ArchiveAvailability.AVAILABLE,
                archive_url="https://web.archive.org/web/20200101/https://example.com/dead"
            )
            
            with patch.object(self.finder.archive_provider, 'get_content_snapshot') as mock_content:
                mock_content.return_value = "<html><head><title>Test Article</title></head></html>"
                
                candidates = self.finder.find_candidates("https://example.com/dead")
                
                # Should be sorted by confidence (highest first)
                if len(candidates) > 1:
                    for i in range(len(candidates) - 1):
                        assert candidates[i].confidence >= candidates[i + 1].confidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
