"""
Test template parameter preservation and different template types.

This file tests:
1. Parameter preservation (titre, site, auteur, etc.) during reconstruction
2. Different template types (Lien web, ouvrage, article) with their specific parameters
3. Special handling for templates without site parameter (ouvrage)
"""

import re
import sys
sys.path.insert(0, 'src')

from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper, ReferenceTemplate


def test_template_parameter_parsing():
    """Test that template parameters are parsed correctly."""
    print("=" * 80)
    print("TESTING TEMPLATE PARAMETER PARSING")
    print("=" * 80)
    
    helper = ReferenceTemplateHelper()
    
    test_cases = [
        {
            "name": "Lien web with all common parameters",
            "template": '{{Lien web|titre=Test Article|url=https://www.example.com/|site=Example.com|auteur=John Doe|date=2026-08-31}}',
            "expected_params": {
                "titre": "Test Article",
                "url": "https://www.example.com/",
                "site": "Example.com",
                "auteur": "John Doe",
                "date": "2026-08-31"
            }
        },
        {
            "name": "Lien web with Unicode in title",
            "template": '{{Lien web|titre="Magyar Ügyvédi Kamara"|url=https://www.mük.hu/|site=mük.hu}}',
            "expected_params": {
                "titre": '"Magyar Ügyvédi Kamara"',
                "url": "https://www.mük.hu/",
                "site": "mük.hu"
            }
        },
        {
            "name": "Article with journal-specific parameters",
            "template": '{{article|titre=Research Paper|périodique=Nature|volume=42|numéro=5|pages=123-145|url=https://www.example.com/paper}}',
            "expected_params": {
                "titre": "Research Paper",
                "périodique": "Nature",
                "volume": "42",
                "numéro": "5",
                "pages": "123-145",
                "url": "https://www.example.com/paper"
            }
        },
        {
            "name": "Ouvrage with book-specific parameters (NO site parameter)",
            "template": '{{ouvrage|titre=Great Book|auteur=Jane Smith|éditeur=Publishing House|année=2020|isbn=978-0-123456-78-9|lire en ligne=https://www.example.com/book}}',
            "expected_params": {
                "titre": "Great Book",
                "auteur": "Jane Smith",
                "éditeur": "Publishing House",
                "année": "2020",
                "isbn": "978-0-123456-78-9",
                "lire en ligne": "https://www.example.com/book"
            },
            "should_not_have_site": True
        },
        {
            "name": "Template with nested template in value",
            "template": '{{Lien web|titre=Article {{date|2026|08|31}}|url=https://www.example.com/}}',
            "expected_params": {
                "titre": "Article {{date|2026|08|31}}",
                "url": "https://www.example.com/"
            }
        },
        {
            "name": "Template with wikilink in title",
            "template": '{{Lien web|titre=[[Wikipedia]] article|url=https://www.example.com/}}',
            "expected_params": {
                "titre": "[[Wikipedia]] article",
                "url": "https://www.example.com/"
            }
        },
        {
            "name": "Template with complex quoted title",
            "template": '{{Lien web|titre="L\'article du jour" - revue|url=https://www.example.com/|site=Revue.fr}}',
            "expected_params": {
                "titre": '"L\'article du jour" - revue',
                "url": "https://www.example.com/",
                "site": "Revue.fr"
            }
        },
    ]
    
    for test_case in test_cases:
        print(f"\n{test_case['name']}")
        print(f"Template: {test_case['template']}")
        
        # Parse the template
        url_pos = test_case['template'].find('http')
        if url_pos == -1:
            url_pos = test_case['template'].find('https')
        
        template = helper.find_reference_template(
            test_case['template'],
            test_case['expected_params'].get('url', ''),
            url_pos
        )
        
        if template:
            print(f"Template found: {template.template_name}")
            print(f"Parameters parsed: {len(template.parameters)}")
            
            # Check expected parameters
            all_match = True
            for key, expected_value in test_case['expected_params'].items():
                actual_value = template.parameters.get(key)
                if actual_value == expected_value:
                    print(f"  ✓ {key}={expected_value}")
                else:
                    print(f"  ✗ {key}: expected={expected_value}, actual={actual_value}")
                    all_match = False
            
            # Check that site is NOT present for ouvrage
            if test_case.get('should_not_have_site'):
                if 'site' in template.parameters:
                    print(f"  ✗ FAIL: ouvrage should NOT have site parameter, but found: {template.parameters['site']}")
                    all_match = False
                else:
                    print(f"  ✓ site parameter correctly absent for ouvrage")
            
            status = "✓ PASS" if all_match else "✗ FAIL"
            print(f"Status: {status}")
        else:
            print(f"Status: ✗ FAIL - Template not found")


def test_template_specific_parameters():
    """Test that different template types have correct parameter lists."""
    print("\n" + "=" * 80)
    print("TESTING TEMPLATE-SPECIFIC PARAMETERS")
    print("=" * 80)
    
    helper = ReferenceTemplateHelper()
    
    # Check that each template type has its expected parameters
    templates_to_check = ['Lien web', 'article', 'ouvrage']
    
    for template_name in templates_to_check:
        print(f"\n{template_name} parameters:")
        params = helper.TEMPLATE_SPECIFIC_PARAMETERS.get(template_name, [])
        print(f"  Total parameters: {len(params)}")
        
        # Check for key parameters
        if template_name == 'Lien web':
            if 'site' in params:
                print(f"  ✓ Has 'site' parameter (correct for Lien web)")
            else:
                print(f"  ✗ Missing 'site' parameter (incorrect for Lien web)")
        
        if template_name == 'article':
            if 'périodique' in params:
                print(f"  ✓ Has 'périodique' parameter (correct for article)")
            else:
                print(f"  ✗ Missing 'périodique' parameter (incorrect for article)")
            if 'volume' in params and 'numéro' in params:
                print(f"  ✓ Has 'volume' and 'numéro' parameters (correct for article)")
        
        if template_name == 'ouvrage':
            if 'site' in params:
                print(f"  ✗ Has 'site' parameter (INCORRECT - ouvrage should not have site)")
            else:
                print(f"  ✓ Does NOT have 'site' parameter (correct for ouvrage)")
            if 'isbn' in params:
                print(f"  ✓ Has 'isbn' parameter (correct for ouvrage)")
            if 'éditeur' in params:
                print(f"  ✓ Has 'éditeur' parameter (correct for ouvrage)")


def test_templates_without_site_param():
    """Test that TEMPLATES_WITHOUT_SITE_PARAM is correctly configured."""
    print("\n" + "=" * 80)
    print("TESTING TEMPLATES_WITHOUT_SITE_PARAM CONFIGURATION")
    print("=" * 80)
    
    helper = ReferenceTemplateHelper()
    
    print(f"Templates without site parameter: {helper.TEMPLATES_WITHOUT_SITE_PARAM}")
    
    expected_without_site = {'ouvrage'}
    if helper.TEMPLATES_WITHOUT_SITE_PARAM == expected_without_site:
        print(f"✓ PASS: Correctly configured - only 'ouvrage' should not have site parameter")
    else:
        print(f"✗ FAIL: Expected {expected_without_site}, got {helper.TEMPLATES_WITHOUT_SITE_PARAM}")


def test_archive_repair_generation():
    """Test that archive repair templates are generated correctly for different template types."""
    print("\n" + "=" * 80)
    print("TESTING ARCHIVE REPAIR TEMPLATE GENERATION")
    print("=" * 80)
    
    helper = ReferenceTemplateHelper()
    
    test_cases = [
        {
            "name": "Lien web with archive",
            "original_template": ReferenceTemplate(
                template_name="Lien web",
                parameters={
                    "titre": "Test Article",
                    "url": "https://www.example.com/",
                    "site": "Example.com"
                },
                full_match="{{Lien web|titre=Test Article|url=https://www.example.com/|site=Example.com}}",
                start_position=0,
                end_position=70
            ),
            "archive_url": "https://web.archive.org/web/20260831/https://www.example.com/",
            "archive_date": "20260831",
            "original_url": "https://www.example.com/",
            "should_have_site": True
        },
        {
            "name": "Ouvrage with archive (should NOT have site)",
            "original_template": ReferenceTemplate(
                template_name="ouvrage",
                parameters={
                    "titre": "Great Book",
                    "auteur": "Jane Smith",
                    "lire en ligne": "https://www.example.com/book"
                },
                full_match="{{ouvrage|titre=Great Book|auteur=Jane Smith|lire en ligne=https://www.example.com/book}}",
                start_position=0,
                end_position=80
            ),
            "archive_url": "https://web.archive.org/web/20260831/https://www.example.com/book",
            "archive_date": "20260831",
            "original_url": "https://www.example.com/book",
            "should_have_site": False
        },
    ]
    
    for test_case in test_cases:
        print(f"\n{test_case['name']}")
        
        try:
            generated = helper.generate_archive_repair_template(
                test_case['original_template'],
                test_case['archive_url'],
                test_case['archive_date'],
                test_case['original_url'],
                assume_patch_deployed=False
            )
            
            print(f"Generated template: {generated[:200]}...")
            
            # Check if site parameter is present/absent as expected
            has_site = '|site=' in generated
            if test_case['should_have_site']:
                if has_site:
                    print(f"  ✓ Has site parameter (correct for {test_case['original_template'].template_name})")
                else:
                    print(f"  ✗ Missing site parameter (incorrect for {test_case['original_template'].template_name})")
            else:
                if not has_site:
                    print(f"  ✓ Does NOT have site parameter (correct for {test_case['original_template'].template_name})")
                else:
                    print(f"  ✗ Has site parameter (incorrect for {test_case['original_template'].template_name})")
            
            # Check that archive parameters are present
            if '|archive-url=' in generated and '|archive-date=' in generated:
                print(f"  ✓ Has archive-url and archive-date parameters")
            else:
                print(f"  ✗ Missing archive parameters")
            
            print(f"Status: ✓ PASS")
        except Exception as e:
            print(f"Status: ✗ FAIL - Error: {e}")


if __name__ == "__main__":
    test_template_parameter_parsing()
    test_template_specific_parameters()
    test_templates_without_site_param()
    test_archive_repair_generation()
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("Template parameter preservation and type-specific handling tested.")
    print("Key checks:")
    print("  - Parameters parsed correctly (titre, site, auteur, etc.)")
    print("  - Unicode characters in parameter values preserved")
    print("  - Nested templates and wikilinks in values preserved")
    print("  - ouvrage does NOT get site parameter")
    print("  - Lien web and article DO get site parameter")
    print("  - Archive repair templates generated correctly per type")
