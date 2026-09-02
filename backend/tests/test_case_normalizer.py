"""
Test script for Case Normalizer module.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from wikipedia_maintenance.utils.case_normalizer import CaseNormalizer

def test_case_normalizer():
    """Test the case normalizer with various reference templates."""
    
    # Test cases with different scenarios
    test_cases = [
        # Test 1: Simple title normalization
        {
            "name": "Simple title normalization",
            "input": "{{Lien web|titre=TEST ARTICLE COMPLETE|url=https://example.com|site=EXAMPLE SITE}}",
            "expected_changes": 1,  # Only titre should be normalized (site is not in official names)
        },
        # Test 2: Title with acronym (should be preserved)
        {
            "name": "Title with acronym",
            "input": "{{Lien web|titre=REPORT ON ONU ACTIVITIES|url=https://example.com}}",
            "expected_changes": 0,  # ONU should be preserved
        },
        # Test 3: Author name normalization
        {
            "name": "Author name normalization",
            "input": "{{Article|auteur=JEAN DUPONT|titre=Test Article}}",
            "expected_changes": 1,  # Only auteur should be normalized (titre is already proper)
        },
        # Test 4: Non-official site name normalization
        {
            "name": "Non-official site name normalization",
            "input": "{{Lien web|site=NEWS SITE|url=https://example.com}}",
            "expected_changes": 1,  # site should be normalized
        },
        # Test 5: Official site name preservation
        {
            "name": "Official site name preservation",
            "input": "{{Lien web|site=Le Monde|url=https://lemonde.fr}}",
            "expected_changes": 0,  # Le Monde is an official name, should be preserved
        },
        # Test 6: URL should never be modified
        {
            "name": "URL preservation",
            "input": "{{Lien web|url=https://EXAMPLE.COM/PATH|titre=Test}}",
            "expected_changes": 0,  # URL should never be modified
        },
        # Test 7: Disabled normalizer
        {
            "name": "Disabled normalizer",
            "input": "{{Lien web|titre=TEST|url=https://example.com}}",
            "enabled": False,
            "expected_changes": 0,  # Should not change when disabled
        },
        # Test 8: Multiple parameters
        {
            "name": "Multiple parameters",
            "input": "{{Lien web|titre=TEST TITLE|auteur=JOHN DOE|site=NEWS SITE|url=https://example.com}}",
            "expected_changes": 3,  # titre, auteur, and site should be normalized
        },
        # Test 9: Publisher/editeur normalization
        {
            "name": "Publisher normalization",
            "input": "{{Ouvrage|éditeur=PUBLISHER NAME|titre=Book Title}}",
            "expected_changes": 1,  # Only éditeur should be normalized (titre is already proper)
        },
        # Test 10: Official company name preservation
        {
            "name": "Official company name preservation",
            "input": "{{Lien web|site=The New York Times|url=https://nytimes.com}}",
            "expected_changes": 0,  # The New York Times is an official name
        },
        # Test 11: Preserved expression
        {
            "name": "Preserved expression",
            "input": "{{Article|titre=History of États-Unis}}",
            "expected_changes": 0,  # États-Unis should be preserved
        },
    ]
    
    print("=" * 60)
    print("CASE NORMALIZER TEST SUITE")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")
        print(f"Input: {test_case['input']}")
        
        enabled = test_case.get('enabled', True)
        normalizer = CaseNormalizer(enabled=enabled)
        
        result = normalizer.normalize_text(test_case['input'])
        
        print(f"Output: {result.normalized_text}")
        print(f"Changes: {result.total_changes}")
        print(f"Ignored: {result.total_ignored}")
        
        # Show detailed reports
        for report in result.reports:
            print(f"  Template: {report.template_name}")
            for param, (before, after) in report.parameter_changes.items():
                print(f"    {param}: '{before}' -> '{after}'")
            for param, reason in report.ignored_occurrences:
                print(f"    {param}: ignored ({reason})")
        
        # Check if result matches expectations
        expected = test_case['expected_changes']
        if result.total_changes == expected:
            print(f"[PASS] Expected {expected} changes, got {result.total_changes}")
        else:
            print(f"[FAIL] Expected {expected} changes, got {result.total_changes}")
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETED")
    print("=" * 60)

def test_idempotency():
    """Test that the normalizer is idempotent (running twice produces same result)."""
    print("\n" + "=" * 60)
    print("IDEMPOTENCY TEST")
    print("=" * 60)
    
    test_cases = [
        # Already properly formatted text
        "{{Lien web|titre=Test Title|auteur=John Doe|url=https://example.com}}",
        # Text with proper mixed case
        "{{Article|titre=The Musical Part|auteur=van Gogh}}",
        # All lowercase (should capitalize first letter only once)
        "{{Lien web|titre=test article|url=https://example.com}}",
    ]
    
    normalizer = CaseNormalizer(enabled=True)
    
    all_pass = True
    for test_text in test_cases:
        print(f"\nTest: {test_text}")
        
        # First pass
        result1 = normalizer.normalize_text(test_text)
        print(f"First pass: {result1.normalized_text}")
        print(f"Changes: {result1.total_changes}")
        
        # Second pass on the result
        result2 = normalizer.normalize_text(result1.normalized_text)
        print(f"Second pass: {result2.normalized_text}")
        print(f"Changes: {result2.total_changes}")
        
        if result1.normalized_text == result2.normalized_text and result2.total_changes == 0:
            print("[PASS] Idempotent for this case")
        else:
            print("[FAIL] Not idempotent for this case")
            all_pass = False
    
    if all_pass:
        print("\n[PASS] Normalizer is idempotent for all test cases")
    else:
        print("\n[FAIL] Normalizer is not idempotent for some cases")

def test_french_specific():
    """Test French-specific cases (particles, accents, etc.)."""
    print("\n" + "=" * 60)
    print("FRENCH-SPECIFIC TESTS")
    print("=" * 60)
    
    test_cases = [
        "{{Article|auteur=de la Tour|titre=Test}}",
        "{{Article|auteur=van Gogh|titre=Painting}}",
        "{{Article|auteur=von Neumann|titre=Mathematics}}",
        "{{Lien web|titre=l'histoire de France|url=https://example.com}}",
    ]
    
    for test_text in test_cases:
        print(f"\nInput: {test_text}")
        normalizer = CaseNormalizer(enabled=True)
        result = normalizer.normalize_text(test_text)
        print(f"Output: {result.normalized_text}")
        print(f"Changes: {result.total_changes}")
        
        for report in result.reports:
            for param, (before, after) in report.parameter_changes.items():
                print(f"  {param}: '{before}' -> '{after}'")

def test_yaml_loading():
    """Test that the YAML configuration is loaded correctly."""
    print("\n" + "=" * 60)
    print("YAML LOADING TEST")
    print("=" * 60)
    
    normalizer = CaseNormalizer(enabled=True)
    
    print(f"Loaded {len(normalizer.common_acronyms)} acronyms")
    print(f"Loaded {len(normalizer.official_names)} official names")
    print(f"Loaded {len(normalizer.particles)} particles")
    print(f"Loaded {len(normalizer.preserved_expressions)} preserved expressions")
    print(f"Loaded {len(normalizer.domain_to_site_name)} domain mappings")
    
    # Test that specific known values are present
    assert 'ONU' in normalizer.common_acronyms, "ONU should be in acronyms"
    assert 'Le Monde' in normalizer.official_names, "Le Monde should be in official names"
    assert 'de' in normalizer.particles, "de should be in particles"
    assert 'États-Unis' in normalizer.preserved_expressions, "États-Unis should be in preserved expressions"
    
    print("[PASS] YAML configuration loaded correctly with expected values")

def test_acronym_false_positives():
    """Test that acronym detection doesn't produce false positives."""
    print("\n" + "=" * 60)
    print("ACRONYM FALSE POSITIVE TEST")
    print("=" * 60)
    
    test_cases = [
        # "ONU" should only match the exact acronym
        ("{{Lien web|titre=Report on ONU activities|url=https://example.com}}", "ONU should match exactly", False),
        # "USA" should not match in "USAGE" (all caps)
        ("{{Lien web|titre=USAGE STATISTICS|url=https://example.com}}", "USA should not match in 'USAGE'", True),
        # "NASA" should not match in "NASA" (all caps but not in acronym list if we test)
        ("{{Lien web|titre=NASA STUDY|url=https://example.com}}", "NASA should match exactly", False),
        # "WHO" should not match in "WHOLE" (all caps)
        ("{{Lien web|titre=WHOLE APPROACH|url=https://example.com}}", "WHO should not match in 'WHOLE'", True),
        # "UN" should not match in "UNDER" (all caps)
        ("{{Lien web|titre=UNDER DEVELOPMENT|url=https://example.com}}", "UN should not match in 'UNDER'", True),
    ]
    
    normalizer = CaseNormalizer(enabled=True)
    
    for test_text, description, should_change in test_cases:
        print(f"\nTest: {description}")
        print(f"Input: {test_text}")
        result = normalizer.normalize_text(test_text)
        print(f"Output: {result.normalized_text}")
        print(f"Changes: {result.total_changes}")
        
        # Check that acronyms are only matched as whole words
        if should_change:
            assert result.total_changes > 0, f"Should normalize but got {result.total_changes} changes"
        else:
            assert result.total_changes == 0, f"Should preserve but got {result.total_changes} changes"
    
    print("[PASS] Acronym detection correctly avoids false positives")

if __name__ == "__main__":
    test_case_normalizer()
    test_idempotency()
    test_french_specific()
    test_yaml_loading()
    test_acronym_false_positives()
