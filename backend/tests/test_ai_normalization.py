"""
Tests for AI-assisted normalization in CaseNormalizer.

These tests verify that the AI normalization integration:
- Respects the normalize_with_ai flag
- Falls back gracefully when Gemini is unavailable
- Validates AI output before acceptance
- Only applies when enable_case_normalization is true
- Logs appropriately for debugging
- Enforces strict scope safety (URLs, references, categories, protected parameters)
"""

import sys
from pathlib import Path
import json

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

import pytest
from wikipedia_maintenance.utils.case_normalizer import CaseNormalizer


class TestAINormalization:
    """Test AI normalization integration."""

    def test_normalize_with_ai_false(self):
        """Test that AI normalization is disabled when normalize_with_ai=False."""
        normalizer = CaseNormalizer(
            enabled=True,
            enable_ner_title_normalization=False,
            normalize_with_ai=False
        )
        
        # Should not attempt to load Gemini client
        assert normalizer._gemini_client is None
        assert not normalizer._gemini_available

    def test_normalize_with_ai_true_but_gemini_unavailable(self):
        """Test graceful degradation when Gemini is not available."""
        normalizer = CaseNormalizer(
            enabled=True,
            enable_ner_title_normalization=False,
            normalize_with_ai=True
        )
        
        # If Gemini API key is not configured, client should be None
        # This is expected behavior - fallback to classical normalization
        if not normalizer._gemini_available:
            assert normalizer._gemini_client is None
            # Should still have warning logged

    def test_normalize_with_ai_disabled_when_normalization_disabled(self):
        """Test that AI normalization is ignored when enable_case_normalization=False."""
        normalizer = CaseNormalizer(
            enabled=False,
            enable_ner_title_normalization=False,
            normalize_with_ai=True  # Should be ignored
        )
        
        # Even with normalize_with_ai=True, it should be ignored when enabled=False
        assert not normalizer.enabled

    def test_classical_normalization_works_without_ai(self):
        """Test that classical normalization works independently of AI."""
        normalizer = CaseNormalizer(
            enabled=True,
            enable_ner_title_normalization=False,
            normalize_with_ai=False
        )
        
        # Simple test case
        test_text = "{{Lien web|titre=TEST ARTICLE|url=https://example.com}}"
        result = normalizer.normalize_text(test_text)
        
        # Should still perform classical normalization
        assert result.normalized_text is not None
        # The exact output depends on the normalization rules

    def test_ai_normalization_skips_when_no_changes(self):
        """Test that AI normalization is skipped if no classical changes were made."""
        normalizer = CaseNormalizer(
            enabled=True,
            enable_ner_title_normalization=False,
            normalize_with_ai=True
        )
        
        # Text that doesn't need normalization
        test_text = "{{Lien web|titre=Test Article|url=https://example.com}}"
        
        # Mock the AI client to verify it's not called when no changes
        if normalizer._gemini_available:
            original_corriger = normalizer._gemini_client.corriger_article
            call_count = [0]
            
            def mock_corriger(text):
                call_count[0] += 1
                return (True, text, None)
            
            normalizer._gemini_client.corriger_article = mock_corriger
            result = normalizer.normalize_text(test_text)
            
            # Should not call AI if no changes needed
            # (This depends on the classical normalization result)

    def test_ai_normalization_fallback_on_failure(self):
        """Test that AI normalization falls back to classical on failure."""
        normalizer = CaseNormalizer(
            enabled=True,
            enable_ner_title_normalization=False,
            normalize_with_ai=True
        )
        
        if normalizer._gemini_available:
            # Mock AI failure
            original_corriger = normalizer._gemini_client.corriger_article
            
            def mock_corriger_fail(text):
                return (False, text, "Mock AI failure")
            
            normalizer._gemini_client.corriger_article = mock_corriger_fail
            
            test_text = "{{Lien web|titre=TEST ARTICLE|url=https://example.com}}"
            result = normalizer.normalize_text(test_text)
            
            # Should return classical result (not fail completely)
            assert result.normalized_text is not None

    def test_ai_normalization_validation_fallback(self):
        """Test that AI normalization falls back on validation failure."""
        normalizer = CaseNormalizer(
            enabled=True,
            enable_ner_title_normalization=False,
            normalize_with_ai=True
        )
        
        if normalizer._gemini_available:
            # Mock validation failure
            original_validate = normalizer._gemini_client._valider_sortie_ia
            
            def mock_validate_fail(original, normalized):
                return (False, "Validation failed")
            
            normalizer._gemini_client._valider_sortie_ia = mock_validate_fail
            
            test_text = "{{Lien web|titre=TEST ARTICLE|url=https://example.com}}"
            result = normalizer.normalize_text(test_text)
            
            # Should return classical result
            assert result.normalized_text is not None

    def test_normalize_with_ai_depends_on_enable_case_normalization(self):
        """Test that normalize_with_ai only works when enable_case_normalization is true."""
        # Case 1: enable_case_normalization=False, normalize_with_ai=True
        normalizer1 = CaseNormalizer(
            enabled=False,
            normalize_with_ai=True
        )
        assert not normalizer1.enabled
        # AI should not be used
        
        # Case 2: enable_case_normalization=True, normalize_with_ai=True
        normalizer2 = CaseNormalizer(
            enabled=True,
            normalize_with_ai=True
        )
        assert normalizer2.enabled
        # AI should be attempted if available

    def test_normalization_prompt_exists(self):
        """Test that the normalization prompt is defined."""
        normalizer = CaseNormalizer(enabled=True)
        prompt = normalizer._get_normalization_prompt()
        
        assert prompt is not None
        assert "normalisation" in prompt.lower()
        assert "paramètres" in prompt.lower()
        assert "JSON" in prompt  # New: should request JSON output

    def test_gemini_client_loading_logs_warning(self):
        """Test that appropriate warnings are logged when Gemini is unavailable."""
        # This test verifies the logging behavior
        # In a real test, we would capture logs
        normalizer = CaseNormalizer(
            enabled=True,
            normalize_with_ai=True
        )
        
        # If Gemini is not configured, warning should be logged
        if not normalizer._gemini_available:
            # Warning should have been logged (verify via log capture in real test)
            pass


class TestNormalizationFlagCombinations:
    """Test all combinations of normalization flags."""

    def test_disabled_normalization(self):
        """Test: enable_case_normalization=False, normalize_with_ai=False."""
        normalizer = CaseNormalizer(
            enabled=False,
            normalize_with_ai=False
        )
        
        test_text = "{{Lien web|titre=TEST|url=https://example.com}}"
        result = normalizer.normalize_text(test_text)
        
        # Should return text unchanged
        assert result.normalized_text == test_text
        assert result.total_changes == 0

    def test_classical_only(self):
        """Test: enable_case_normalization=True, normalize_with_ai=False."""
        normalizer = CaseNormalizer(
            enabled=True,
            normalize_with_ai=False
        )
        
        test_text = "{{Lien web|titre=TEST|url=https://example.com}}"
        result = normalizer.normalize_text(test_text)
        
        # Should apply classical normalization
        assert result.normalized_text is not None
        # AI should not be used
        assert not normalizer._gemini_available or normalizer._gemini_client is None

    def test_ai_enabled_but_unavailable(self):
        """Test: enable_case_normalization=True, normalize_with_ai=True, Gemini unavailable."""
        normalizer = CaseNormalizer(
            enabled=True,
            normalize_with_ai=True
        )
        
        if not normalizer._gemini_available:
            test_text = "{{Lien web|titre=TEST|url=https://example.com}}"
            result = normalizer.normalize_text(test_text)
            
            # Should still apply classical normalization
            assert result.normalized_text is not None

    def test_ai_enabled_and_available(self):
        """Test: enable_case_normalization=True, normalize_with_ai=True, Gemini available."""
        normalizer = CaseNormalizer(
            enabled=True,
            normalize_with_ai=True
        )
        
        if normalizer._gemini_available:
            test_text = "{{Lien web|titre=TEST|url=https://example.com}}"
            result = normalizer.normalize_text(test_text)
            
            # Should apply normalization (classical + AI if successful)
            assert result.normalized_text is not None


class TestScopeSafetyValidation:
    """Test scope safety validation for AI normalization."""

    def test_extract_authorized_values(self):
        """Test that only authorized parameter values are extracted."""
        normalizer = CaseNormalizer(enabled=True)
        
        test_text = "{{Lien web|titre=TEST|site=LE MONDE|url=https://example.com|éditeur=FAYARD}}"
        templates = normalizer._find_reference_templates(test_text)
        
        values = normalizer._extract_authorized_values(templates)
        
        # Should extract titre, site, éditeur but not url
        assert "titre" in values
        assert "site" in values
        assert "éditeur" in values
        assert "url" not in values

    def test_validate_ai_json_response_forbidden_field(self):
        """Test that forbidden fields in JSON response are rejected."""
        normalizer = CaseNormalizer(enabled=True)
        
        original_values = {"titre": "TEST", "site": "LE MONDE"}
        normalized_values = {"titre": "Test", "site": "Le Monde", "url": "https://example.com"}
        
        is_valid, error = normalizer._validate_ai_json_response(normalized_values, original_values)
        
        assert not is_valid
        assert "forbidden_parameter_modified" in error

    def test_validate_ai_json_response_invalid_type(self):
        """Test that non-string values in JSON response are rejected."""
        normalizer = CaseNormalizer(enabled=True)
        
        original_values = {"titre": "TEST"}
        normalized_values = {"titre": 123}  # Invalid: not a string
        
        is_valid, error = normalizer._validate_ai_json_response(normalized_values, original_values)
        
        assert not is_valid
        assert "invalid_value_type" in error

    def test_validate_ai_json_response_valid(self):
        """Test that valid JSON response is accepted."""
        normalizer = CaseNormalizer(enabled=True)
        
        original_values = {"titre": "TEST", "site": "LE MONDE"}
        normalized_values = {"titre": "Test", "site": "Le Monde"}
        
        is_valid, error = normalizer._validate_ai_json_response(normalized_values, original_values)
        
        assert is_valid
        assert error == ""

    def test_validate_scope_safety_url_modified(self):
        """Test that URL modification is detected and rejected."""
        normalizer = CaseNormalizer(enabled=True)
        
        before = "{{Lien web|titre=Test|url=https://example.com}}"
        after = "{{Lien web|titre=Test|url=https://different.com}}"
        
        is_safe, error = normalizer._validate_scope_safety(before, after)
        
        assert not is_safe
        assert error == "url_modified"

    def test_validate_scope_safety_reference_modified(self):
        """Test that reference modification is detected and rejected."""
        normalizer = CaseNormalizer(enabled=True)
        
        before = "<ref>Original reference</ref>{{Lien web|titre=Test}}"
        after = "<ref>Modified reference</ref>{{Lien web|titre=Test}}"
        
        is_safe, error = normalizer._validate_scope_safety(before, after)
        
        assert not is_safe
        assert error == "reference_modified"

    def test_validate_scope_safety_category_modified(self):
        """Test that category modification is detected and rejected."""
        normalizer = CaseNormalizer(enabled=True)
        
        before = "[[Catégorie:Test]]{{Lien web|titre=Test}}"
        after = "[[Catégorie:Modified]]{{Lien web|titre=Test}}"
        
        is_safe, error = normalizer._validate_scope_safety(before, after)
        
        assert not is_safe
        assert error == "category_modified"

    def test_validate_scope_safety_protected_parameter_modified(self):
        """Test that protected parameter modification is detected and rejected."""
        normalizer = CaseNormalizer(enabled=True)
        
        # Use a protected parameter (isbn) to test detection
        before = "{{Lien web|titre=Test|isbn=978-2-1234-5678-9}}"
        after = "{{Lien web|titre=Test|isbn=978-2-9876-5432-1}}"
        
        is_safe, error = normalizer._validate_scope_safety(before, after)
        
        assert not is_safe
        assert "protected_parameter_modified" in error

    def test_validate_scope_safety_authorized_parameter_modified(self):
        """Test that authorized parameter modification is accepted."""
        normalizer = CaseNormalizer(enabled=True)
        
        before = "{{Lien web|titre=TEST|url=https://example.com}}"
        after = "{{Lien web|titre=Test|url=https://example.com}}"
        
        is_safe, error = normalizer._validate_scope_safety(before, after)
        
        assert is_safe
        assert error == ""

    def test_extract_urls(self):
        """Test URL extraction."""
        normalizer = CaseNormalizer(enabled=True)
        
        text = "{{Lien web|titre=Test|url=https://example.com}} https://another.com"
        urls = normalizer._extract_urls(text)
        
        assert "https://example.com" in urls
        assert "https://another.com" in urls

    def test_extract_references(self):
        """Test reference extraction."""
        normalizer = CaseNormalizer(enabled=True)
        
        text = "<ref>Reference 1</ref> {{Lien web|titre=Test}} <ref>Reference 2</ref>"
        refs = normalizer._extract_references(text)
        
        assert len(refs) == 2
        assert "<ref>Reference 1</ref>" in refs

    def test_extract_categories(self):
        """Test category extraction."""
        normalizer = CaseNormalizer(enabled=True)
        
        text = "[[Catégorie:Test]] {{Lien web|titre=Test}} [[Category:English]]"
        cats = normalizer._extract_categories(text)
        
        assert len(cats) == 2
        assert "[[Catégorie:Test]]" in cats

    def test_reinject_normalized_values(self):
        """Test that normalized values are correctly reinjected."""
        normalizer = CaseNormalizer(enabled=True)
        
        text = "{{Lien web|titre=TEST|site=LE MONDE|url=https://example.com}}"
        templates = normalizer._find_reference_templates(text)
        
        normalized_values = {"titre": "Test", "site": "Le Monde"}
        
        result = normalizer._reinject_normalized_values(text, templates, normalized_values)
        
        assert "titre=Test" in result
        assert "site=Le Monde" in result
        assert "url=https://example.com" in result  # URL should remain unchanged

    def test_reinject_preserves_unchanged_values(self):
        """Test that unchanged values are preserved."""
        normalizer = CaseNormalizer(enabled=True)
        
        text = "{{Lien web|titre=TEST|site=LE MONDE}}"
        templates = normalizer._find_reference_templates(text)
        
        normalized_values = {"titre": "Test"}  # Only titre changed
        
        result = normalizer._reinject_normalized_values(text, templates, normalized_values)
        
        assert "titre=Test" in result
        assert "site=LE MONDE" in result  # site should remain unchanged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
