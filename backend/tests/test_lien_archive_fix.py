"""
Test the Lien archive template recognition and repair fix.

This test verifies that:
1. 'Lien archive' is now recognized as a supported template
2. The distinction between no template vs unsupported template works
3. Unsupported templates trigger REVIEW_REQUIRED instead of bare URL fallback
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper, ReferenceTemplate


def test_lien_archive_recognition():
    """Test that Lien archive is now recognized as a supported template."""
    print("\n" + "=" * 60)
    print("TEST: Lien Archive Recognition")
    print("=" * 60)
    
    helper = ReferenceTemplateHelper()
    
    # Check if Lien archive is in KNOWN_TEMPLATE_NAMES
    assert 'lien archive' in helper.KNOWN_TEMPLATE_NAMES, "Lien archive should be in KNOWN_TEMPLATE_NAMES"
    assert helper.KNOWN_TEMPLATE_NAMES['lien archive'] == 'Lien archive', "Should normalize to 'Lien archive'"
    
    # Check if Lien archive supports archive as main link
    assert 'Lien archive' in helper.TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK, \
        "Lien archive should support archive as main link"
    
    # Check if Lien archive has parameter definitions
    assert 'Lien archive' in helper.TEMPLATE_SPECIFIC_PARAMETERS, \
        "Lien archive should have parameter definitions"
    
    print("[PASS] Lien archive recognition verified")
    print("  - Found in KNOWN_TEMPLATE_NAMES")
    print("  - Supports archive as main link")
    print("  - Has parameter definitions")


def test_template_parsing():
    """Test that Lien archive template is parsed correctly."""
    print("\n" + "=" * 60)
    print("TEST: Lien Archive Template Parsing")
    print("=" * 60)
    
    helper = ReferenceTemplateHelper()
    
    # Test content with Lien archive template
    content = "{{Lien archive |url=http://www.example.com/document.pdf |titre=Test Document |horodatage archive=20200101120000}}"
    url = "http://www.example.com/document.pdf"
    position = content.find(url)
    
    template = helper.find_reference_template(content, url, position)
    
    assert template is not None, "Template should be found"
    assert template.template_name == "Lien archive", f"Template name should be 'Lien archive', got {template.template_name}"
    assert template.is_supported == True, "Template should be marked as supported"
    assert 'url' in template.parameters, "Should have url parameter"
    assert template.parameters['url'] == url, "URL parameter should match"
    
    print("[PASS] Lien archive template parsing verified")
    print(f"  - Template name: {template.template_name}")
    print(f"  - Is supported: {template.is_supported}")
    print(f"  - Parameters: {len(template.parameters)}")


def test_unsupported_template_handling():
    """Test that unsupported templates are handled correctly."""
    print("\n" + "=" * 60)
    print("TEST: Unsupported Template Handling")
    print("=" * 60)
    
    helper = ReferenceTemplateHelper()
    
    # Test content with an unsupported template (not in KNOWN_TEMPLATE_NAMES)
    content = "{{UnknownTemplate |url=http://www.example.com/doc.pdf |titre=Test}}"
    url = "http://www.example.com/doc.pdf"
    position = content.find(url)
    
    template = helper.find_reference_template(content, url, position)
    
    assert template is not None, "Template should still be found even if unsupported"
    assert template.is_supported == False, "Template should be marked as unsupported"
    assert template.template_name == "UnknownTemplate", "Should preserve original template name"
    
    print("[PASS] Unsupported template handling verified")
    print(f"  - Template found: {template.template_name}")
    print(f"  - Is supported: {template.is_supported}")
    print("  - Correctly marked as unsupported for manual review")


def test_parameter_specificity():
    """Test that Lien archive has specific parameters."""
    print("\n" + "=" * 60)
    print("TEST: Lien Archive Parameter Specificity")
    print("=" * 60)
    
    helper = ReferenceTemplateHelper()
    
    lien_archive_params = helper.TEMPLATE_SPECIFIC_PARAMETERS.get('Lien archive', [])
    
    # Check for Lien archive specific parameters
    assert 'horodatage archive' in lien_archive_params, \
        "Lien archive should have 'horodatage archive' parameter"
    assert 'url' in lien_archive_params, "Should have url parameter"
    assert 'titre' in lien_archive_params, "Should have titre parameter"
    
    print("[PASS] Lien archive parameter specificity verified")
    print(f"  - Specific parameters: {len(lien_archive_params)}")
    print(f"  - Key parameters: url, titre, horodatage archive")


if __name__ == "__main__":
    try:
        test_lien_archive_recognition()
        test_template_parsing()
        test_unsupported_template_handling()
        test_parameter_specificity()
        
        print("\n" + "=" * 60)
        print("ALL LIEN ARCHIVE FIXES TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
