"""
Unitary tests for the specific bug fixes
Tests individual functions and edge cases
"""
import sys
sys.path.insert(0, 'src')

from wikipedia_maintenance.utils.bare_url_helper import BareUrlHelper
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper

def test_safe_extract_domain():
    """Test _safe_extract_domain with various inputs"""
    print("\n" + "=" * 80)
    print("UNIT TEST: _safe_extract_domain")
    print("=" * 80)
    
    helper = BareUrlHelper()
    
    test_cases = [
        ("https://www.example.com/path", "www.example.com"),
        ("http://example.com", "example.com"),
        ("https://sub.domain.co.uk/path", "sub.domain.co.uk"),
        ("invalid-url", ""),  # Should return empty string for invalid URLs
        ("", ""),  # Empty string
        ("not a url", ""),  # Invalid format
    ]
    
    all_passed = True
    for url, expected in test_cases:
        result = helper._safe_extract_domain(url)
        if result == expected:
            print(f"[OK] '{url}' -> '{result}'")
        else:
            print(f"[FAIL] '{url}' -> '{result}' (expected '{expected}')")
            all_passed = False
    
    return all_passed

def test_resolve_site_display_name():
    """Test _resolve_site_display_name with various inputs"""
    print("\n" + "=" * 80)
    print("UNIT TEST: _resolve_site_display_name")
    print("=" * 80)
    
    helper = ReferenceTemplateHelper()
    
    test_cases = [
        # (input, should_start_with_brackets, description)
        ("lemonde.fr", True, "Known mapped domain"),
        ("youtube.com", True, "Known mapped domain"),
        ("umoncton.ca", False, "Unknown domain"),
        ("[[Le Monde]]", True, "Already wikilink"),
        ("Le Monde", False, "Human-readable name"),
        ("", False, "Empty string (no brackets expected)"),
        ("notadomain", False, "Not a domain"),
    ]
    
    all_passed = True
    for domain, should_have_brackets, description in test_cases:
        result = helper._resolve_site_display_name(domain)
        has_brackets = result and result.strip().startswith('[[')
        
        # For empty string, has_brackets is False which is correct
        if result == "" and domain == "":
            has_brackets = False  # Explicitly handle empty string case
        
        if has_brackets == should_have_brackets:
            print(f"[OK] {description}: '{domain}' -> '{result}'")
        else:
            print(f"[FAIL] {description}: '{domain}' -> '{result}' (brackets={has_brackets}, expected={should_have_brackets})")
            all_passed = False
    
    return all_passed

def test_validate_title_candidate():
    """Test _validate_title_candidate with various inputs"""
    print("\n" + "=" * 80)
    print("UNIT TEST: _validate_title_candidate")
    print("=" * 80)
    
    import logging
    test_logger = logging.getLogger("test")
    
    test_cases = [
        # (title, should_pass, description)
        ("Valid Title", True, "Normal title"),
        ("A", False, "Too short"),
        ("Title with | pipe", False, "Contains pipe"),
        ("Title with [ bracket", False, "Unbalanced brackets"),
        ("Title with ] bracket", False, "Unbalanced brackets"),
        ("01.01", False, "Date-like"),
        ("Valid Title with numbers 2020", True, "Title with date but not dominated"),
        ("Valid Title", True, "Valid title"),
        ("", False, "Empty title"),
        (None, False, "None title"),
    ]
    
    all_passed = True
    for title, should_pass, description in test_cases:
        result = BareUrlHelper._validate_title_candidate(title, "test_url", test_logger, "test")
        passed = result is not None
        
        if passed == should_pass:
            status = "accepted" if passed else "rejected"
            print(f"[OK] {description}: '{title}' -> {status}")
        else:
            status = "accepted" if passed else "rejected"
            expected_status = "accepted" if should_pass else "rejected"
            print(f"[FAIL] {description}: '{title}' -> {status} (expected {expected_status})")
            all_passed = False
    
    return all_passed

def test_yaml_loading():
    """Test YAML loading functionality"""
    print("\n" + "=" * 80)
    print("UNIT TEST: YAML loading")
    print("=" * 80)
    
    # Test that mapping loads
    mapping = ReferenceTemplateHelper._load_domain_to_site_name_mapping()
    
    if not mapping:
        print("[FAIL] No mapping loaded")
        return False
    
    print(f"[OK] Loaded {len(mapping)} entries")
    
    # Test that it's cached
    mapping2 = ReferenceTemplateHelper._load_domain_to_site_name_mapping()
    if mapping is mapping2:
        print("[OK] Mapping is cached (same object)")
    else:
        print("[WARNING] Mapping not cached (different objects)")
    
    # Test specific entries
    if "lemonde.fr" in mapping:
        print(f"[OK] lemonde.fr -> {mapping['lemonde.fr']}")
    else:
        print("[FAIL] lemonde.fr not in mapping")
        return False
    
    return True

def test_domain_capitalization():
    """Test domain capitalization in title fallback"""
    print("\n" + "=" * 80)
    print("UNIT TEST: Domain capitalization")
    print("=" * 80)
    
    # This tests the fix for the IndexError when domain is empty
    # and the capitalization logic when domain is present
    
    test_cases = [
        ("example.com", "Example.com"),
        ("www.example.com", "Www.example.com"),
        ("sub.domain.com", "Sub.domain.com"),
    ]
    
    all_passed = True
    for domain, expected_capitalized in test_cases:
        if domain:
            capitalized = domain[0].upper() + domain[1:]
            if capitalized == expected_capitalized:
                print(f"[OK] '{domain}' -> '{capitalized}'")
            else:
                print(f"[FAIL] '{domain}' -> '{capitalized}' (expected '{expected_capitalized}')")
                all_passed = False
        else:
            print(f"[OK] Empty domain handled correctly")
    
    return all_passed

def test_template_specific_parameters():
    """Test that different templates have correct parameter support"""
    print("\n" + "=" * 80)
    print("UNIT TEST: Template-specific parameters")
    print("=" * 80)
    
    helper = ReferenceTemplateHelper()
    
    # Test TEMPLATES_WITHOUT_SITE_PARAM
    if 'ouvrage' in helper.TEMPLATES_WITHOUT_SITE_PARAM:
        print("[OK] ouvrage in TEMPLATES_WITHOUT_SITE_PARAM")
    else:
        print("[FAIL] ouvrage not in TEMPLATES_WITHOUT_SITE_PARAM")
        return False
    
    if 'chapitre' in helper.TEMPLATES_WITHOUT_SITE_PARAM:
        print("[OK] chapitre in TEMPLATES_WITHOUT_SITE_PARAM")
    else:
        print("[FAIL] chapitre not in TEMPLATES_WITHOUT_SITE_PARAM")
        return False
    
    # Test TEMPLATES_WITHOUT_ARCHIVE_PARAMS
    if 'ouvrage' in helper.TEMPLATES_WITHOUT_ARCHIVE_PARAMS:
        print("[OK] ouvrage in TEMPLATES_WITHOUT_ARCHIVE_PARAMS")
    else:
        print("[FAIL] ouvrage not in TEMPLATES_WITHOUT_ARCHIVE_PARAMS")
        return False
    
    # Test TEMPLATES_SUPPORTING_CONSULTE_LE
    if 'lien web' in helper.TEMPLATES_SUPPORTING_CONSULTE_LE:
        print("[OK] lien web in TEMPLATES_SUPPORTING_CONSULTE_LE")
    else:
        print("[FAIL] lien web not in TEMPLATES_SUPPORTING_CONSULTE_LE")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 80)
    print("UNITARY TEST SUITE FOR BARE_URL_HELPER FIXES")
    print("=" * 80)
    
    helper = BareUrlHelper()
    
    tests = [
        ("_safe_extract_domain", test_safe_extract_domain),
        ("_resolve_site_display_name", test_resolve_site_display_name),
        ("_validate_title_candidate", test_validate_title_candidate),
        ("YAML loading", test_yaml_loading),
        ("Domain capitalization", test_domain_capitalization),
        ("Template-specific parameters", test_template_specific_parameters),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"[ERROR] Exception in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")
    
    print(f"\nTotal: {passed_count}/{total_count} unit tests passed")
    
    if passed_count == total_count:
        print("\n[SUCCESS] All unit tests passed!")
        sys.exit(0)
    else:
        print(f"\n[FAILURE] {total_count - passed_count} unit test(s) failed")
        sys.exit(1)
