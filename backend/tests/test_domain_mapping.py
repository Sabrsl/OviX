"""
Test pour vérifier le fonctionnement des liens internes et du mapping domaine_to_site_name
"""
import sys
import io
sys.path.insert(0, r'C:\Users\badza\Desktop\Sabrsl_dead_linker_Bot\src')

# Forcer l'encodage UTF-8 pour la sortie console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from wikipedia_maintenance.utils.edit_summaries import get_summary_from_issues, _detect_enrichment_mapping, _detect_dead_link_mapping
from wikipedia_maintenance.utils.config import load_config

# Créer des issues factices pour les tests
def create_issue(issue_type):
    return type('Issue', (), {'issue_type': issue_type, 'suggested_text': 'correction'})()

print("=== Test 1: Vérification du mapping domaine_to_site_name ===")
try:
    import yaml
    from pathlib import Path
    
    yaml_file = Path(r'C:\Users\badza\Desktop\Sabrsl_dead_linker_Bot\config\case_normalization_data.yaml')
    with open(yaml_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    domain_mapping = data.get('domain_to_site_name', {})
    print(f"Nombre de domaines dans le mapping: {len(domain_mapping)}")
    
    # Vérifier quelques domaines connus
    test_domains = ['apple.com', 'bbc.com', 'wikipedia.org', 'spotify.com']
    for domain in test_domains:
        if domain in domain_mapping:
            site_name = domain_mapping[domain]
            print(f"✓ {domain} → {site_name}")
        else:
            print(f"✗ {domain} non trouvé dans le mapping")
except Exception as e:
    print(f"Erreur lors du chargement du mapping: {e}")

print("\n=== Test 2: Détection d'enrichissements avec liens internes ===")

# Simuler un contenu original et corrigé avec enrichissement
original_content = """
{{Article|url=https://www.lemonde.fr/planete/article/2024/01/15/climat/|titre=Le climat en 2024}}
"""

corrected_content = """
{{Article|url=https://www.lemonde.fr/planete/article/2024/01/15/climat/|titre=Le climat en 2024|site=[[Le Monde]]|consulté le=2024-02-20}}
"""

enrichment_mapping, total_count = _detect_enrichment_mapping(original_content, corrected_content)
print(f"Enrichissements détectés: {enrichment_mapping}")
print(f"Total: {total_count}")

# Vérifier si le lien interne est détecté
has_internal_link = any("[[" in entry for entry in enrichment_mapping)
print(f"Contient des liens internes: {has_internal_link}")

print("\n=== Test 3: Enrichissement avec domaine mapping ===")

# Simuler un cas où le domaine est dans le mapping
original_content2 = """
{{Article|url=https://bbc.com/news/world|titre=World News}}
"""

corrected_content2 = """
{{Article|url=https://bbc.com/news/world|titre=World News|site=[[BBC]]|consulté le=2024-02-20}}
"""

enrichment_mapping2, total_count2 = _detect_enrichment_mapping(original_content2, corrected_content2)
print(f"Enrichissements détectés: {enrichment_mapping2}")
print(f"Total: {total_count2}")

print("\n=== Test 4: Résumé d'édition avec enrichissements ===")

# Créer des issues d'enrichissement
issues_enrichment = [create_issue('reference_enrichment')]
summary = get_summary_from_issues(issues_enrichment, original_content2, corrected_content2)
print(f"Résumé: {summary}")

print("\n=== Test 5: Détection de liens morts avec mapping ===")

# Simuler un contenu avec lien mort remplacé par archive
original_content_dead = """
{{Article|url=https://www.lemonde.fr/planete/article/2020/01/15/climat/|titre=Le climat en 2020}}
"""

corrected_content_dead = """
{{Article|url=https://web.archive.org/web/20240115123456/https://www.lemonde.fr/planete/article/2020/01/15/climat/|titre=Le climat en 2020}}
"""

from wikipedia_maintenance.utils.edit_summaries import _detect_dead_link_mapping
dead_link_mapping, dead_total = _detect_dead_link_mapping(original_content_dead, corrected_content_dead)
print(f"Liens morts détectés: {dead_link_mapping}")
print(f"Total: {dead_total}")

print("\n=== Test 6: Résumé d'édition avec liens morts ===")

# Créer des issues de liens morts
issues_dead = [create_issue('dead_link'), create_issue('dead_link')]
summary_dead = get_summary_from_issues(issues_dead, original_content_dead, corrected_content_dead)
print(f"Résumé: {summary_dead}")

print("\n=== Test 7: Résumé d'édition combiné (liens morts + enrichissements) ===")

# Créer des issues combinées
issues_combined = [create_issue('dead_link'), create_issue('dead_link'), create_issue('reference_enrichment')]
summary_combined = get_summary_from_issues(issues_combined, original_content_dead, corrected_content2)
print(f"Résumé: {summary_combined}")

print("\n=== Test 8: Vérification des variantes www dans le mapping ===")

# Vérifier que les variantes www sont présentes
www_variants = ['www.apple.com', 'www.bbc.com', 'www.wikipedia.org', 'www.spotify.com']
for domain in www_variants:
    if domain in domain_mapping:
        site_name = domain_mapping[domain]
        print(f"✓ {domain} → {site_name}")
    else:
        print(f"✗ {domain} non trouvé dans le mapping")

print("\n=== Tests terminés ===")