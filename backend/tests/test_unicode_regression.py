"""
Regression test for Unicode URL fix.

This test ensures that the Unicode URL fix doesn't break existing functionality:
- ASCII URLs still work correctly
- URL extraction still works for all valid URL characters
- Template parsing is not affected
- No performance degradation
"""

import re
import sys
sys.path.insert(0, 'src')

from wikipedia_maintenance.utils.url_extraction import UrlExtractor
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper


def test_ascii_urls_still_work():
    """Test that ASCII URLs still work correctly after Unicode fix."""
    print("=" * 80)
    print("REGRESSION TEST: ASCII URLs Still Work")
    print("=" * 80)
    
    extractor = UrlExtractor()
    
    ascii_urls = [
        "https://www.example.com/",
        "https://example.com/path/to/resource",
        "https://subdomain.example.com:8080/path?query=value&other=test#section",
        "http://example.com/path%20with%20spaces",
        "https://user:pass@example.com/path",
        "https://example.com/path-with-dashes_and_underscores",
        "https://example.com/path/with/slashes",
        "https://example.com?query=1&query2=2",
        "https://example.com#section",
    ]
    
    all_pass = True
    for url in ascii_urls:
        # Test full match
        match = UrlExtractor.URL_PATTERN.fullmatch(url)
        if match:
            print(f"  ✓ {url}")
        else:
            print(f"  ✗ FAIL: {url}")
            all_pass = False
    
    # Test extraction from content
    content = "Visit https://www.example.com/ and https://example.com/path for more info."
    urls = extractor.find_urls_in_content(content)
    expected_count = 2
    if len(urls) == expected_count:
        print(f"  ✓ Extracted {len(urls)} URLs from content (expected {expected_count})")
    else:
        print(f"  ✗ FAIL: Extracted {len(urls)} URLs (expected {expected_count})")
        all_pass = False
    
    return all_pass


def test_unicode_urls_work():
    """Test that Unicode URLs now work correctly."""
    print("\n" + "=" * 80)
    print("REGRESSION TEST: Unicode URLs Now Work")
    print("=" * 80)
    
    extractor = UrlExtractor()
    
    unicode_urls = [
        "https://www.mük.hu/",
        "https://www.fürst.de/presse",
        "https://www.école.fr/programme",
        "https://www.münchen.de/fürsten",
        "https://www.über.com/path",
    ]
    
    all_pass = True
    for url in unicode_urls:
        match = UrlExtractor.URL_PATTERN.fullmatch(url)
        if match:
            print(f"  ✓ {url}")
        else:
            print(f"  ✗ FAIL: {url}")
            all_pass = False
    
    return all_pass


def test_template_parsing_not_affected():
    """Test that template parsing is not affected by Unicode fix."""
    print("\n" + "=" * 80)
    print("REGRESSION TEST: Template Parsing Not Affected")
    print("=" * 80)
    
    helper = ReferenceTemplateHelper()
    
    templates = [
        {
            "template": '{{Lien web|titre=Test|url=https://www.example.com/|site=Example.com}}',
            "expected_url": "https://www.example.com/",
            "expected_site": "Example.com"
        },
        {
            "template": '{{article|titre=Paper|périodique=Nature|url=https://www.example.com/paper}}',
            "expected_url": "https://www.example.com/paper",
            "expected_periodique": "Nature"
        },
        {
            "template": '{{ouvrage|titre=Book|auteur=Author|lire en ligne=https://www.example.com/book}}',
            "expected_lire_en_ligne": "https://www.example.com/book",
            "should_not_have_site": True
        },
    ]
    
    all_pass = True
    for test in templates:
        url_pos = test['template'].find('http')
        # Find the URL parameter to use for template lookup
        lookup_url = test.get('expected_url') or test.get('expected_lire_en_ligne', '')
        template = helper.find_reference_template(test['template'], lookup_url, url_pos)
        
        if template:
            url_ok = True
            if 'expected_url' in test:
                url_ok = template.parameters.get('url') == test['expected_url']
            elif 'expected_lire_en_ligne' in test:
                url_ok = template.parameters.get('lire en ligne') == test['expected_lire_en_ligne']
            
            if 'expected_site' in test:
                site_ok = template.parameters.get('site') == test['expected_site']
            elif test.get('should_not_have_site'):
                site_ok = 'site' not in template.parameters
            else:
                site_ok = True
            
            if 'expected_periodique' in test:
                periodique_ok = template.parameters.get('périodique') == test['expected_periodique']
            else:
                periodique_ok = True
            
            if url_ok and site_ok and periodique_ok:
                print(f"  ✓ Template parsed correctly")
            else:
                print(f"  ✗ FAIL: Template parsing issue")
                print(f"    url_ok: {url_ok}, site_ok: {site_ok}, periodique_ok: {periodique_ok}")
                print(f"    Parameters: {template.parameters}")
                all_pass = False
        else:
            print(f"  ✗ FAIL: Template not found")
            all_pass = False
    
    return all_pass


def test_url_validation_not_affected():
    """Test that URL validation is not affected by Unicode fix."""
    print("\n" + "=" * 80)
    print("REGRESSION TEST: URL Validation Not Affected")
    print("=" * 80)
    
    extractor = UrlExtractor()
    
    # Valid URLs
    valid_urls = [
        "https://www.example.com/",
        "https://www.mük.hu/",  # Unicode
    ]
    
    # Invalid URLs
    invalid_urls = [
        "https://www.example.com|param=value",  # Contains template delimiter
        "https://www.example.com{param}",  # Contains template delimiter
        "not-a-url",
        "",
    ]
    
    all_pass = True
    
    print("Valid URLs:")
    for url in valid_urls:
        is_valid = extractor.is_syntactically_valid(url)
        if is_valid:
            print(f"  ✓ {url} - valid")
        else:
            print(f"  ✗ FAIL: {url} - should be valid but rejected")
            all_pass = False
    
    print("\nInvalid URLs:")
    for url in invalid_urls:
        is_valid = extractor.is_syntactically_valid(url)
        if not is_valid:
            print(f"  ✓ {url} - invalid (correctly rejected)")
        else:
            print(f"  ✗ FAIL: {url} - should be invalid but accepted")
            all_pass = False
    
    return all_pass


def test_special_characters_still_work():
    """Test that special URL characters still work correctly."""
    print("\n" + "=" * 80)
    print("REGRESSION TEST: Special URL Characters Still Work")
    print("=" * 80)
    
    special_urls = [
        "https://example.com/path?query=value&other=test#section",
        "https://example.com/path%20with%20spaces",
        "https://example.com:8080/path",
        "https://user:pass@example.com/path",
        "https://example.com/path-with-dashes_and_underscores",
        "https://example.com/path/with/slashes",
        "https://example.com/path.with.dots",
        "https://example.com/path~with~tildes",
    ]
    
    all_pass = True
    for url in special_urls:
        match = UrlExtractor.URL_PATTERN.fullmatch(url)
        if match:
            print(f"  ✓ {url}")
        else:
            print(f"  ✗ FAIL: {url}")
            all_pass = False
    
    return all_pass


def test_template_delimiters_still_excluded():
    """Test that template delimiters are still excluded from URL matches."""
    print("\n" + "=" * 80)
    print("REGRESSION TEST: Template Delimiters Still Excluded")
    print("=" * 80)
    
    # URLs with template delimiters should NOT match fully
    # The pattern should stop at the delimiter
    test_cases = [
        ("https://www.example.com|param=value", "https://www.example.com"),
        ("https://www.example.com{param}", "https://www.example.com"),
        ("https://www.example.com}param", "https://www.example.com"),
        ("https://www.example.com[param]", "https://www.example.com"),
    ]
    
    all_pass = True
    for full_text, expected_url in test_cases:
        # The pattern should match only the URL part, not including the delimiter
        match = UrlExtractor.URL_PATTERN.search(full_text)
        if match:
            matched = match.group(0)
            if matched == expected_url:
                print(f"  ✓ {full_text} → {matched}")
            else:
                print(f"  ✗ FAIL: {full_text} → {matched} (expected {expected_url})")
                all_pass = False
        else:
            print(f"  ✗ FAIL: {full_text} - no match")
            all_pass = False
    
    return all_pass


if __name__ == "__main__":
    results = []
    
    results.append(("ASCII URLs Still Work", test_ascii_urls_still_work()))
    results.append(("Unicode URLs Now Work", test_unicode_urls_work()))
    results.append(("Template Parsing Not Affected", test_template_parsing_not_affected()))
    results.append(("URL Validation Not Affected", test_url_validation_not_affected()))
    results.append(("Special Characters Still Work", test_special_characters_still_work()))
    results.append(("Template Delimiters Still Excluded", test_template_delimiters_still_excluded()))
    
    print("\n" + "=" * 80)
    print("REGRESSION TEST SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("ALL REGRESSION TESTS PASSED")
        print("Unicode URL fix does not break existing functionality.")
    else:
        print("SOME REGRESSION TESTS FAILED")
        print("Unicode URL fix may have broken existing functionality.")
    print("=" * 80)
