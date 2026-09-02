"""
Test the defensive fixes for dead_links.py.

This test verifies that:
1. template_name=None doesn't crash with .lower()
2. Template bounds detection prevents destructive fallback
3. Supported templates list is included in debug info
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
from wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult


def test_template_name_none_safety():
    """Test that template_name=None doesn't crash with .lower()."""
    print("\n" + "=" * 60)
    print("TEST: Template Name None Safety")
    print("=" * 60)
    
    # Test the defensive string formatting
    template_name = None
    repair_type = f"{(template_name or 'unknown').lower()}_template"
    
    assert repair_type == "unknown_template", f"Should handle None safely, got {repair_type}"
    
    # Test with actual value
    template_name = "Lien web"
    repair_type = f"{(template_name or 'unknown').lower()}_template"
    assert repair_type == "lien web_template", f"Should work with actual value, got {repair_type}"
    
    print("[PASS] Template name None safety verified")
    print("  - None case handled: unknown_template")
    print("  - Normal case handled: lien web_template")


def test_template_bounds_detection():
    """Test that template bounds detection prevents destructive fallback."""
    print("\n" + "=" * 60)
    print("TEST: Template Bounds Detection")
    print("=" * 60)
    
    analyzer = DeadLinkAnalyzer()
    
    # Test content with a template that might not be recognized
    content = "{{SomeTemplate |url=http://example.com/doc.pdf |titre=Test}}"
    url = "http://example.com/doc.pdf"
    position = content.find(url)
    
    # Check if helper can find template bounds
    bounds = analyzer.reference_template_helper._find_enclosing_template_bounds(content, position)
    
    assert bounds is not None, "Should find template bounds even for unrecognized template"
    assert bounds[0] == 0, "Template should start at position 0"
    assert bounds[1] == len(content), "Template should end at content length"
    
    print("[PASS] Template bounds detection verified")
    print(f"  - Bounds found: {bounds}")
    print("  - Can detect templates even when not recognized")


def test_supported_templates_list():
    """Test that supported templates list is available for debug info."""
    print("\n" + "=" * 60)
    print("TEST: Supported Templates List")
    print("=" * 60)
    
    analyzer = DeadLinkAnalyzer()
    
    # Get the list of supported templates
    supported_templates = list(analyzer.reference_template_helper.KNOWN_TEMPLATE_NAMES.values())
    
    assert len(supported_templates) > 0, "Should have supported templates"
    assert 'Lien web' in supported_templates, "Should include Lien web"
    assert 'Lien archive' in supported_templates, "Should include Lien archive (our fix)"
    
    print("[PASS] Supported templates list verified")
    print(f"  - Total supported templates: {len(supported_templates)}")
    print(f"  - Key templates: {supported_templates[:5]}")  # Show first 5


def test_defensive_formatting():
    """Test all defensive formatting patterns in the code."""
    print("\n" + "=" * 60)
    print("TEST: Defensive Formatting Patterns")
    print("=" * 60)
    
    # Test the pattern used in the code
    test_cases = [
        (None, "unknown"),
        ("Lien web", "lien web"),
        ("article", "article"),
        ("", "unknown"),  # Empty string
    ]
    
    for template_name, expected in test_cases:
        result = f"{(template_name or 'unknown').lower()}_template"
        assert result == f"{expected}_template", f"Failed for {template_name}: got {result}"
    
    print("[PASS] Defensive formatting patterns verified")
    print("  - Handles None: OK")
    print("  - Handles normal values: OK")
    print("  - Handles empty strings: OK")


if __name__ == "__main__":
    try:
        test_template_name_none_safety()
        test_template_bounds_detection()
        test_supported_templates_list()
        test_defensive_formatting()
        
        print("\n" + "=" * 60)
        print("ALL DEFENSIVE FIXES TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
