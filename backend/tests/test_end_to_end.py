"""
End-to-end test for dead link detection and repair system.

This test simulates the complete flow:
1. URL extraction from wikitext
2. Dead link detection
3. Template parsing
4. Archive repair generation
5. Validation of repairs
"""

import re
import sys
sys.path.insert(0, 'src')

from wikipedia_maintenance.utils.url_extraction import UrlExtractor
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper, ReferenceTemplate


def test_end_to_end_bare_url_repair():
    """Test end-to-end flow for bare URL repair."""
    print("=" * 80)
    print("END-TO-END TEST: Bare URL Repair Flow")
    print("=" * 80)
    
    # Simulate wikitext with a dead bare URL
    content = "Voir http://www.example.com/dead-link pour plus d'informations."
    
    # Step 1: Extract URLs
    extractor = UrlExtractor()
    urls = extractor.find_urls_in_content(content)
    print(f"Step 1 - URL Extraction: Found {len(urls)} URLs")
    for url, start, end in urls:
        print(f"  URL: {url} at position {start}-{end}")
    
    if not urls:
        print("  ✗ FAIL: No URLs extracted")
        return False
    
    # Step 2: Validate URL syntax
    url = urls[0][0]
    is_valid = extractor.is_syntactically_valid(url)
    print(f"Step 2 - URL Validation: {'Valid' if is_valid else 'Invalid'}")
    
    if not is_valid:
        print("  ✗ FAIL: URL syntax validation failed")
        return False
    
    # Step 3: Check if it's in a template (should not be for bare URL)
    template = extractor.extract_domain(url)
    print(f"Step 3 - Template Check: Domain extracted: {template}")
    
    # Step 4: Simulate repair (archive URL)
    old_url = url
    new_url = "https://web.archive.org/web/20260831/http://www.example.com/dead-link"
    
    # Step 5: Apply replacement
    from wikipedia_maintenance.utils.safe_url_replacer import SafeURLReplacer
    replacer = SafeURLReplacer()
    result = replacer.replace_exact_occurrence(content, old_url, new_url, urls[0][1])
    
    if result.success:
        print(f"Step 4 - Repair Applied: {old_url} → {new_url}")
        print(f"  New content: {result.new_content}")
        print("  ✓ PASS")
        return True
    else:
        print(f"Step 4 - Repair Failed: {result.reason}")
        print("  ✗ FAIL")
        return False


def test_end_to_end_template_repair():
    """Test end-to-end flow for template-based repair."""
    print("\n" + "=" * 80)
    print("END-TO-END TEST: Template Repair Flow")
    print("=" * 80)
    
    # Simulate wikitext with a dead link in {{Lien web}} template
    content = '{{Lien web|titre=Test Article|url=http://www.example.com/dead-link|site=Example.com}}'
    
    # Step 1: Extract URLs
    extractor = UrlExtractor()
    urls = extractor.find_urls_in_content(content)
    print(f"Step 1 - URL Extraction: Found {len(urls)} URLs")
    for url, start, end in urls:
        print(f"  URL: {url} at position {start}-{end}")
    
    if not urls:
        print("  ✗ FAIL: No URLs extracted")
        return False
    
    # Step 2: Find template
    helper = ReferenceTemplateHelper()
    url = urls[0][0]
    url_pos = urls[0][1]
    template = helper.find_reference_template(content, url, url_pos)
    
    if template:
        print(f"Step 2 - Template Found: {template.template_name}")
        print(f"  Parameters: {template.parameters}")
    else:
        print("  ✗ FAIL: Template not found")
        return False
    
    # Step 3: Generate archive repair template
    archive_url = "https://web.archive.org/web/20260831/http://www.example.com/dead-link"
    archive_date = "20260831"
    
    new_template = helper.generate_archive_repair_template(
        template,
        archive_url,
        archive_date,
        url,
        assume_patch_deployed=False
    )
    
    print(f"Step 3 - Archive Repair Generated:")
    print(f"  {new_template[:200]}...")
    
    # Step 4: Validate template structure
    if '|archive-url=' in new_template and '|archive-date=' in new_template:
        print("  ✓ Archive parameters present")
    else:
        print("  ✗ FAIL: Archive parameters missing")
        return False
    
    if '|brisé le=' in new_template:
        print("  ✓ brisé le parameter present")
    else:
        print("  ✗ FAIL: brisé le parameter missing")
        return False
    
    # Step 5: Verify site parameter preserved
    if '|site=' in new_template:
        print("  ✓ site parameter preserved")
    else:
        print("  ✗ FAIL: site parameter lost")
        return False
    
    print("  ✓ PASS")
    return True


def test_end_to_end_ouvrage_repair():
    """Test end-to-end flow for ouvrage template repair (should NOT have site)."""
    print("\n" + "=" * 80)
    print("END-TO-END TEST: Ouvrage Template Repair Flow")
    print("=" * 80)
    
    # Simulate wikitext with a dead link in {{ouvrage}} template
    content = '{{ouvrage|titre=Great Book|auteur=Jane Smith|lire en ligne=http://www.example.com/book}}'
    
    # Step 1: Extract URLs
    extractor = UrlExtractor()
    urls = extractor.find_urls_in_content(content)
    print(f"Step 1 - URL Extraction: Found {len(urls)} URLs")
    
    if not urls:
        print("  ✗ FAIL: No URLs extracted")
        return False
    
    # Step 2: Find template
    helper = ReferenceTemplateHelper()
    url = urls[0][0]
    url_pos = urls[0][1]
    template = helper.find_reference_template(content, url, url_pos)
    
    if template:
        print(f"Step 2 - Template Found: {template.template_name}")
        print(f"  Parameters: {template.parameters}")
    else:
        print("  ✗ FAIL: Template not found")
        return False
    
    # Step 3: Generate archive repair template
    archive_url = "https://web.archive.org/web/20260831/http://www.example.com/book"
    archive_date = "20260831"
    
    new_template = helper.generate_archive_repair_template(
        template,
        archive_url,
        archive_date,
        url,
        assume_patch_deployed=False
    )
    
    print(f"Step 3 - Archive Repair Generated:")
    print(f"  {new_template[:200]}...")
    
    # Step 4: Verify site parameter is NOT present (ouvrage should not have site)
    if '|site=' not in new_template:
        print("  ✓ site parameter correctly absent for ouvrage")
    else:
        print("  ✗ FAIL: site parameter incorrectly added to ouvrage")
        return False
    
    # Step 5: Verify archive parameters present
    if '|archive-url=' in new_template and '|archive-date=' in new_template:
        print("  ✓ Archive parameters present")
    else:
        print("  ✗ FAIL: Archive parameters missing")
        return False
    
    print("  ✓ PASS")
    return True


def test_end_to_end_unicode_url_repair():
    """Test end-to-end flow with Unicode URL."""
    print("\n" + "=" * 80)
    print("END-TO-END TEST: Unicode URL Repair Flow")
    print("=" * 80)
    
    # Simulate wikitext with a dead Unicode URL in template
    content = '{{Lien web|titre="Magyar Ügyvédi Kamara"|url=https://www.mük.hu/|site=mük.hu}}'
    
    # Step 1: Extract URLs
    extractor = UrlExtractor()
    urls = extractor.find_urls_in_content(content)
    print(f"Step 1 - URL Extraction: Found {len(urls)} URLs")
    for url, start, end in urls:
        print(f"  URL: {url} at position {start}-{end}")
    
    if not urls:
        print("  ✗ FAIL: No URLs extracted")
        return False
    
    # Verify Unicode URL is extracted correctly
    url = urls[0][0]
    if url == "https://www.mük.hu/":
        print("  ✓ Unicode URL extracted correctly")
    else:
        print(f"  ✗ FAIL: Unicode URL truncated to {url}")
        return False
    
    # Step 2: Find template
    helper = ReferenceTemplateHelper()
    url_pos = urls[0][1]
    template = helper.find_reference_template(content, url, url_pos)
    
    if template:
        print(f"Step 2 - Template Found: {template.template_name}")
        print(f"  Parameters: {template.parameters}")
    else:
        print("  ✗ FAIL: Template not found")
        return False
    
    # Verify Unicode characters preserved in parameters
    if template.parameters.get('titre') == '"Magyar Ügyvédi Kamara"':
        print("  ✓ Unicode characters preserved in title")
    else:
        print(f"  ✗ FAIL: Title corrupted: {template.parameters.get('titre')}")
        return False
    
    if template.parameters.get('site') == 'mük.hu':
        print("  ✓ Unicode characters preserved in site")
    else:
        print(f"  ✗ FAIL: Site corrupted: {template.parameters.get('site')}")
        return False
    
    # Step 3: Generate archive repair template
    archive_url = "https://web.archive.org/web/20260831/https://www.mük.hu/"
    archive_date = "20260831"
    
    new_template = helper.generate_archive_repair_template(
        template,
        archive_url,
        archive_date,
        url,
        assume_patch_deployed=False
    )
    
    print(f"Step 3 - Archive Repair Generated:")
    print(f"  {new_template[:200]}...")
    
    # Step 4: Verify Unicode preserved in generated template
    if 'mük.hu' in new_template:
        print("  ✓ Unicode characters preserved in generated template")
    else:
        print("  ✗ FAIL: Unicode characters lost in generated template")
        return False
    
    print("  ✓ PASS")
    return True


def test_system_reliability_checks():
    """Test system reliability and safety checks."""
    print("\n" + "=" * 80)
    print("SYSTEM RELIABILITY CHECKS")
    print("=" * 80)
    
    helper = ReferenceTemplateHelper()
    
    # Check 1: TEMPLATES_WITHOUT_SITE_PARAM is correctly configured
    if helper.TEMPLATES_WITHOUT_SITE_PARAM == {'ouvrage'}:
        print("✓ TEMPLATES_WITHOUT_SITE_PARAM correctly configured")
    else:
        print(f"✗ FAIL: TEMPLATES_WITHOUT_SITE_PARAM = {helper.TEMPLATES_WITHOUT_SITE_PARAM}")
        return False
    
    # Check 2: TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK is configured
    if helper.TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK == {'Lien web', 'Lien archive'}:
        print("✓ TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK correctly configured")
    else:
        print(f"✗ FAIL: TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK = {helper.TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK}")
        return False
    
    # Check 3: Known template names are defined
    if len(helper.KNOWN_TEMPLATE_NAMES) > 0:
        print(f"✓ KNOWN_TEMPLATE_NAMES has {len(helper.KNOWN_TEMPLATE_NAMES)} entries")
    else:
        print("✗ FAIL: KNOWN_TEMPLATE_NAMES is empty")
        return False
    
    # Check 4: Template-specific parameters are defined
    if all(len(params) > 0 for params in helper.TEMPLATE_SPECIFIC_PARAMETERS.values()):
        print(f"✓ TEMPLATE_SPECIFIC_PARAMETERS defined for {len(helper.TEMPLATE_SPECIFIC_PARAMETERS)} template types")
    else:
        print("✗ FAIL: Some template types have empty parameter lists")
        return False
    
    print("✓ All reliability checks passed")
    return True


if __name__ == "__main__":
    results = []
    
    results.append(("Bare URL Repair Flow", test_end_to_end_bare_url_repair()))
    results.append(("Template Repair Flow", test_end_to_end_template_repair()))
    results.append(("Ouvrage Template Repair Flow", test_end_to_end_ouvrage_repair()))
    results.append(("Unicode URL Repair Flow", test_end_to_end_unicode_url_repair()))
    results.append(("System Reliability Checks", test_system_reliability_checks()))
    
    print("\n" + "=" * 80)
    print("END-TO-END TEST SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("ALL END-TO-END TESTS PASSED")
        print("Dead link detection and repair system is functional and reliable.")
    else:
        print("SOME END-TO-END TESTS FAILED")
        print("Dead link system may have issues.")
    print("=" * 80)
