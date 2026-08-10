"""
Tests pour la protection des graphiques dans WhitespaceAnalyzer
"""

import sys
from pathlib import Path

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.analyzers.whitespace import WhitespaceAnalyzer


def test_graph_whitespace_protection():
    """Test que WhitespaceAnalyzer ne modifie pas la syntaxe des graphiques"""
    
    graph_content = """TimeAxis = orientation:horizontal format:yyyy orientation :horizontal format :yyyy

Colors =
id:vocals value:red legend:Chant id :vocals value :red legend :Chant
id:keyboard value:purple legend:Claviers id :keyboard value :purple legend :Claviers
id:guitar value:green legend:Guitare id :guitar value :green legend :Guitare
id:bass value:blue legend:Basse id :bass value :blue legend :Basse
id:drums value:orange legend:Batterie id :drums value :orange legend :Batterie
id:lines1 value:black legend:Album_studio id :lines1 value :black legend :Album_studio
id:bars value:gray(0.93) id :bars value :gray(0.93)

Legend = orientation:horizontal position:bottom orientation :horizontal position :bottom
BackgroundColors = bars:bars bars :bars
ScaleMajor = increment:2 start:1982 increment :2 start :1982
ScaleMinor = increment:1 start:1982 increment :1 start :1982

LineData =
at:09/27/1984 color:lines1 layer:back at :09/27/1984 color :lines1 layer :back
at:06/05/1986 color:lines1 layer:back at :06/05/1986 color :lines1 layer :back
at:04/04/1989 color:lines1 layer:back at :04/04/1989 color :lines1 layer :back
at:08/26/1994 color:lines1 layer:back at :08/26/1994 color :lines1 layer :back
at:09/01/1997 color:lines1 layer:back at :09/01/1997 color :lines1 layer :back
at:11/19/2010 color:lines1 layer:back at :11/19/2010 color :lines1 layer :back
at:04/07/2017 color:lines1 layer:back at :04/07/2017 color :lines1 layer :back

BarData =
bar:Marian text:Marian Gold bar :Marian text :Marian Gold
bar:Bernhard text:Bernhard Lloyd bar :Bernhard text :Bernhard Lloyd
bar:Frank text:Frank Mertens bar :Frank text :Frank Mertens
bar:Ricky text:Ricky Echolette bar :Ricky text :Ricky Echolette
bar:Martin text:Martin Lister bar :Martin text :Martin Lister
bar:Carsten text:Carsten Brocker bar :Carsten text :Carsten Brocker
bar:David text:David Goodes bar :David text :David Goodes
bar:Maja text:Maja Kim bar :Maja text :Maja Kim
bar:Alex text:Alexandra Merl bar :Alex text :Alexandra Merl
bar:Robbie text:Robbie France bar :Robbie text :Robbie France
bar:Jakob text:Jakob Kiersch bar :Jakob text :Jakob Kiersch

PlotData=
width:11 textcolor:black align:left anchor:from shift:(10,-4) width :11 textcolor :black align :left anchor :from shift :(10,-4)
bar:Marian"""
    
    whitespace_analyzer = WhitespaceAnalyzer()
    issues = whitespace_analyzer.analyze(graph_content)
    
    print(f'Nombre d issues: {len(issues)}')
    for i, issue in enumerate(issues):
        print(f'Issue {i+1}: {issue.description}')
        print(f'  Original: {issue.original_text}')
        print(f'  Suggested: {issue.suggested_text}')
    
    # Vérifier qu'aucune issue n'est détectée dans la syntaxe de graphique
    assert len(issues) == 0, f"WhitespaceAnalyzer ne devrait pas modifier la syntaxe de graphique, mais a trouvé {len(issues)} issues"
    
    print("Step 1 - WhitespaceAnalyzer graph protection: OK")


def test_normal_whitespace_still_detected():
    """Test que les problèmes d'espaces normaux sont toujours détectés"""
    
    normal_content = "Ceci  est  un  test avec  espaces  doubles"
    
    whitespace_analyzer = WhitespaceAnalyzer()
    issues = whitespace_analyzer.analyze(normal_content)
    
    # Les espaces doubles doivent être détectés
    assert len(issues) > 0, "Les espaces doubles normaux doivent être détectés"
    
    print("Step 2 - Normal whitespace still detected: OK")


if __name__ == "__main__":
    print("=" * 60)
    print("WHITESPACE GRAPH PROTECTION TESTS")
    print("=" * 60)
    print()
    
    test_graph_whitespace_protection()
    test_normal_whitespace_still_detected()
    
    print()
    print("=" * 60)
    print("ALL WHITESPACE GRAPH PROTECTION TESTS PASSED")
    print("=" * 60)
