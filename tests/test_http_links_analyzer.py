"""
Tests unitaires pour HttpLinksAnalyzer - validation de la détection des liens HTTP non sécurisés

Ce test vérifie que HttpLinksAnalyzer détecte correctement :
- Les URL HTTP simples
- Les URL HTTP dans les références <ref>
- Les URL HTTP dans les modèles {{Lien web}}
- Les URL HTTP avec paramètres
- Les URL HTTP avec chemins
- Les URL HTTP avec fragments

Et ne génère PAS de faux positifs pour :
- Les URL HTTPS
- Les liens internes Wikipédia
- Les chaînes contenant "http://" mais n'étant pas des URL valides
"""

import sys
from pathlib import Path

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.analyzers.http_links import HttpLinksAnalyzer


def test_no_http_links():
    """Test qu'aucun lien HTTP n'est détecté quand il n'y en a pas"""
    analyzer = HttpLinksAnalyzer()
    
    test_cases = [
        "Ceci est un texte sans lien",
        "Les liens HTTPS sont https://example.com",
        "Lien interne [[Paris]]",
        "Modèle {{Lien web|url=https://example.com}}",
    ]
    
    for test_case in test_cases:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        assert len(issues) == 0, f"Expected no issues for: {test_case}"


def test_single_http_link():
    """Test la détection d'un seul lien HTTP"""
    analyzer = HttpLinksAnalyzer()
    
    test_cases = [
        "Lien http://example.com",
        "Visitez http://www.example.com pour plus d'infos",
        "http://example.org/article",
    ]
    
    for test_case in test_cases:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        assert len(issues) == 1, f"Expected 1 issue for: {test_case}"
        assert issues[0].issue_type == "http_link"
        assert issues[0].original_text.startswith("http://")
        assert issues[0].suggested_text.startswith("https://")


def test_multiple_http_links():
    """Test la détection de plusieurs liens HTTP"""
    analyzer = HttpLinksAnalyzer()
    
    test_case = "Liens : http://example.com et http://example.org"
    issues = analyzer.analyze(test_case)
    
    assert len(issues) == 2
    assert all(i.issue_type == "http_link" for i in issues)
    assert issues[0].original_text == "http://example.com"
    assert issues[1].original_text == "http://example.org"


def test_https_only():
    """Test que les liens HTTPS ne sont pas détectés"""
    analyzer = HttpLinksAnalyzer()
    
    test_cases = [
        "https://example.com",
        "https://www.example.com/page",
        "https://example.org/article?id=123",
    ]
    
    for test_case in test_cases:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        assert len(issues) == 0, f"HTTPS links should not be detected: {test_case}"


def test_http_in_ref():
    """Test la détection de liens HTTP dans les références <ref>"""
    analyzer = HttpLinksAnalyzer()
    
    test_case = "<ref>{{Lien web |url=http://example.com/article |titre=Exemple}}</ref>"
    issues = analyzer.analyze(test_case)
    
    assert len(issues) == 1
    assert issues[0].original_text == "http://example.com/article"
    assert issues[0].suggested_text == "https://example.com/article"


def test_http_in_template():
    """Test la détection de liens HTTP dans les modèles"""
    analyzer = HttpLinksAnalyzer()
    
    test_cases = [
        "{{Lien web|url=http://example.com|titre=Test}}",
        "{{cite web|url=http://example.org}}",
    ]
    
    for test_case in test_cases:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        assert len(issues) == 1, f"Expected 1 HTTP link in template: {test_case}"
        assert issues[0].original_text.startswith("http://")


def test_url_with_path():
    """Test la détection d'URL HTTP avec chemin"""
    analyzer = HttpLinksAnalyzer()
    
    test_cases = [
        "http://example.com/page",
        "http://example.com/path/to/article",
        "http://example.org/wiki/Test",
    ]
    
    for test_case in test_cases:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        assert len(issues) == 1
        assert issues[0].suggested_text == test_case.replace("http://", "https://")


def test_url_with_parameters():
    """Test la détection d'URL HTTP avec paramètres"""
    analyzer = HttpLinksAnalyzer()
    
    test_cases = [
        "http://example.com/article?id=123",
        "http://example.org?page=1&sort=name",
        "http://example.net?q=test&lang=fr",
    ]
    
    for test_case in test_cases:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        assert len(issues) == 1
        assert issues[0].suggested_text == test_case.replace("http://", "https://")


def test_url_with_fragment():
    """Test la détection d'URL HTTP avec fragment"""
    analyzer = HttpLinksAnalyzer()
    
    test_cases = [
        "http://example.com/page#section",
        "http://example.org#intro",
    ]
    
    for test_case in test_cases:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        assert len(issues) == 1
        assert issues[0].suggested_text == test_case.replace("http://", "https://")


def test_mixed_http_https():
    """Test la détection dans un mélange HTTP/HTTPS"""
    analyzer = HttpLinksAnalyzer()
    
    test_case = "Liens HTTP : http://example.com et HTTPS : https://example.org"
    issues = analyzer.analyze(test_case)
    
    assert len(issues) == 1
    assert issues[0].original_text == "http://example.com"
    assert issues[0].suggested_text == "https://example.com"


def test_internal_links_not_detected():
    """Test que les liens internes Wikipédia ne sont pas détectés"""
    analyzer = HttpLinksAnalyzer()
    
    test_cases = [
        "[[Paris]]",
        "[[Article|Titre]]",
        "[[Fichier:Image.jpg]]",
        "[[Catégorie:Test]]",
    ]
    
    for test_case in test_cases:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        assert len(issues) == 0, f"Internal links should not be detected: {test_case}"


def test_protected_areas():
    """Test que les liens HTTP dans les zones protégées sont ignorés"""
    analyzer = HttpLinksAnalyzer()
    
    test_cases = [
        "<nowiki>http://example.com</nowiki>",
        "<!-- http://example.com -->",
        "<pre>http://example.com</pre>",
    ]
    
    for test_case in test_cases:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        assert len(issues) == 0, f"Protected areas should be ignored: {test_case}"


def test_max_issues_limit():
    """Test la limitation du nombre d'issues"""
    analyzer = HttpLinksAnalyzer(max_issues=2)
    
    test_case = "Liens : http://example1.com http://example2.com http://example3.com"
    issues = analyzer.analyze(test_case)
    
    assert len(issues) == 2


def test_correction_preserves_url():
    """Test que la correction préserve l'URL exacte sauf le protocole"""
    analyzer = HttpLinksAnalyzer()
    
    test_url = "http://example.com/path/to/page?id=123&lang=fr#section"
    analyzer.clear_issues()
    issues = analyzer.analyze(test_url)
    
    assert len(issues) == 1
    assert issues[0].original_text == test_url
    assert issues[0].suggested_text == "https://example.com/path/to/page?id=123&lang=fr#section"


if __name__ == "__main__":
    # Exécuter tous les tests
    test_no_http_links()
    print("[OK] test_no_http_links")
    
    test_single_http_link()
    print("[OK] test_single_http_link")
    
    test_multiple_http_links()
    print("[OK] test_multiple_http_links")
    
    test_https_only()
    print("[OK] test_https_only")
    
    test_http_in_ref()
    print("[OK] test_http_in_ref")
    
    test_http_in_template()
    print("[OK] test_http_in_template")
    
    test_url_with_path()
    print("[OK] test_url_with_path")
    
    test_url_with_parameters()
    print("[OK] test_url_with_parameters")
    
    test_url_with_fragment()
    print("[OK] test_url_with_fragment")
    
    test_mixed_http_https()
    print("[OK] test_mixed_http_https")
    
    test_internal_links_not_detected()
    print("[OK] test_internal_links_not_detected")
    
    test_protected_areas()
    print("[OK] test_protected_areas")
    
    test_max_issues_limit()
    print("[OK] test_max_issues_limit")
    
    test_correction_preserves_url()
    print("[OK] test_correction_preserves_url")
    
    print("\n[SUCCESS] All tests passed!")
