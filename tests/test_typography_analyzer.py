"""
Tests unitaires pour TypographyAnalyzer - validation des corrections mécaniques déterministes

Ce test vérifie que TypographyAnalyzer n'effectue QUE les corrections autorisées :
- Suppression des espaces doubles
- Suppression des espaces en fin de ligne
- Suppression des lignes vides multiples
- Normalisation des espaces avant : ; ? !
- Normalisation des guillemets français
- Correction des intervalles numériques
- Ajout de l'espace avant %
- Ajout des espaces entre nombres et unités
- Simplification des liens internes identiques
- Suppression des catégories dupliquées

ET N'effectue PAS :
- de reformulation
- de correction grammaticale
- de correction orthographique
- de wikification
- d'ajout ou suppression de contenu
- de modification des références
- de modification des modèles
- de modification des dates, chiffres ou informations factuelles
"""

import sys
from pathlib import Path

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.analyzers.typography import TypographyAnalyzer


def test_double_spaces():
    """Test la détection des espaces doubles"""
    analyzer = TypographyAnalyzer(check_double_spaces=True)
    
    # Cas positifs : doivent être détectés
    test_cases_positive = [
        "Ceci  est  un  test",
        "Mot  double",
        "Texte   avec   triples   espaces",
    ]
    
    for test_case in test_cases_positive:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)  # Using analyze method which handles masking
        double_space_issues = [i for i in issues if i.issue_type == "double_space"]
        assert len(double_space_issues) > 0, f"Devrait détecter les espaces doubles dans : {test_case}"
        print(f"✅ Détection correcte des espaces doubles : {test_case}")
    
    # Cas négatifs : ne doivent PAS être détectés
    test_cases_negative = [
        "Ceci est un test",
        "Mot simple",
        "Texte normal",
    ]
    
    for test_case in test_cases_negative:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        double_space_issues = [i for i in issues if i.issue_type == "double_space"]
        assert len(double_space_issues) == 0, f"Ne devrait pas détecter d'espaces doubles dans : {test_case}"
        print(f"✅ Ignoré correctement (pas d'espaces doubles) : {test_case}")


def test_trailing_spaces():
    """Test la détection des espaces en fin de ligne"""
    analyzer = TypographyAnalyzer(check_trailing_spaces=True)
    
    # Cas positifs : doivent être détectés
    test_cases_positive = [
        "Ligne avec espaces   \n",
        "Ligne avec espaces\t\n",
        "Ligne avec espaces   ",
    ]
    
    for test_case in test_cases_positive:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        trailing_space_issues = [i for i in issues if i.issue_type == "trailing_space"]
        assert len(trailing_space_issues) > 0, f"Devrait détecter les espaces en fin de ligne dans : {repr(test_case)}"
        print(f"✅ Détection correcte des espaces en fin de ligne : {repr(test_case)}")
    
    # Cas négatifs : ne doivent PAS être détectés
    test_cases_negative = [
        "Ligne normale\n",
        "Ligne sans retour",
        "Ligne propre\n",
    ]
    
    for test_case in test_cases_negative:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        trailing_space_issues = [i for i in issues if i.issue_type == "trailing_space"]
        assert len(trailing_space_issues) == 0, f"Ne devrait pas détecter d'espaces en fin de ligne dans : {repr(test_case)}"
        print(f"✅ Ignoré correctement (pas d'espaces en fin de ligne) : {repr(test_case)}")


def test_multiple_blank_lines():
    """Test la détection des lignes vides multiples"""
    analyzer = TypographyAnalyzer(check_multiple_blank_lines=True)
    
    # Cas positifs : doivent être détectés
    test_cases_positive = [
        "Ligne 1\n\n\nLigne 2",
        "Ligne 1\n\n\n\nLigne 2",
        "Ligne 1\n\n\n\n\nLigne 2",
    ]
    
    for test_case in test_cases_positive:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        blank_line_issues = [i for i in issues if i.issue_type == "multiple_blank_lines"]
        assert len(blank_line_issues) > 0, f"Devrait détecter les lignes vides multiples dans : {repr(test_case)}"
        print(f"✅ Détection correcte des lignes vides multiples : {repr(test_case)}")
    
    # Cas négatifs : ne doivent PAS être détectés
    test_cases_negative = [
        "Ligne 1\n\nLigne 2",
        "Ligne 1\nLigne 2",
        "Ligne seule",
    ]
    
    for test_case in test_cases_negative:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        blank_line_issues = [i for i in issues if i.issue_type == "multiple_blank_lines"]
        assert len(blank_line_issues) == 0, f"Ne devrait pas détecter de lignes vides multiples dans : {repr(test_case)}"
        print(f"✅ Ignoré correctement (pas de lignes vides multiples) : {repr(test_case)}")


def test_punctuation_spacing():
    """Test la normalisation des espaces avant : ; ? !"""
    analyzer = TypographyAnalyzer(check_punctuation_spacing=True)
    
    # Cas positifs : doivent être détectés
    test_cases_positive = [
        "Mot: autre",
        "Mot; autre",
        "Mot? autre",
        "Mot! autre",
    ]
    
    for test_case in test_cases_positive:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        punctuation_issues = [i for i in issues if i.issue_type == "punctuation_spacing"]
        assert len(punctuation_issues) > 0, f"Devrait détecter l'espace manquant dans : {test_case}"
        print(f"✅ Détection correcte de l'espace manquant : {test_case}")
    
    # Cas négatifs : ne doivent PAS être détectés
    test_cases_negative = [
        "12:30",  # Heures
        "Mot : autre",  # Déjà correct
        "Mot ; autre",  # Déjà correct
    ]
    
    for test_case in test_cases_negative:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        punctuation_issues = [i for i in issues if i.issue_type == "punctuation_spacing"]
        assert len(punctuation_issues) == 0, f"Ne devrait pas détecter d'espace manquant dans : {test_case}"
        print(f"✅ Ignoré correctement : {test_case}")


def test_french_quotes():
    """Test la normalisation des guillemets français"""
    analyzer = TypographyAnalyzer(check_french_quotes=True)
    
    # Cas positifs : doivent être détectés
    test_cases_positive = [
        '"texte"',
        '"autre texte"',
        '"citation"',
    ]
    
    for test_case in test_cases_positive:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        quote_issues = [i for i in issues if i.issue_type == "french_quotes"]
        assert len(quote_issues) > 0, f"Devrait détecter les guillemets droits dans : {test_case}"
        print(f"✅ Détection correcte des guillemets droits : {test_case}")
    
    # Cas négatifs : ne doivent PAS être détectés
    test_cases_negative = [
        "'texte'",
        "« texte »",
        "déjà correct",
    ]
    
    for test_case in test_cases_negative:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        quote_issues = [i for i in issues if i.issue_type == "french_quotes"]
        assert len(quote_issues) == 0, f"Ne devrait pas détecter de guillemets droits dans : {test_case}"
        print(f"✅ Ignoré correctement : {test_case}")


def test_numeric_intervals():
    """Test la correction des intervalles numériques"""
    analyzer = TypographyAnalyzer(check_numeric_intervals=True)
    
    # Cas positifs : doivent être détectés
    test_cases_positive = [
        "1914 - 1918",
        "10 - 20",
        "1000 - 2000",
    ]
    
    for test_case in test_cases_positive:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        interval_issues = [i for i in issues if i.issue_type == "numeric_interval"]
        assert len(interval_issues) > 0, f"Devrait détecter l'intervalle numérique dans : {test_case}"
        print(f"✅ Détection correcte de l'intervalle numérique : {test_case}")
    
    # Cas négatifs : ne doivent PAS être détectés
    test_cases_negative = [
        "Paris - Londres",
        "texte - autre",
        "mot - mot",
    ]
    
    for test_case in test_cases_negative:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        interval_issues = [i for i in issues if i.issue_type == "numeric_interval"]
        assert len(interval_issues) == 0, f"Ne devrait pas détecter d'intervalle numérique dans : {test_case}"
        print(f"✅ Ignoré correctement : {test_case}")


def test_percent_spacing():
    """Test l'ajout de l'espace avant %"""
    analyzer = TypographyAnalyzer(check_percent_spacing=True)
    
    # Cas positifs : doivent être détectés
    test_cases_positive = [
        "10%",
        "50%",
        "100%",
    ]
    
    for test_case in test_cases_positive:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        percent_issues = [i for i in issues if i.issue_type == "percent_spacing"]
        assert len(percent_issues) > 0, f"Devrait détecter l'espace manquant dans : {test_case}"
        print(f"✅ Détection correcte de l'espace manquant avant % : {test_case}")
    
    # Cas négatifs : ne doivent PAS être détectés
    test_cases_negative = [
        "10 %",
        "50 %",
        "déjà correct",
    ]
    
    for test_case in test_cases_negative:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        percent_issues = [i for i in issues if i.issue_type == "percent_spacing"]
        assert len(percent_issues) == 0, f"Ne devrait pas détecter d'espace manquant dans : {test_case}"
        print(f"✅ Ignoré correctement : {test_case}")


def test_unit_spacing():
    """Test l'ajout des espaces entre nombres et unités"""
    analyzer = TypographyAnalyzer(check_unit_spacing=True)
    
    # Cas positifs : doivent être détectés
    test_cases_positive = [
        "10km",
        "25kg",
        "50°C",
        "100m",
    ]
    
    for test_case in test_cases_positive:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        unit_issues = [i for i in issues if i.issue_type == "unit_spacing"]
        assert len(unit_issues) > 0, f"Devrait détecter l'espace manquant dans : {test_case}"
        print(f"✅ Détection correcte de l'espace manquant avant unité : {test_case}")
    
    # Cas négatifs : ne doivent PAS être détectés
    test_cases_negative = [
        "10 km",
        "25 kg",
        "50 °C",
        "déjà correct",
    ]
    
    for test_case in test_cases_negative:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        unit_issues = [i for i in issues if i.issue_type == "unit_spacing"]
        assert len(unit_issues) == 0, f"Ne devrait pas détecter d'espace manquant dans : {test_case}"
        print(f"✅ Ignoré correctement : {test_case}")


def test_duplicate_links():
    """Test la simplification des liens internes identiques"""
    analyzer = TypographyAnalyzer()
    
    # Cas positifs : doivent être détectés
    test_cases_positive = [
        "[[Paris|Paris]]",
        "[[France|France]]",
        "[[Test|Test]]",
    ]
    
    for test_case in test_cases_positive:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        link_issues = [i for i in issues if i.issue_type == "duplicate_link"]
        assert len(link_issues) > 0, f"Devrait détecter le lien dupliqué dans : {test_case}"
        print(f"✅ Détection correcte du lien dupliqué : {test_case}")
    
    # Cas négatifs : ne doivent PAS être détectés
    test_cases_negative = [
        "[[Paris|France]]",  # Alias différent
        "[[Paris]]",  # Déjà simplifié
        "Texte normal",
    ]
    
    for test_case in test_cases_negative:
        analyzer.clear_issues()
        issues = analyzer.analyze(test_case)
        link_issues = [i for i in issues if i.issue_type == "duplicate_link"]
        assert len(link_issues) == 0, f"Ne devrait pas détecter de lien dupliqué dans : {test_case}"
        print(f"✅ Ignoré correctement : {test_case}")


def test_no_undesired_corrections():
    """Test que l'analyseur n'effectue PAS de corrections non autorisées"""
    analyzer = TypographyAnalyzer()
    
    # Test que l'analyseur ne fait pas de correction grammaticale
    text_with_grammar_error = "Il vont au magasin"
    issues = analyzer.analyze(text_with_grammar_error)
    grammar_issues = [i for i in issues if i.issue_type in ["grammar", "spelling", "reformulation"]]
    assert len(grammar_issues) == 0, "Ne devrait pas corriger les erreurs grammaticales"
    print("✅ Pas de correction grammaticale")
    
    # Test que l'analyseur ne fait pas de correction orthographique
    text_with_spelling_error = "La pharse est mal orthographiée"
    issues = analyzer.analyze(text_with_spelling_error)
    spelling_issues = [i for i in issues if i.issue_type in ["spelling", "orthographique"]]
    assert len(spelling_issues) == 0, "Ne devrait pas corriger les erreurs orthographiques"
    print("✅ Pas de correction orthographique")
    
    # Test que l'analyseur ne modifie pas les références
    text_with_ref = "Ceci est une référence<ref>source</ref>."
    issues = analyzer.analyze(text_with_ref)
    ref_issues = [i for i in issues if "ref" in i.issue_type.lower()]
    assert len(ref_issues) == 0, "Ne devrait pas modifier les références"
    print("✅ Pas de modification des références")
    
    # Test que l'analyseur ne modifie pas les modèles
    text_with_template = "{{Infobox}}"
    issues = analyzer.analyze(text_with_template)
    template_issues = [i for i in issues if "template" in i.issue_type.lower()]
    assert len(template_issues) == 0, "Ne devrait pas modifier les modèles"
    print("✅ Pas de modification des modèles")
    
    # Test que l'analyseur ne fait pas de wikification
    text_plain = "Ceci est du texte sans wikification"
    issues = analyzer.analyze(text_plain)
    wikification_issues = [i for i in issues if "wiki" in i.issue_type.lower() or "link" in i.issue_type.lower()]
    assert len(wikification_issues) == 0, "Ne devrait pas faire de wikification automatique"
    print("✅ Pas de wikification automatique")


def test_only_deterministic_rules():
    """Test que toutes les corrections sont déterministes et basées sur des règles"""
    analyzer = TypographyAnalyzer()
    
    # Test avec un texte simple
    simple_text = "Ceci est un test  avec des espaces  doubles."
    issues = analyzer.analyze(simple_text)
    
    # Vérifier que toutes les issues sont de types autorisés
    allowed_types = [
        "double_space",
        "trailing_space", 
        "multiple_blank_lines",
        "punctuation_spacing",
        "french_quotes",
        "numeric_interval",
        "percent_spacing",
        "unit_spacing",
        "duplicate_category",
        "duplicate_link"
    ]
    
    for issue in issues:
        assert issue.issue_type in allowed_types, f"Type d'issue non autorisé : {issue.issue_type}"
    
    print("✅ Toutes les corrections sont de types autorisés")


def run_all_tests():
    """Exécute tous les tests"""
    print("=== DÉBUT DES TESTS TypographyAnalyzer ===\n")
    
    print("Test 1: Espaces doubles")
    test_double_spaces()
    print()
    
    print("Test 2: Espaces en fin de ligne")
    test_trailing_spaces()
    print()
    
    print("Test 3: Lignes vides multiples")
    test_multiple_blank_lines()
    print()
    
    print("Test 4: Espaces avant ponctuation")
    test_punctuation_spacing()
    print()
    
    print("Test 5: Guillemets français")
    test_french_quotes()
    print()
    
    print("Test 6: Intervalles numériques")
    test_numeric_intervals()
    print()
    
    print("Test 7: Espaces avant %")
    test_percent_spacing()
    print()
    
    print("Test 8: Espaces avant unités")
    test_unit_spacing()
    print()
    
    print("Test 9: Liens dupliqués")
    test_duplicate_links()
    print()
    
    print("Test 10: Pas de corrections non autorisées")
    test_no_undesired_corrections()
    print()
    
    print("Test 11: Règles uniquement déterministes")
    test_only_deterministic_rules()
    print()
    
    print("=== TOUS LES TESTS PASSÉS ✅ ===")


if __name__ == "__main__":
    run_all_tests()
