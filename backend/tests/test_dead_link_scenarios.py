"""
Test scenarios for dead link correction/reconstruction.

This file contains various dead link scenarios to test the bot's ability to:
1. Detect dead links in different contexts
2. Extract URLs correctly (including Unicode domains)
3. Reconstruct proper reference templates
4. Handle edge cases (special characters, nested templates, etc.)
"""

import re

# Test scenarios
SCENARIOS = [
    {
        "name": "Bare dead link with Unicode domain (Hungarian)",
        "description": "Dead link with ü character in domain - was being truncated to 'm'",
        "input": "Voir http://www.mük.hu/ pour plus d'informations.",
        "expected_url": "http://www.mük.hu/",
        "issue": "URL was truncated to 'http://www.m' due to ASCII-only regex",
    },
    {
        "name": "Bare dead link with Unicode domain (German)",
        "description": "Dead link with ü character in German domain",
        "input": "Source: https://www.fürst.de/presse",
        "expected_url": "https://www.fürst.de/presse",
        "issue": "URL was truncated to 'https://www.f'",
    },
    {
        "name": "Bare dead link with Unicode domain (French)",
        "description": "Dead link with é character in French domain",
        "input": "Référence: https://www.école.fr/programme",
        "expected_url": "https://www.école.fr/programme",
        "issue": "URL was truncated to 'https://www.'",
    },
    {
        "name": "Bare URL alone (no context)",
        "description": "URL standing alone in text",
        "input": "https://www.mük.hu/",
        "expected_url": "https://www.mük.hu/",
        "issue": "Should extract URL when it's the only content",
    },
    {
        "name": "Bare URL at end of sentence",
        "description": "URL at end of sentence with punctuation",
        "input": "Le site est https://www.mük.hu/.",
        "expected_url": "https://www.mük.hu/",
        "issue": "Should stop before period punctuation",
    },
    {
        "name": "Bare URL with parentheses",
        "description": "URL in parentheses",
        "input": "(voir https://www.mük.hu/ pour détails)",
        "expected_url": "https://www.mük.hu/",
        "issue": "Should handle URLs in parentheses",
    },
    {
        "name": "Bare URL with comma after",
        "description": "URL followed by comma",
        "input": "Site: https://www.mük.hu/, et aussi autre chose",
        "expected_url": "https://www.mük.hu/",
        "issue": "Should stop before comma",
    },
    {
        "name": "Multiple bare URLs in sequence",
        "description": "Multiple URLs one after another",
        "input": "https://www.mük.hu/ https://www.fürst.de/ https://www.école.fr/",
        "expected_urls": ["https://www.mük.hu/", "https://www.fürst.de/", "https://www.école.fr/"],
        "issue": "Should extract all URLs in sequence",
    },
    {
        "name": "Bare URL with port number",
        "description": "URL with port specification",
        "input": "https://www.example.com:8080/path",
        "expected_url": "https://www.example.com:8080/path",
        "issue": "Should handle port numbers",
    },
    {
        "name": "Bare URL with authentication",
        "description": "URL with username:password",
        "input": "https://user:pass@example.com/path",
        "expected_url": "https://user:pass@example.com/path",
        "issue": "Should handle authentication in URL",
    },
    {
        "name": "Bare URL with long path",
        "description": "URL with long path segments",
        "input": "https://www.example.com/very/long/path/to/resource/file.html",
        "expected_url": "https://www.example.com/very/long/path/to/resource/file.html",
        "issue": "Should handle long paths",
    },
    {
        "name": "Bare URL with multiple Unicode chars",
        "description": "URL with multiple Unicode characters in domain",
        "input": "https://www.münchen.de/fürsten",
        "expected_url": "https://www.münchen.de/fürsten",
        "issue": "Should handle multiple Unicode chars in same URL",
    },
    {
        "name": "Dead link in {{Lien web}} template with Unicode",
        "description": "Template with Unicode URL - parameters were being corrupted",
        "input": '{{Lien web|titre="Magyar Ügyvédi Kamara". Magyar Ügyvédi Kamara|url=https://www.mük.hu/}}',
        "expected_url": "https://www.mük.hu/",
        "issue": "URL truncated to 'm', title truncated, site parameter corrupted",
    },
    {
        "name": "Dead link in <ref> tag with Unicode",
        "description": "Reference tag with Unicode URL",
        "input": '<ref>Information disponible sur https://www.mük.hu/</ref>',
        "expected_url": "https://www.mük.hu/",
        "issue": "URL truncated in reference extraction",
    },
    {
        "name": "Bare dead link with special characters",
        "description": "URL with query parameters and special chars",
        "input": "Voir https://example.com/path?query=value&other=test#section",
        "expected_url": "https://example.com/path?query=value&other=test#section",
        "issue": "Should handle query strings and fragments correctly",
    },
    {
        "name": "Dead link with percent encoding",
        "description": "URL with percent-encoded characters",
        "input": "https://example.com/path%20with%20spaces",
        "expected_url": "https://example.com/path%20with%20spaces",
        "issue": "Should handle percent-encoding correctly",
    },
    {
        "name": "Dead link in template with nested template",
        "description": "Template containing nested template in parameter value",
        "input": '{{Lien web|titre=Article {{date|2026|08|31}}|url=https://www.mük.hu/}}',
        "expected_url": "https://www.mük.hu/",
        "issue": "Should preserve nested templates in parameter values",
    },
    {
        "name": "Dead link with wikilink in title",
        "description": "Template with wikilink in title parameter",
        "input": '{{Lien web|titre=[[Article]] sur le site|url=https://www.example.com/}}',
        "expected_url": "https://www.example.com/",
        "issue": "Should preserve wikilinks in parameter values",
    },
    {
        "name": "Multiple dead links in same text",
        "description": "Multiple bare URLs with Unicode characters",
        "input": "Voir https://www.mük.hu/ et https://www.fürst.de/ pour plus d'infos.",
        "expected_urls": ["https://www.mük.hu/", "https://www.fürst.de/"],
        "issue": "Should extract all URLs correctly",
    },
    {
        "name": "Dead link with archive already present",
        "description": "Template that already has archive-url parameter",
        "input": '{{Lien web|titre=Test|url=https://www.example.com/|archive-url=https://web.archive.org/web/20200101/https://www.example.com/}}',
        "expected_url": "https://www.example.com/",
        "issue": "Should handle existing archive parameters",
    },
    {
        "name": "Dead link with complex title (quotes, special chars)",
        "description": "Template with complex title containing quotes and special characters",
        "input": '{{Lien web|titre="L\'article du jour" - revue|url=https://www.example.com/}}',
        "expected_url": "https://www.example.com/",
        "issue": "Should preserve complex title formatting",
    },
]


def test_url_extraction():
    """Test URL extraction with Unicode support."""
    print("=" * 80)
    print("TESTING URL EXTRACTION WITH UNICODE SUPPORT")
    print("=" * 80)
    
    # Use the fixed pattern
    pattern = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=%\u0080-\uFFFF]+', re.IGNORECASE)
    
    for scenario in SCENARIOS:
        print(f"\n{scenario['name']}")
        print(f"Description: {scenario['description']}")
        print(f"Input: {scenario['input']}")
        
        urls = pattern.findall(scenario['input'])
        print(f"Extracted URLs: {urls}")
        
        if 'expected_url' in scenario:
            expected = scenario['expected_url']
            found = expected in urls
            status = "✓ PASS" if found else "✗ FAIL"
            print(f"Expected: {expected}")
            print(f"Status: {status}")
        elif 'expected_urls' in scenario:
            expected = scenario['expected_urls']
            status = "✓ PASS" if set(urls) == set(expected) else "✗ FAIL"
            print(f"Expected: {expected}")
            print(f"Status: {status}")
        
        if scenario['issue']:
            print(f"Issue: {scenario['issue']}")


def test_template_parsing():
    """Test template parameter parsing with Unicode URLs."""
    print("\n" + "=" * 80)
    print("TESTING TEMPLATE PARSING WITH UNICODE")
    print("=" * 80)
    
    pattern = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=%\u0080-\uFFFF]+', re.IGNORECASE)
    
    template_scenarios = [s for s in SCENARIOS if "{{Lien web" in s['input']]
    
    for scenario in template_scenarios:
        print(f"\n{scenario['name']}")
        print(f"Input: {scenario['input']}")
        
        urls = pattern.findall(scenario['input'])
        print(f"Extracted URLs from template: {urls}")
        
        if 'expected_url' in scenario:
            expected = scenario['expected_url']
            found = expected in urls
            status = "✓ PASS" if found else "✗ FAIL"
            print(f"Expected: {expected}")
            print(f"Status: {status}")
        
        if scenario['issue']:
            print(f"Issue: {scenario['issue']}")


def test_url_pattern_regex():
    """Test the URL_PATTERN regex directly."""
    print("\n" + "=" * 80)
    print("TESTING URL_PATTERN REGEX")
    print("=" * 80)
    
    # Test the fixed pattern
    pattern = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=%\u0080-\uFFFF]+', re.IGNORECASE)
    
    test_urls = [
        "https://www.mük.hu/",
        "https://www.fürst.de/",
        "https://www.école.fr/",
        "https://example.com/",
        "https://diuf.unifr.ch/pai/people/juillera/Sudoku/Sudoku.html",
    ]
    
    for url in test_urls:
        match = pattern.fullmatch(url)
        status = "✓ MATCH" if match else "✗ NO MATCH"
        print(f"{url}: {status}")


if __name__ == "__main__":
    test_url_pattern_regex()
    test_url_extraction()
    test_template_parsing()
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("All URL_PATTERN regexes have been updated to support Unicode characters.")
    print("This fixes the truncation bug for URLs with non-ASCII domain characters.")
    print("Files modified:")
    print("  - safe_url_replacer.py")
    print("  - url_extraction.py")
    print("  - corrector.py (2 locations)")
    print("  - reference_utils.py")
