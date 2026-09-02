"""
Test URL normalization for dead link detection.

This test verifies that URL normalization works correctly.
Note: www. and m. prefixes are NOT removed during URL normalization,
as www.example.com and example.com may have different content.
www. removal is only done for the 'Site' parameter in reference templates.
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from wikipedia_maintenance.utils.tracking_service import normalize_url


def test_url_normalization():
    """Test that URL normalization preserves www. and m. prefixes."""
    
    # Test cases: URLs should preserve www. and m. prefixes during normalization
    test_cases = [
        ("https://www.vlaamsbouwmeester.be/path", "https://www.vlaamsbouwmeester.be/path"),
        ("http://www.example.com/test", "http://www.example.com/test"),
        ("https://www.example.com/", "https://www.example.com/"),
        ("http://www.example.com", "http://www.example.com/"),  # Root path gets "/" added
        ("https://m.example.com/mobile", "https://m.example.com/mobile"),  # m. prefix preserved
        ("https://WWW.EXAMPLE.COM/TEST", "https://www.example.com/TEST"),  # Case normalization
        ("https://www.example.com?query=1", "https://www.example.com/?query=1"),  # Root path with query
        ("https://www.example.com#section", "https://www.example.com/#section"),  # Root path with fragment
    ]
    
    print("Testing URL normalization (www. and m. prefixes preserved):")
    for original, expected in test_cases:
        normalized = normalize_url(original)
        status = "PASS" if normalized == expected else "FAIL"
        print(f"{status}: {original} -> {normalized} (expected: {expected})")
        assert normalized == expected, f"Expected {expected}, got {normalized}"
    
    print("\nAll URL normalization tests passed!")


def test_case_normalization():
    """Test that URLs are case-normalized in scheme and netloc."""
    
    # Test that scheme and netloc are lowercased
    test_cases = [
        ("HTTPS://WWW.EXAMPLE.COM/PATH", "https://www.example.com/PATH"),
        ("HTTP://Example.COM/Test", "http://example.com/Test"),
        ("HtTpS://WwW.ExAmPlE.CoM/", "https://www.example.com/"),
    ]
    
    print("\nTesting case normalization:")
    for original, expected in test_cases:
        normalized = normalize_url(original)
        status = "PASS" if normalized == expected else "FAIL"
        print(f"{status}: {original} -> {normalized} (expected: {expected})")
        assert normalized == expected, f"Expected {expected}, got {normalized}"
    
    print("\nAll case normalization tests passed!")


if __name__ == "__main__":
    test_url_normalization()
    test_case_normalization()
    print("\nSUCCESS: All tests passed successfully!")
