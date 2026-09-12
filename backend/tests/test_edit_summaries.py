"""
Test pour vérifier les formats de résumés d'édition
"""
import sys
import io
sys.path.insert(0, r'C:\Users\badza\Desktop\Sabrsl_dead_linker_Bot\backend\src')

# Forcer l'encodage UTF-8 pour la sortie console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from wikipedia_maintenance.utils.edit_summaries import get_summary_from_issues

# Créer des issues factices pour les tests
def create_issue(issue_type):
    return type('Issue', (), {'issue_type': issue_type, 'suggested_text': 'correction'})()

# Test 1: Seulement enrichissements
print("=== Test 1: Seulement enrichissements ===")
issues_enrichment = [create_issue('reference_enrichment')]
summary1 = get_summary_from_issues(issues_enrichment, "", "")
print(f"Résultat: {summary1}")
print()

# Test 2: Seulement liens morts
print("=== Test 2: Seulement liens morts ===")
issues_dead_link = [create_issue('dead_link'), create_issue('dead_link')]
summary2 = get_summary_from_issues(issues_dead_link, "", "")
print(f"Résultat: {summary2}")
print()

# Test 3: Liens morts + enrichissements
print("=== Test 3: Liens morts + enrichissements ===")
issues_both = [create_issue('dead_link'), create_issue('dead_link'), create_issue('reference_enrichment')]
summary3 = get_summary_from_issues(issues_both, "", "")
print(f"Résultat: {summary3}")
print()

# Test 4: Liens morts + enrichissements + autres corrections
print("=== Test 4: Liens morts + enrichissements + autres corrections ===")
issues_mixed = [create_issue('dead_link'), create_issue('dead_link'), create_issue('reference_enrichment'), create_issue('http_link'), create_issue('http_link'), create_issue('http_link')]
summary4 = get_summary_from_issues(issues_mixed, "", "")
print(f"Résultat: {summary4}")
print()

print("=== Tests terminés ===")
