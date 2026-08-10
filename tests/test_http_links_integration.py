"""
Test d'intégration bout en bout pour HttpLinksAnalyzer

Ce test vérifie le chemin complet :
1. Détection → Issue
2. Issue → correction 
3. Correction → wikicode corrigé
4. Wikicode corrigé → réanalyse (pas de nouveau détection)
"""

import sys
from pathlib import Path

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.analyzers.http_links import HttpLinksAnalyzer
from wikipedia_maintenance.utils.corrector import Corrector


def test_end_to_end_http_link_correction():
    """Test le chemin complet de détection et correction d'un lien HTTP"""
    
    # Contenu original avec lien HTTP dans un modèle
    original_content = """{{Lien web
 |url=http://example.com/article
 |titre=Exemple
}}"""
    
    # Étape 1: Détection
    analyzer = HttpLinksAnalyzer()
    issues = analyzer.analyze(original_content)
    
    assert len(issues) == 1, "Expected exactly 1 HTTP link detected"
    assert issues[0].issue_type == "http_link"
    assert issues[0].original_text == "http://example.com/article"
    assert issues[0].suggested_text == "https://example.com/article"
    assert issues[0].position is not None
    
    print("Step 1 - Detection: HTTP link detected correctly")
    print(f"  Original: {issues[0].original_text}")
    print(f"  Suggested: {issues[0].suggested_text}")
    
    # Étape 2: Correction via Corrector
    corrector = Corrector(original_content)
    corrected_content = corrector.apply_corrections(issues)
    
    print("Step 2 - Correction: Applied via Corrector")
    print(f"  Original content:\n{original_content}")
    print(f"  Corrected content:\n{corrected_content}")
    
    # Vérifier que la correction a été appliquée
    assert "http://example.com/article" not in corrected_content, "HTTP link should be removed"
    assert "https://example.com/article" in corrected_content, "HTTPS link should be present"
    assert corrector.corrections[0].applied == True, "Correction should be marked as applied"
    
    # Étape 3: Réanalyse du contenu corrigé
    analyzer.clear_issues()
    reanalyzed_issues = analyzer.analyze(corrected_content)
    
    print("Step 3 - Re-analysis: Checking corrected content")
    print(f"  Issues found after correction: {len(reanalyzed_issues)}")
    
    # Vérifier qu'aucun nouveau lien HTTP n'est détecté
    assert len(reanalyzed_issues) == 0, "No HTTP links should be detected after correction"
    
    print("Step 4 - Verification: No HTTP links in corrected content")
    print("SUCCESS: Full end-to-end pipeline working correctly")


def test_end_to_end_multiple_http_links():
    """Test avec plusieurs liens HTTP"""
    
    original_content = """
Voici quelques liens :
* http://example1.com/page1
* http://example2.org/page2?id=123
* http://example3.net#section
"""
    
    # Étape 1: Détection
    analyzer = HttpLinksAnalyzer()
    issues = analyzer.analyze(original_content)
    
    assert len(issues) == 3, f"Expected 3 HTTP links, got {len(issues)}"
    
    print("Step 1 - Detection: Multiple HTTP links detected")
    for i, issue in enumerate(issues):
        print(f"  Link {i+1}: {issue.original_text} -> {issue.suggested_text}")
    
    # Étape 2: Correction
    corrector = Corrector(original_content)
    corrected_content = corrector.apply_corrections(issues)
    
    print("Step 2 - Correction: All links corrected")
    
    # Vérifier que tous les liens HTTP ont été corrigés
    assert "http://" not in corrected_content, "No HTTP links should remain"
    assert corrected_content.count("https://") == 3, "All 3 links should be HTTPS"
    
    # Étape 3: Réanalyse
    analyzer.clear_issues()
    reanalyzed_issues = analyzer.analyze(corrected_content)
    
    assert len(reanalyzed_issues) == 0, "No HTTP links should remain after correction"
    
    print("SUCCESS: Multiple HTTP links corrected and verified")


def test_end_to_end_mixed_http_https():
    """Test avec mélange HTTP et HTTPS"""
    
    original_content = """
Liens mixtes :
* HTTP: http://example.com/page
* HTTPS: https://example.org/secure
* HTTP: http://example.net/another
"""
    
    # Étape 1: Détection
    analyzer = HttpLinksAnalyzer()
    issues = analyzer.analyze(original_content)
    
    assert len(issues) == 2, "Only HTTP links should be detected (not HTTPS)"
    
    print("Step 1 - Detection: Only HTTP links detected (HTTPS ignored)")
    for i, issue in enumerate(issues):
        print(f"  HTTP link {i+1}: {issue.original_text}")
    
    # Étape 2: Correction
    corrector = Corrector(original_content)
    corrected_content = corrector.apply_corrections(issues)
    
    # Vérifier que seuls les liens HTTP ont été modifiés
    assert "http://example.com/page" not in corrected_content
    assert "https://example.com/page" in corrected_content
    assert "https://example.org/secure" in corrected_content  # HTTPS inchangé
    assert "http://example.net/another" not in corrected_content
    assert "https://example.net/another" in corrected_content
    
    print("Step 2 - Correction: Only HTTP links converted, HTTPS preserved")
    
    # Étape 3: Réanalyse
    analyzer.clear_issues()
    reanalyzed_issues = analyzer.analyze(corrected_content)
    
    assert len(reanalyzed_issues) == 0, "No HTTP links should remain"
    
    print("SUCCESS: Mixed HTTP/HTTPS handled correctly")


def test_protected_areas_integration():
    """Test que les zones protégées sont respectées dans le pipeline"""
    
    original_content = """
<nowiki>http://example.com/protected</nowiki>
Lien normal: http://example.org/unprotected
<!-- http://example.com/comment -->
"""
    
    # Étape 1: Détection
    analyzer = HttpLinksAnalyzer()
    issues = analyzer.analyze(original_content)
    
    # Seul le lien non protégé doit être détecté
    assert len(issues) == 1, "Only unprotected HTTP link should be detected"
    assert "unprotected" in issues[0].original_text
    
    print("Step 1 - Detection: Protected areas correctly ignored")
    print(f"  Detected: {issues[0].original_text}")
    
    # Étape 2: Correction
    corrector = Corrector(original_content)
    corrected_content = corrector.apply_corrections(issues)
    
    # Vérifier que seul le lien non protégé a été modifié
    assert "http://example.com/protected" in corrected_content  # Protégé, inchangé
    assert "https://example.org/unprotected" in corrected_content  # Non protégé, corrigé
    assert "http://example.com/comment" in corrected_content  # Commentaire, inchangé
    
    print("Step 2 - Correction: Protected areas preserved")
    
    # Étape 3: Réanalyse
    analyzer.clear_issues()
    reanalyzed_issues = analyzer.analyze(corrected_content)
    
    # Le lien protégé est toujours là mais ignoré, donc 0 issues
    assert len(reanalyzed_issues) == 0
    
    print("SUCCESS: Protected areas integration working correctly")


def test_url_with_parameters_integration():
    """Test avec URL complexes (paramètres, fragments)"""
    
    original_content = "{{Lien web|url=http://example.com/article?id=123&lang=fr#section|titre=Test}}"
    
    # Étape 1: Détection
    analyzer = HttpLinksAnalyzer()
    issues = analyzer.analyze(original_content)
    
    assert len(issues) == 1
    expected_url = "http://example.com/article?id=123&lang=fr#section"
    assert issues[0].original_text == expected_url
    
    print("Step 1 - Detection: Complex URL with parameters detected")
    print(f"  URL: {issues[0].original_text}")
    
    # Étape 2: Correction
    corrector = Corrector(original_content)
    corrected_content = corrector.apply_corrections(issues)
    
    expected_corrected = "https://example.com/article?id=123&lang=fr#section"
    assert expected_corrected in corrected_content
    
    print("Step 2 - Correction: Complex URL converted preserving parameters")
    
    # Étape 3: Réanalyse
    analyzer.clear_issues()
    reanalyzed_issues = analyzer.analyze(corrected_content)
    
    assert len(reanalyzed_issues) == 0
    
    print("SUCCESS: Complex URLs handled correctly in pipeline")


if __name__ == "__main__":
    print("=" * 60)
    print("HTTP LINKS ANALYZER - END-TO-END INTEGRATION TESTS")
    print("=" * 60)
    print()
    
    test_end_to_end_http_link_correction()
    print()
    
    test_end_to_end_multiple_http_links()
    print()
    
    test_end_to_end_mixed_http_https()
    print()
    
    test_protected_areas_integration()
    print()
    
    test_url_with_parameters_integration()
    print()
    
    print("=" * 60)
    print("ALL INTEGRATION TESTS PASSED")
    print("=" * 60)
