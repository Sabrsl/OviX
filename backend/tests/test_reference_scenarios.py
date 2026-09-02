"""
Test script for 15 reference format scenarios
Tests DeadLinkAnalyzer behavior on various wikitext reference formats
"""

import sys
sys.path.insert(0, 'src')

from wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper
from wikipedia_maintenance.utils.corrector import Corrector

# Test scenarios
SCENARIOS = [
    {
        "id": 1,
        "name": "Bare URL simple dans <ref>",
        "wikitext": "<ref>http://exemple-mort.fr/page-article</ref>",
        "expected": "Should detect dead link and suggest {{Lien web}} with archive"
    },
    {
        "id": 2,
        "name": "Bare URL dans liste Liens externes",
        "wikitext": """== Liens externes ==
* http://vieux-site.org/ressource (consulté le 3 janvier 2015)""",
        "expected": "Should detect dead link in external links section"
    },
    {
        "id": 3,
        "name": "Template {{Lien web}} classique",
        "wikitext": "<ref>{{Lien web |langue=fr |titre=Titre de l'article |url=http://exemple-mort.fr/page |site=exemple-mort.fr |auteur=Jean Dupont |date=12 mars 2010}}</ref>",
        "expected": "Should repair with archive parameters"
    },
    {
        "id": 4,
        "name": "{{Lien web}} avec archive déjà présente et valide",
        "wikitext": "<ref>{{Lien web |titre=Article existant |url=http://site-mort.com/x |site=site-mort.com |archive-url=https://web.archive.org/web/20180101000000/http://site-mort.com/x |archive-date=2018-01-01 |consulté le=15 avril 2019}}</ref>",
        "expected": "Should preserve existing valid archive"
    },
    {
        "id": 5,
        "name": "{{Lien web}} avec archive déjà présente mais morte",
        "wikitext": "<ref>{{Lien web |titre=Article X |url=http://site-mort.com/y |archive-url=https://web.archive.org/web/20050101000000/http://site-mort.com/y |archive-date=2005-01-01}}</ref>",
        "expected": "Should try to find newer archive"
    },
    {
        "id": 6,
        "name": "Template {{Lien brisé}}",
        "wikitext": "<ref>{{Lien brisé |url=http://ancien-domaine.fr/page |titre=Vieux titre |date=2011}}</ref>",
        "expected": "Should repair with archive"
    },
    {
        "id": 7,
        "name": "Template {{Article}} (référence académique)",
        "wikitext": "<ref>{{Article |langue=en |auteur=A. Smith |titre=Étude sur X |périodique=Journal of Science |vol.=12 |n°=3 |p.=45-60 |url=http://revue-morte.edu/doi/123 |année=2009}}</ref>",
        "expected": "Should repair with archive parameters"
    },
    {
        "id": 8,
        "name": "Template {{Ouvrage}} (pas de paramètre site)",
        "wikitext": "<ref>{{Ouvrage |auteur=Marie Curie |titre=Recherches sur les substances radioactives |éditeur=Gauthier-Villars |année=1904 |url=http://gallica-morte.fr/livre |ISBN=978-2-1234-5678-9}}</ref>",
        "expected": "Should NOT add site parameter (books don't have sites)"
    },
    {
        "id": 9,
        "name": "URL archive.org sans original apparié",
        "wikitext": "<ref>https://web.archive.org/web/20200101000000/http://site-disparu.net/page</ref>",
        "expected": "Should detect as archive URL and handle appropriately"
    },
    {
        "id": 10,
        "name": "Deux références au même lien mort (test dédup)",
        "wikitext": """<ref>http://doublon-mort.fr/page</ref>
... plus loin ...
<ref>http://doublon-mort.fr/page</ref>""",
        "expected": "Should detect duplicate and handle deduplication"
    },
    {
        "id": 11,
        "name": "Lien mort hors périmètre (ne doit PAS être traité)",
        "wikitext": """== Voir aussi ==
* [http://site-quelconque-mort.fr Un site externe]""",
        "expected": "Should NOT process (outside <ref> tags)"
    },
    {
        "id": 12,
        "name": "URL avec redirection valide mais contenu différent",
        "wikitext": "<ref>{{Lien web |titre=Ancien produit |url=http://boutique-fermee.com/produit-42 |site=boutique-fermee.com}}</ref>",
        "expected": "Should reject if content differs"
    },
    {
        "id": 13,
        "name": "{{Lien web}} avec série= ou collection= (site ne doit pas être auto-rempli)",
        "wikitext": "<ref>{{Lien web |titre=Épisode 4 |url=http://site-mort.tv/ep4 |série=Ma Série |saison=2}}</ref>",
        "expected": "Should NOT auto-fill site when série is present"
    },
    {
        "id": 14,
        "name": "Erreur DNS transitoire (ne doit pas être traité comme mort)",
        "wikitext": "<ref>{{Lien web |titre=Site temporairement inaccessible |url=http://domaine-timeout.fr/page |site=domaine-timeout.fr}}</ref>",
        "expected": "Should classify as REVIEW_REQUIRED or TEMPORARY_ERROR, not DEAD"
    },
    {
        "id": 15,
        "name": "Template non supporté / inconnu",
        "wikitext": "<ref>{{Cite web |title=English style ref |url=http://dead-english-site.com/x}}</ref>",
        "expected": "Should map to {{Lien web}} (mapped template)"
    }
]

def test_scenario(scenario):
    """Test a single scenario and return results"""
    print(f"\n{'='*80}")
    print(f"SCÉNARIO {scenario['id']}: {scenario['name']}")
    print(f"{'='*80}")
    print(f"Wikitext ORIGINAL:\n{scenario['wikitext']}")
    print(f"\nAttendu: {scenario['expected']}")
    print(f"\n{'-'*80}")
    
    try:
        analyzer = DeadLinkAnalyzer()
        issues = analyzer.analyze(scenario['wikitext'])
        
        if not issues:
            print("✅ STATUT: AUCUN PROBLÈME DÉTECTÉ")
            print("   Aucun lien mort ou problème détecté dans ce scénario.")
            print(f"\nWikitext CORRIGÉ: (inchangé)")
            print(f"{scenario['wikitext']}")
            return {"status": "no_issues", "count": 0, "corrected": scenario['wikitext']}
        
        print(f"✅ STATUT: {len(issues)} PROBLÈME(S) DÉTECTÉ(S)")
        
        for i, issue in enumerate(issues, 1):
            print(f"\n   Problème {i}:")
            print(f"   - Type: {issue.issue_type}")
            print(f"   - Description: {issue.description}")
            print(f"   - Sévérité: {issue.severity}")
            print(f"   - Position: {issue.position}")
            
            if issue.original_text:
                print(f"   - Original: {issue.original_text[:100]}...")
            
            if issue.suggested_text:
                print(f"   - Suggestion: {issue.suggested_text[:100]}...")
            
            if issue.extra:
                print(f"   - Extra: {issue.extra}")
        
        # Apply corrections
        corrector = Corrector(scenario['wikitext'])
        corrected_content = corrector.apply_corrections(issues)
        
        print(f"\n{'-'*80}")
        print(f"Wikitext CORRIGÉ:")
        print(f"{corrected_content}")
        
        return {"status": "issues_found", "count": len(issues), "issues": issues, "corrected": corrected_content}
        
    except Exception as e:
        print(f"❌ STATUT: ERREUR")
        print(f"   Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

def main():
    """Run all test scenarios"""
    print("="*80)
    print("TEST DES 15 SCÉNARIOS DE RÉFÉRENCE WIKITEXT")
    print("="*80)
    
    results = []
    
    for scenario in SCENARIOS:
        result = test_scenario(scenario)
        results.append({
            "id": scenario['id'],
            "name": scenario['name'],
            "result": result
        })
    
    # Summary
    print(f"\n\n{'='*80}")
    print("RÉSUMÉ DES TESTS")
    print(f"{'='*80}")
    
    for r in results:
        status_symbol = "✅" if r['result']['status'] in ['no_issues', 'issues_found'] else "❌"
        status_text = r['result']['status'].upper()
        count = r['result'].get('count', 0)
        print(f"{status_symbol} Scénario {r['id']}: {status_text} ({count} problème(s)) - {r['name']}")
    
    total = len(results)
    errors = sum(1 for r in results if r['result']['status'] == 'error')
    print(f"\nTotal: {total} scénarios testés, {errors} erreur(s)")

if __name__ == "__main__":
    main()
