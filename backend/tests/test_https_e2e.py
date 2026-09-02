"""
End-to-end integration test for HTTP→HTTPS conversion.

This test verifies the complete flow:
Article Wikipédia → HttpLinksAnalyzer → HTTPS verification → issue http_link → Corrector → wikicode final
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from unittest.mock import Mock, patch
from wikipedia_maintenance.analyzers.http_links import HttpLinksAnalyzer
from wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
from wikipedia_maintenance.orchestrator.orchestrator import DeadLinkOrchestrator
from wikipedia_maintenance.utils.publisher import Corrector
from wikipedia_maintenance.utils.https_verification_cache import VerificationStatus


class TestHttpsEndToEnd:
    """End-to-end integration tests for HTTPS conversion."""

    def test_e2e_simple_http_to_https_conversion(self):
        """Test complete flow: article → analyzer → verification → correction → final wikicode."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=True, timeout=10.0)
            )
            with patch('wikipedia_maintenance.utils.database.DatabaseManager'):
                with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationCache') as mock_cache:
                    with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationService') as mock_service:
                        # Mock successful HTTPS verification
                        mock_service.return_value.verify_domain.return_value = Mock(
                            status=VerificationStatus.HTTPS_AVAILABLE,
                            domain="example.com",
                            https_url="https://example.com",
                            http_status_code=200
                        )
                        mock_cache.return_value.get.return_value = None
                        
                        # Original wikicode with HTTP link
                        original_wikicode = "Voir http://example.com/page pour plus d'informations."
                        
                        # Step 1: Analyzer detects HTTP link and verifies HTTPS
                        analyzer = HttpLinksAnalyzer()
                        issues = analyzer.analyze(original_wikicode)
                        
                        # Verify analyzer created http_link issue
                        assert len(issues) == 1
                        assert issues[0].issue_type == "http_link"
                        assert issues[0].original_text == "http://example.com/page"
                        assert issues[0].suggested_text == "https://example.com/page"
                        
                        # Step 2: Corrector applies the correction
                        corrector = Corrector(original_wikicode)
                        final_wikicode = corrector.apply_corrections(issues)
                        
                        # Step 3: Verify final wikicode has HTTPS
                        assert "https://example.com/page" in final_wikicode
                        assert "http://example.com/page" not in final_wikicode
                        assert final_wikicode == "Voir https://example.com/page pour plus d'informations."

    def test_e2e_no_conversion_when_https_unavailable(self):
        """Test that no conversion happens when HTTPS is unavailable."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=True, timeout=10.0)
            )
            with patch('wikipedia_maintenance.utils.database.DatabaseManager'):
                with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationCache') as mock_cache:
                    with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationService') as mock_service:
                        # Mock HTTPS unavailable
                        mock_service.return_value.verify_domain.return_value = Mock(
                            status=VerificationStatus.HTTPS_UNAVAILABLE,
                            domain="example.com",
                            http_status_code=404
                        )
                        mock_cache.return_value.get.return_value = None
                        
                        original_wikicode = "Voir http://example.com/page pour plus d'informations."
                        
                        # Step 1: Analyzer detects HTTP link but no conversion proposed
                        analyzer = HttpLinksAnalyzer()
                        issues = analyzer.analyze(original_wikicode)
                        
                        # Verify no issue created (HTTPS unavailable)
                        assert len(issues) == 0
                        
                        # Step 2: Corrector applies empty corrections
                        corrector = Corrector(original_wikicode)
                        final_wikicode = corrector.apply_corrections(issues)
                        
                        # Step 3: Verify wikicode unchanged
                        assert final_wikicode == original_wikicode
                        assert "http://example.com/page" in final_wikicode

    def test_e2e_timeout_no_conversion(self):
        """Test that no conversion happens on timeout."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=True, timeout=10.0)
            )
            with patch('wikipedia_maintenance.utils.database.DatabaseManager'):
                with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationCache') as mock_cache:
                    with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationService') as mock_service:
                        # Mock timeout error
                        mock_service.return_value.verify_domain.return_value = Mock(
                            status=VerificationStatus.CHECK_FAILED,
                            domain="example.com",
                            error_type="TIMEOUT"
                        )
                        mock_cache.return_value.get.return_value = None
                        
                        original_wikicode = "Voir http://example.com/page pour plus d'informations."
                        
                        analyzer = HttpLinksAnalyzer()
                        issues = analyzer.analyze(original_wikicode)
                        
                        # No conversion on timeout
                        assert len(issues) == 0
                        
                        corrector = Corrector(original_wikicode)
                        final_wikicode = corrector.apply_corrections(issues)
                        
                        assert final_wikicode == original_wikicode

    def test_e2e_dns_error_no_conversion(self):
        """Test that no conversion happens on DNS error."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=True, timeout=10.0)
            )
            with patch('wikipedia_maintenance.utils.database.DatabaseManager'):
                with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationCache') as mock_cache:
                    with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationService') as mock_service:
                        # Mock DNS error
                        mock_service.return_value.verify_domain.return_value = Mock(
                            status=VerificationStatus.CHECK_FAILED,
                            domain="example.com",
                            error_type="DNS_ERROR"
                        )
                        mock_cache.return_value.get.return_value = None
                        
                        original_wikicode = "Voir http://example.com/page pour plus d'informations."
                        
                        analyzer = HttpLinksAnalyzer()
                        issues = analyzer.analyze(original_wikicode)
                        
                        assert len(issues) == 0
                        
                        corrector = Corrector(original_wikicode)
                        final_wikicode = corrector.apply_corrections(issues)
                        
                        assert final_wikicode == original_wikicode

    def test_e2e_tls_error_no_conversion(self):
        """Test that no conversion happens on TLS error."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=True, timeout=10.0)
            )
            with patch('wikipedia_maintenance.utils.database.DatabaseManager'):
                with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationCache') as mock_cache:
                    with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationService') as mock_service:
                        # Mock TLS error
                        mock_service.return_value.verify_domain.return_value = Mock(
                            status=VerificationStatus.CHECK_FAILED,
                            domain="example.com",
                            error_type="SSL_ERROR"
                        )
                        mock_cache.return_value.get.return_value = None
                        
                        original_wikicode = "Voir http://example.com/page pour plus d'informations."
                        
                        analyzer = HttpLinksAnalyzer()
                        issues = analyzer.analyze(original_wikicode)
                        
                        assert len(issues) == 0
                        
                        corrector = Corrector(original_wikicode)
                        final_wikicode = corrector.apply_corrections(issues)
                        
                        assert final_wikicode == original_wikicode

    def test_e2e_already_https_no_change(self):
        """Test that HTTPS links are not modified."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=True, timeout=10.0)
            )
            with patch('wikipedia_maintenance.utils.database.DatabaseManager'):
                with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationCache'):
                    with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationService'):
                        original_wikicode = "Voir https://example.com/page pour plus d'informations."
                        
                        analyzer = HttpLinksAnalyzer()
                        issues = analyzer.analyze(original_wikicode)
                        
                        # No issues for HTTPS links
                        assert len(issues) == 0
                        
                        corrector = Corrector(original_wikicode)
                        final_wikicode = corrector.apply_corrections(issues)
                        
                        assert final_wikicode == original_wikicode

    def test_e2e_lien_web_template_conversion(self):
        """Test HTTP→HTTPS conversion in {{Lien web}} template."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=True, timeout=10.0)
            )
            with patch('wikipedia_maintenance.utils.database.DatabaseManager'):
                with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationCache') as mock_cache:
                    with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationService') as mock_service:
                        # Mock successful HTTPS verification
                        mock_service.return_value.verify_domain.return_value = Mock(
                            status=VerificationStatus.HTTPS_AVAILABLE,
                            domain="example.com",
                            https_url="https://example.com",
                            http_status_code=200
                        )
                        mock_cache.return_value.get.return_value = None
                        
                        original_wikicode = "{{Lien web |url=http://example.com/page |titre=Exemple |site=example.com }}"
                        
                        analyzer = HttpLinksAnalyzer()
                        issues = analyzer.analyze(original_wikicode)
                        
                        # Should create issue for HTTP URL in template
                        assert len(issues) == 1
                        assert issues[0].issue_type == "http_link"
                        assert issues[0].extra['template_name'] == "Lien web"
                        
                        corrector = Corrector(original_wikicode)
                        final_wikicode = corrector.apply_corrections(issues)
                        
                        # Verify template structure preserved but URL converted
                        assert "{{Lien web" in final_wikicode
                        assert "|titre=Exemple" in final_wikicode
                        assert "|site=example.com" in final_wikicode
                        assert "https://example.com/page" in final_wikicode
                        assert "http://example.com/page" not in final_wikicode

    def test_e2e_multiple_links_mixed_results(self):
        """Test multiple HTTP links with mixed HTTPS availability."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=True, timeout=10.0)
            )
            with patch('wikipedia_maintenance.utils.database.DatabaseManager'):
                with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationCache') as mock_cache:
                    with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationService') as mock_service:
                        # Mock different results for different domains
                        mock_service.return_value.verify_domain.side_effect = [
                            Mock(status=VerificationStatus.HTTPS_AVAILABLE, domain="available.com", https_url="https://available.com", http_status_code=200),
                            Mock(status=VerificationStatus.HTTPS_UNAVAILABLE, domain="unavailable.com", http_status_code=404),
                            Mock(status=VerificationStatus.HTTPS_AVAILABLE, domain="alsoworks.com", https_url="https://alsoworks.com", http_status_code=200),
                        ]
                        mock_cache.return_value.get.return_value = None
                        
                        original_wikicode = "Voir http://available.com, http://unavailable.com et http://alsoworks.com."
                        
                        analyzer = HttpLinksAnalyzer()
                        issues = analyzer.analyze(original_wikicode)
                        
                        # Should create issues only for available domains
                        assert len(issues) == 2
                        assert all(issue.issue_type == "http_link" for issue in issues)
                        
                        corrector = Corrector(original_wikicode)
                        final_wikicode = corrector.apply_corrections(issues)
                        
                        # Verify only available domains converted
                        assert "https://available.com" in final_wikicode
                        assert "https://alsoworks.com" in final_wikicode
                        assert "http://unavailable.com" in final_wikicode  # Not converted
                        assert "http://available.com" not in final_wikicode
                        assert "http://alsoworks.com" not in final_wikicode

    def test_e2e_cache_hit_scenario(self):
        """Test scenario where cache hit speeds up verification."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=True, timeout=10.0)
            )
            with patch('wikipedia_maintenance.utils.database.DatabaseManager'):
                with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationCache') as mock_cache:
                    with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationService'):
                        # Mock cache hit
                        mock_cache.return_value.get.return_value = {
                            'status_enum': VerificationStatus.HTTPS_AVAILABLE,
                            'https_url': 'https://example.com',
                            'http_status_code': 200
                        }
                        
                        original_wikicode = "Voir http://example.com/page pour plus d'informations."
                        
                        analyzer = HttpLinksAnalyzer()
                        issues = analyzer.analyze(original_wikicode)
                        
                        # Should use cache and still propose conversion
                        assert len(issues) == 1
                        assert analyzer.stats['https_cache_hits'] == 1
                        
                        corrector = Corrector(original_wikicode)
                        final_wikicode = corrector.apply_corrections(issues)
                        
                        assert "https://example.com/page" in final_wikicode

    def test_e2e_functionality_disabled(self):
        """Test that no conversion happens when functionality is disabled."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=False, timeout=10.0)
            )
            
            original_wikicode = "Voir http://example.com/page pour plus d'informations."
            
            analyzer = HttpLinksAnalyzer()
            issues = analyzer.analyze(original_wikicode)
            
            # Should not create any issues when disabled
            assert len(issues) == 0
            assert analyzer.enabled is False
            
            corrector = Corrector(original_wikicode)
            final_wikicode = corrector.apply_corrections(issues)
            
            assert final_wikicode == original_wikicode

    def test_e2e_orchestrator_integration(self):
        """Test integration with DeadLinkOrchestrator."""
        with patch('wikipedia_maintenance.analyzers.http_links.load_config') as mock_config:
            mock_config.return_value = Mock(
                https_verification=Mock(enabled=True, timeout=10.0)
            )
            with patch('wikipedia_maintenance.utils.database.DatabaseManager'):
                with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationCache') as mock_cache:
                    with patch('wikipedia_maintenance.analyzers.http_links.HttpsVerificationService') as mock_service:
                        # Mock successful HTTPS verification
                        mock_service.return_value.verify_domain.return_value = Mock(
                            status=VerificationStatus.HTTPS_AVAILABLE,
                            domain="example.com",
                            https_url="https://example.com",
                            http_status_code=200
                        )
                        mock_cache.return_value.get.return_value = None
                        
                        original_wikicode = "Voir http://example.com/page pour plus d'informations."
                        
                        # Use orchestrator to run complete analysis
                        orchestrator = DeadLinkOrchestrator(language='fr')
                        result = orchestrator.analyze(original_wikicode)
                        
                        # Verify result contains HTTP link corrections
                        assert result.http_links_found >= 1
                        assert "https://example.com/page" in result.corrected_content
                        assert "http://example.com/page" not in result.corrected_content
                        assert result.corrected_content != original_wikicode


if __name__ == "__main__":
    pytest.main([__file__, "-v"])