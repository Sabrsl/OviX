"""
Test to verify the ARCHIVE_FALLBACK HTTP verification fix.

This test ensures that archive URLs are actually verified with HTTP checks
before being accepted as replacements, preventing the bug where CDX records
exist but the snapshots are not accessible.
"""

import pytest
from unittest.mock import Mock, patch
from wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
from wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult
from wikipedia_maintenance.utils.archive_provider import ArchiveResult, ArchiveAvailability


class TestArchiveVerification:
    """Test cases for archive URL HTTP verification."""
    
    def test_archive_url_404_should_not_repair(self):
        """Test that archive URL returning 404 should NOT result in repair."""
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        # Sample content with a dead link
        content = "See https://www.cairn.info/revue-arabe-2022-3-page-345.htm for details"
        url = "https://www.cairn.info/revue-arabe-2022-3-page-345.htm"
        
        # Mock HTTP check returning 404 for original URL
        with patch.object(analyzer.link_checker, 'check_link') as mock_check:
            # Original URL is dead
            mock_check.return_value = LinkCheckResult(
                url=url,
                status=LinkStatus.DEAD,
                http_status_code=404,
                confidence=1.0
            )
            
            # Mock redirect finder finding no redirect
            with patch.object(analyzer.redirect_finder, 'find_redirect') as mock_redirect:
                mock_redirect.return_value = None
                
                # Mock archive provider finding an archive URL
                with patch.object(analyzer.archive_provider, 'check_archive') as mock_archive:
                    mock_archive.return_value = ArchiveResult(
                        original_url=url,
                        availability=ArchiveAvailability.AVAILABLE,
                        archive_url="https://web.archive.org/web/20220907/https://www.cairn.info/revue-arabe-2022-3-page-345.htm",
                        archive_date="20220907",
                        provider="wayback"
                    )
                    
                    # Mock HTTP check for archive URL returning 404 (snapshot not accessible)
                    def side_effect_check(check_url):
                        if check_url == url:
                            return LinkCheckResult(
                                url=url,
                                status=LinkStatus.DEAD,
                                http_status_code=404,
                                confidence=1.0
                            )
                        elif "web.archive.org" in check_url:
                            # Archive URL returns 404 - snapshot not accessible
                            return LinkCheckResult(
                                url=check_url,
                                status=LinkStatus.DEAD,
                                http_status_code=404,
                                confidence=1.0
                            )
                        return LinkCheckResult(
                            url=check_url,
                            status=LinkStatus.UNKNOWN,
                            confidence=0.0
                        )
                    
                    mock_check.side_effect = side_effect_check
                    
                    # Run analysis
                    analyzer.analyze(content)
                    
                    # Should NOT have repaired the link since archive URL is not accessible
                    assert len(analyzer.issues) == 0, "Should not repair when archive URL returns 404"
    
    def test_archive_url_200_should_repair(self):
        """Test that archive URL returning 200 SHOULD result in repair."""
        analyzer = DeadLinkAnalyzer()
        analyzer.enable_auto_repair = True
        
        # Sample content with a dead link
        content = "See https://www.example.com/dead-link for details"
        url = "https://www.example.com/dead-link"
        
        # Mock HTTP check returning 404 for original URL
        with patch.object(analyzer.link_checker, 'check_link') as mock_check:
            # Original URL is dead
            mock_check.return_value = LinkCheckResult(
                url=url,
                status=LinkStatus.DEAD,
                http_status_code=404,
                confidence=1.0
            )
            
            # Mock redirect finder finding no redirect
            with patch.object(analyzer.redirect_finder, 'find_redirect') as mock_redirect:
                mock_redirect.return_value = None
                
                # Mock archive provider finding an archive URL
                with patch.object(analyzer.archive_provider, 'check_archive') as mock_archive:
                    archive_url = "https://web.archive.org/web/20230101/https://www.example.com/dead-link"
                    mock_archive.return_value = ArchiveResult(
                        original_url=url,
                        availability=ArchiveAvailability.AVAILABLE,
                        archive_url=archive_url,
                        archive_date="20230101",
                        provider="wayback"
                    )
                    
                    # Mock HTTP check for archive URL returning 200 (snapshot accessible)
                    def side_effect_check(check_url):
                        if check_url == url:
                            return LinkCheckResult(
                                url=url,
                                status=LinkStatus.DEAD,
                                http_status_code=404,
                                confidence=1.0
                            )
                        elif "web.archive.org" in check_url:
                            # Archive URL returns 200 - snapshot is accessible
                            return LinkCheckResult(
                                url=check_url,
                                status=LinkStatus.HEALTHY,
                                http_status_code=200,
                                confidence=1.0
                            )
                        return LinkCheckResult(
                            url=check_url,
                            status=LinkStatus.UNKNOWN,
                            confidence=0.0
                        )
                    
                    mock_check.side_effect = side_effect_check
                    
                    # Run analysis
                    issues = analyzer.analyze(content)
                    
                    # SHOULD have repaired the link since archive URL is accessible
                    assert len(issues) == 1, "Should repair when archive URL returns 200"
                    assert issues[0].issue_type == "dead_link"
                    assert issues[0].suggested_text == archive_url, "Issue should suggest archive URL"
                    assert issues[0].original_text == url, "Issue should reference original dead URL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
