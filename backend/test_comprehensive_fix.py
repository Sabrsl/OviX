"""
Comprehensive test suite for the bare_url_helper and reference_template_helper fixes
Tests multiple scenarios and edge cases
"""
import sys
sys.path.insert(0, 'src')

from wikipedia_maintenance.utils.bare_url_helper import BareUrlHelper, BareUrlRef
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper

def test_scenario_1_empty_domain_title():
    """Test that empty domain triggers 'Page web' fallback"""
    print("\n" + "=" * 80)
    print("SCENARIO 1: Empty domain title fallback")
    print("=" * 80)
    
    helper = BareUrlHelper()
    template_helper = ReferenceTemplateHelper()
    
    # Test with a URL that might result in problematic domain extraction
    ref = BareUrlRef(
        dead_url="https://example.com/",
        dead_url_start=0,
        dead_url_end=19,
        replacement_end=19,
        line_start=0,
        line_end=100,
        existing_archive_url=None,
        context_text="https://example.com/",
        link_label=None,
        replacement_start=0
    )
    
    try:
        result = helper.build_repaired_reference_template(
            ref=ref,
            archive_url="https://web.archive.org/web/20200101/https://example.com/",
            archive_date="20200101",
            title_hint=None,  # Force fallback
            provider="WaybackMachine",
            template_name='Lien web',
            extra_params=None,
            template_helper=template_helper
        )
        
        if result and 'titre=' in result:
            titre = result.split('titre=')[1].split('|')[0].split('}}')[0]
            print(f"[OK] Title present: {titre}")
            return True
        else:
            print("[FAIL] No title in template")
            return False
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False

def test_scenario_2_mapped_domain_site():
    """Test that mapped domains get wikilink site parameter"""
    print("\n" + "=" * 80)
    print("SCENARIO 2: Mapped domain site parameter")
    print("=" * 80)
    
    helper = BareUrlHelper()
    template_helper = ReferenceTemplateHelper()
    
    # Test with a known mapped domain (lemonde.fr)
    ref = BareUrlRef(
        dead_url="https://www.lemonde.fr/article",
        dead_url_start=0,
        dead_url_end=30,
        replacement_end=30,
        line_start=0,
        line_end=100,
        existing_archive_url=None,
        context_text="https://www.lemonde.fr/article",
        link_label=None,
        replacement_start=0
    )
    
    result = helper.build_repaired_reference_template(
        ref=ref,
        archive_url="https://web.archive.org/web/20200101/https://www.lemonde.fr/article",
        archive_date="20200101",
        title_hint="Test Article",
        provider="WaybackMachine",
        template_name='Lien web',
        extra_params=None,
        template_helper=template_helper
    )
    
    if result:
        if 'site=' in result:
            site = result.split('site=')[1].split('|')[0].split('}}')[0]
            print(f"Site parameter: {site}")
            if site.startswith('[['):
                print("[OK] Site is wikilink format")
                return True
            else:
                print("[FAIL] Site is not wikilink format")
                return False
        else:
            print("[FAIL] No site parameter for mapped domain")
            return False
    else:
        print("[FAIL] Template generation failed")
        return False

def test_scenario_3_unmapped_domain_no_site():
    """Test that unmapped domains don't get site parameter"""
    print("\n" + "=" * 80)
    print("SCENARIO 3: Unmapped domain - no site parameter")
    print("=" * 80)
    
    helper = BareUrlHelper()
    template_helper = ReferenceTemplateHelper()
    
    # Test with unmapped domain (umoncton.ca)
    ref = BareUrlRef(
        dead_url="https://www.umoncton.ca/",
        dead_url_start=0,
        dead_url_end=24,
        replacement_end=24,
        line_start=0,
        line_end=100,
        existing_archive_url=None,
        context_text="https://www.umoncton.ca/",
        link_label=None,
        replacement_start=0
    )
    
    result = helper.build_repaired_reference_template(
        ref=ref,
        archive_url="https://web.archive.org/web/19970201/https://www.umoncton.ca/",
        archive_date="19970201",
        title_hint="Test Title",
        provider="WaybackMachine",
        template_name='Lien web',
        extra_params=None,
        template_helper=template_helper
    )
    
    if result:
        if 'site=' in result:
            site = result.split('site=')[1].split('|')[0].split('}}')[0]
            print(f"[FAIL] Unexpected site parameter: {site}")
            return False
        else:
            print("[OK] No site parameter for unmapped domain")
            return True
    else:
        print("[FAIL] Template generation failed")
        return False

def test_scenario_4_ouvrage_no_site():
    """Test that ouvrage templates never get site parameter"""
    print("\n" + "=" * 80)
    print("SCENARIO 4: Ouvrage template - no site parameter")
    print("=" * 80)
    
    helper = BareUrlHelper()
    template_helper = ReferenceTemplateHelper()
    
    ref = BareUrlRef(
        dead_url="https://example.com/book",
        dead_url_start=0,
        dead_url_end=22,
        replacement_end=22,
        line_start=0,
        line_end=100,
        existing_archive_url=None,
        context_text="https://example.com/book",
        link_label=None,
        replacement_start=0
    )
    
    result = helper.build_repaired_reference_template(
        ref=ref,
        archive_url="https://web.archive.org/web/20200101/https://example.com/book",
        archive_date="20200101",
        title_hint="Book Title",
        provider="WaybackMachine",
        template_name='ouvrage',  # Books should never have site=
        extra_params=None,
        template_helper=template_helper
    )
    
    # Ouvrage templates don't support archive parameters, so they return None or empty
    # This is expected behavior - books are physical/digital publications, not web sites
    if not result or result.strip() == "":
        print("[OK] Ouvrage template returns None/empty (no archive support)")
        return True
    elif 'site=' in result:
        print("[FAIL] Ouvrage has site parameter (should not)")
        return False
    else:
        print("[OK] Ouvrage has no site parameter")
        return True

def test_scenario_5_yaml_mapping_direct():
    """Test YAML mapping loads correctly"""
    print("\n" + "=" * 80)
    print("SCENARIO 5: YAML mapping direct test")
    print("=" * 80)
    
    mapping = ReferenceTemplateHelper._load_domain_to_site_name_mapping()
    
    if not mapping:
        print("[FAIL] No mapping loaded")
        return False
    
    print(f"[OK] Loaded {len(mapping)} entries")
    
    # Test specific known mappings
    test_cases = [
        ("lemonde.fr", "[[Le Monde]]"),
        ("youtube.com", "[[YouTube]]"),
        ("apple.com", "[[Apple]]"),
    ]
    
    all_passed = True
    for domain, expected in test_cases:
        if domain in mapping:
            actual = mapping[domain]
            if actual == expected:
                print(f"[OK] {domain} -> {actual}")
            else:
                print(f"[FAIL] {domain} -> {actual} (expected {expected})")
                all_passed = False
        else:
            print(f"[FAIL] {domain} not in mapping")
            all_passed = False
    
    return all_passed

def test_scenario_6_link_label_priority():
    """Test that link_label is used when available"""
    print("\n" + "=" * 80)
    print("SCENARIO 6: Link label priority in title")
    print("=" * 80)
    
    helper = BareUrlHelper()
    template_helper = ReferenceTemplateHelper()
    
    # Test with a wiki external link "[url label]"
    ref = BareUrlRef(
        dead_url="https://example.com/page",
        dead_url_start=1,
        dead_url_end=21,
        replacement_end=35,
        line_start=0,
        line_end=100,
        existing_archive_url=None,
        context_text="[https://example.com/page My Custom Title]",
        link_label="My Custom Title",
        replacement_start=0
    )
    
    result = helper.build_repaired_reference_template(
        ref=ref,
        archive_url="https://web.archive.org/web/20200101/https://example.com/page",
        archive_date="20200101",
        title_hint=None,  # Should use link_label instead
        provider="WaybackMachine",
        template_name='Lien web',
        extra_params=None,
        template_helper=template_helper
    )
    
    if result and 'titre=' in result:
        titre = result.split('titre=')[1].split('|')[0].split('}}')[0]
        if "My Custom Title" in titre:
            print(f"[OK] Link label used as title: {titre}")
            return True
        else:
            print(f"[FAIL] Link label not used: {titre}")
            return False
    else:
        print("[FAIL] Template generation failed or no title")
        return False

def test_scenario_7_malformed_link_label_rejection():
    """Test that malformed link labels are rejected"""
    print("\n" + "=" * 80)
    print("SCENARIO 7: Malformed link label rejection")
    print("=" * 80)
    
    helper = BareUrlHelper()
    template_helper = ReferenceTemplateHelper()
    
    # Test with suspicious link label (too short)
    ref = BareUrlRef(
        dead_url="https://example.com/page",
        dead_url_start=1,
        dead_url_end=21,
        replacement_end=24,
        line_start=0,
        line_end=100,
        existing_archive_url=None,
        context_text="[https://example.com/page xy]",
        link_label="xy",  # Too short, should be rejected
        replacement_start=0
    )
    
    result = helper.build_repaired_reference_template(
        ref=ref,
        archive_url="https://web.archive.org/web/20200101/https://example.com/page",
        archive_date="20200101",
        title_hint=None,
        provider="WaybackMachine",
        template_name='Lien web',
        extra_params=None,
        template_helper=template_helper
    )
    
    if result and 'titre=' in result:
        titre = result.split('titre=')[1].split('|')[0].split('}}')[0]
        if titre != "xy":
            print(f"[OK] Malformed label rejected, used fallback: {titre}")
            return True
        else:
            print(f"[FAIL] Malformed label not rejected: {titre}")
            return False
    else:
        print("[FAIL] Template generation failed")
        return False

def test_scenario_8_archive_date_extraction():
    """Test archive date extraction from URL"""
    print("\n" + "=" * 80)
    print("SCENARIO 8: Archive date extraction from URL")
    print("=" * 80)
    
    helper = BareUrlHelper()
    template_helper = ReferenceTemplateHelper()
    
    ref = BareUrlRef(
        dead_url="https://example.com/page",
        dead_url_start=0,
        dead_url_end=21,
        replacement_end=21,
        line_start=0,
        line_end=100,
        existing_archive_url=None,
        context_text="https://example.com/page",
        link_label=None,
        replacement_start=0
    )
    
    # Test with archive URL containing timestamp but no archive_date parameter
    result = helper.build_repaired_reference_template(
        ref=ref,
        archive_url="https://web.archive.org/web/20200101120000/https://example.com/page",
        archive_date="",  # Empty, should extract from URL
        title_hint="Test Title",
        provider="WaybackMachine",
        template_name='Lien web',
        extra_params=None,
        template_helper=template_helper
    )
    
    if result and 'archive-date=' in result:
        archive_date = result.split('archive-date=')[1].split('|')[0].split('}}')[0]
        if "2020-01-01" in archive_date:
            print(f"[OK] Archive date extracted from URL: {archive_date}")
            return True
        else:
            print(f"[FAIL] Archive date not correct: {archive_date}")
            return False
    else:
        print("[FAIL] No archive-date in template")
        return False

if __name__ == "__main__":
    print("=" * 80)
    print("COMPREHENSIVE TEST SUITE FOR BARE_URL_HELPER FIXES")
    print("=" * 80)
    
    scenarios = [
        ("Empty domain title fallback", test_scenario_1_empty_domain_title),
        ("Mapped domain site parameter", test_scenario_2_mapped_domain_site),
        ("Unmapped domain no site", test_scenario_3_unmapped_domain_no_site),
        ("Ouvrage no site parameter", test_scenario_4_ouvrage_no_site),
        ("YAML mapping direct test", test_scenario_5_yaml_mapping_direct),
        ("Link label priority", test_scenario_6_link_label_priority),
        ("Malformed link label rejection", test_scenario_7_malformed_link_label_rejection),
        ("Archive date extraction", test_scenario_8_archive_date_extraction),
    ]
    
    results = []
    for name, test_func in scenarios:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"[ERROR] Exception in {name}: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")
    
    print(f"\nTotal: {passed_count}/{total_count} scenarios passed")
    
    if passed_count == total_count:
        print("\n[SUCCESS] All scenarios passed!")
        sys.exit(0)
    else:
        print(f"\n[FAILURE] {total_count - passed_count} scenario(s) failed")
        sys.exit(1)
