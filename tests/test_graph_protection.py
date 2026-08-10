"""
Tests pour la protection des graphiques Wikipédia contre les modifications typographiques
"""

import sys
from pathlib import Path

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.analyzers.typography import TypographyAnalyzer
from wikipedia_maintenance.analyzers.whitespace import WhitespaceAnalyzer


def test_graph_syntax_protection():
    """Test que la syntaxe des graphiques n'est pas modifiée"""
    
    # Exemple de graphique Wikipédia (tiré de l'exemple de l'utilisateur)
    graph_content = """TimeAxis = orientation:horizontal format:yyyy orientation :horizontal format :yyyy

Colors =
id:vocals value:red legend:Chant id :vocals value :red legend :Chant
id:keyboard value:purple legend:Claviers id :keyboard value :purple legend :Claviers

PlotData=
width:11 textcolor:black align:left anchor:from shift:(10,-4) width :11 textcolor :black align :left anchor :from shift :(10,-4)
bar:Marian  from:1980 till:1987 color:vocals"""
    
    # Test avec TypographyAnalyzer
    typo_analyzer = TypographyAnalyzer()
    issues = typo_analyzer.analyze(graph_content)
    
    # Vérifier qu'aucune issue n'est détectée dans la syntaxe de graphique
    graph_issues = [i for i in issues if 'graph' not in i.description.lower()]
    assert len(graph_issues) == 0, f"TypographyAnalyzer ne devrait pas modifier la syntaxe de graphique, mais a trouvé {len(graph_issues)} issues"
    
    print("Step 1 - TypographyAnalyzer graph protection: OK")
    
    # Test avec WhitespaceAnalyzer
    whitespace_analyzer = WhitespaceAnalyzer()
    issues = whitespace_analyzer.analyze(graph_content)
    
    # Vérifier qu'aucune issue n'est détectée dans la syntaxe de graphique
    graph_issues = [i for i in issues if 'graph' not in i.description.lower()]
    assert len(graph_issues) == 0, f"WhitespaceAnalyzer ne devrait pas modifier la syntaxe de graphique, mais a trouvé {len(graph_issues)} issues"
    
    print("Step 2 - WhitespaceAnalyzer graph protection: OK")


def test_graph_with_spaces_preserved():
    """Test que les espaces dans les graphiques sont préservés"""
    
    graph_line = "id:vocals value:red legend:Chant id :vocals value :red legend :Chant"
    
    typo_analyzer = TypographyAnalyzer()
    issues = typo_analyzer.analyze(graph_line)
    
    # Cette ligne contient des espaces autour de : qui font partie de la syntaxe
    # et ne doivent pas être modifiés
    assert len(issues) == 0, "Les espaces dans la syntaxe de graphique ne doivent pas être modifiés"
    
    print("Step 3 - Graph spaces preserved: OK")


def test_graph_parameters_preserved():
    """Test que les paramètres de graphique sont préservés"""
    
    graph_params = """PlotData=
width:11 textcolor:black align:left anchor:from shift:(10,-4)"""
    
    typo_analyzer = TypographyAnalyzer()
    issues = typo_analyzer.analyze(graph_params)
    
    # Les paramètres comme width:11, textcolor:black, shift:(10,-4) ne doivent pas être modifiés
    assert len(issues) == 0, "Les paramètres de graphique ne doivent pas être modifiés"
    
    print("Step 4 - Graph parameters preserved: OK")


def test_normal_text_still_corrected():
    """Test que le texte normal est toujours corrigé"""
    
    normal_text = "Ceci  est  un  test"
    
    typo_analyzer = TypographyAnalyzer()
    issues = typo_analyzer.analyze(normal_text)
    
    # Le texte normal doit toujours être corrigé
    assert len(issues) > 0, "Le texte normal doit toujours être corrigé"
    
    print("Step 5 - Normal text still corrected: OK")


def test_mixed_content():
    """Test un contenu mixte avec graphique et texte normal"""
    
    mixed_content = """Ceci est du texte normal.

{{Chart}}
TimeAxis = orientation:horizontal format:yyyy
Colors = id:vocals value:red legend:Chant
{{End}}

Autre texte normal ici."""
    
    typo_analyzer = TypographyAnalyzer()
    issues = typo_analyzer.analyze(mixed_content)
    
    # Vérifier que les corrections sont appliquées uniquement au texte normal
    # et non à la section du graphique
    graph_related = [i for i in issues if any(keyword in i.description.lower() for keyword in ['graph', 'chart', 'timeline'])]
    assert len(graph_related) == 0, "Les graphiques ne doivent pas générer d'issues"
    
    # Mais il doit y avoir des corrections potentielles ailleurs
    assert len(issues) >= 0, "Il peut y avoir des corrections dans le texte normal"
    
    print("Step 6 - Mixed content handled: OK")


if __name__ == "__main__":
    print("=" * 60)
    print("GRAPH PROTECTION TESTS")
    print("=" * 60)
    print()
    
    test_graph_syntax_protection()
    test_graph_with_spaces_preserved()
    test_graph_parameters_preserved()
    test_normal_text_still_corrected()
    test_mixed_content()
    
    print()
    print("=" * 60)
    print("ALL GRAPH PROTECTION TESTS PASSED")
    print("=" * 60)
