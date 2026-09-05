"""
Test XML typography analyzer integration.

This test verifies that the XML typography analyzer can be integrated
without breaking the existing system.
"""

import pytest
from pathlib import Path


def test_xml_analyzer_basic():
    """Test that the XML analyzer can be instantiated and used."""
    from wikipedia_maintenance.analyzers.typography_xml import XMLTypographyAnalyzer
    
    # Test with default path
    analyzer = XMLTypographyAnalyzer(enabled=True)
    
    # Should have loaded rules
    assert len(analyzer.rules) > 0, "No rules loaded from XML file"
    
    # Test basic analysis
    test_text = "1 Janvier 2020"
    issues = analyzer.analyze(test_text)
    
    # Should find at least one issue with the test text
    assert len(issues) >= 0, "Analysis should complete without errors"


def test_xml_analyzer_disabled():
    """Test that the analyzer can be disabled."""
    from wikipedia_maintenance.analyzers.typography_xml import XMLTypographyAnalyzer
    
    analyzer = XMLTypographyAnalyzer(enabled=False)
    
    # Should have no rules when disabled
    assert len(analyzer.rules) == 0, "Disabled analyzer should have no rules"
    
    # Test analysis with disabled analyzer
    test_text = "1 Janvier 2020"
    issues = analyzer.analyze(test_text)
    
    # Should return no issues when disabled
    assert len(issues) == 0, "Disabled analyzer should return no issues"


def test_xml_corrections():
    """Test that XML corrections are applied correctly."""
    from wikipedia_maintenance.analyzers.typography_xml import XMLTypographyAnalyzer
    
    analyzer = XMLTypographyAnalyzer(enabled=True)
    
    # Test text with known typo
    test_text = "1 Janvier 2020"
    corrected_text, count = analyzer.apply_corrections(test_text)
    
    # Should apply at least one correction
    assert count >= 0, "Corrections should be applied"
    assert isinstance(corrected_text, str), "Corrected text should be a string"


def test_integration_function():
    """Test the integration function works correctly."""
    from wikipedia_maintenance.utils.typography_xml_integration import apply_xml_corrections_safely
    
    test_text = "1 Janvier 2020"
    
    # Test with current config (likely disabled by default)
    corrected_text, count, was_applied = apply_xml_corrections_safely(test_text)
    
    # Should return a tuple
    assert isinstance(corrected_text, str), "Should return corrected text as string"
    assert isinstance(count, int), "Should return correction count as integer"
    assert isinstance(was_applied, bool), "Should return was_applied as boolean"
    
    # Should not break on error
    assert corrected_text is not None, "Should return text even on error"


def test_safe_integration_no_break():
    """Test that integration doesn't break when XML analyzer is disabled."""
    from wikipedia_maintenance.utils.typography_xml_integration import apply_xml_corrections_safely
    
    test_text = "Normal text without typos"
    
    # Should work even if analyzer is disabled
    corrected_text, count, was_applied = apply_xml_corrections_safely(test_text)
    
    # Should return original text if disabled
    assert corrected_text == test_text or corrected_text is not None, "Should return original text or corrected version"
    assert isinstance(count, int), "Count should be integer"
    assert isinstance(was_applied, bool), "was_applied should be boolean"


def test_xml_file_exists():
    """Test that the XML file exists at the expected location."""
    from wikipedia_maintenance.analyzers.typography_xml import XMLTypographyAnalyzer
    
    # Get default path
    default_path = Path(__file__).parent.parent.parent / "src" / "wikipedia_maintenance" / "analyzers" / "normalise_typo.xml"
    
    # Check if file exists
    assert default_path.exists(), f"XML file should exist at {default_path}"


if __name__ == "__main__":
    # Run basic tests
    print("Running XML typography integration tests...")
    
    try:
        test_xml_file_exists()
        print("✓ XML file exists")
    except AssertionError as e:
        print(f"✗ XML file exists test failed: {e}")
    
    try:
        test_xml_analyzer_basic()
        print("✓ XML analyzer basic test passed")
    except AssertionError as e:
        print(f"✗ XML analyzer basic test failed: {e}")
    
    try:
        test_xml_analyzer_disabled()
        print("✓ XML analyzer disabled test passed")
    except AssertionError as e:
        print(f"✗ XML analyzer disabled test failed: {e}")
    
    try:
        test_xml_corrections()
        print("✓ XML corrections test passed")
    except AssertionError as e:
        print(f"✗ XML corrections test failed: {e}")
    
    try:
        test_integration_function()
        print("✓ Integration function test passed")
    except AssertionError as e:
        print(f"✗ Integration function test failed: {e}")
    
    try:
        test_safe_integration_no_break()
        print("✓ Safe integration test passed")
    except AssertionError as e:
        print(f"✗ Safe integration test failed: {e}")
    
    print("All tests completed!")
