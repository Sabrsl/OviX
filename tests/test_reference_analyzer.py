"""
Tests unitaires pour ReferenceAnalyzer - détection des points avant </ref>
"""

import sys
from pathlib import Path

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.analyzers.reference_analyzer import ReferenceAnalyzer


def test_detect_period_before_ref_close():
    """Test la détection des points mal placés avant </ref>"""
    
    analyzer = ReferenceAnalyzer()
    
    # Cas positifs : doivent être détectés
    test_cases_positive = [
        "{{Lien web|x}}.</ref>",
        "{{Ouvrage|x}}. </ref>",
        "{{Article|x}}.    </ref>",
        "{{Lien web|url=http://example.com|titre=Test}}.</ref>",
    ]
    
    for test_case in test_cases_positive:
        analyzer.clear_issues()
        analyzer._detect_period_before_ref_close(test_case)
        assert len(analyzer.issues) == 1, f"Devrait détecter : {test_case}"
        assert analyzer.issues[0].issue_type == "period_before_ref_close"
        print(f"✅ Détection correcte : {test_case}")
    
    # Cas négatifs : ne doivent PAS être détectés
    test_cases_negative = [
        "Jean Dupont.</ref>",
        "Paris.</ref>",
        "{{Lien web|x}}</ref>.",
        "{{Lien web|x}}</ref>",
        "Dupont, Jean. Histoire du Maroc.</ref>",  # Point valide dans le contenu
    ]
    
    for test_case in test_cases_negative:
        analyzer.clear_issues()
        analyzer._detect_period_before_ref_close(test_case)
        assert len(analyzer.issues) == 0, f"Ne devrait PAS détecter : {test_case}"
        print(f"✅ Ignoré correctement : {test_case}")
    
    print("\n✅ Tous les tests passés pour _detect_period_before_ref_close")


if __name__ == "__main__":
    test_detect_period_before_ref_close()
