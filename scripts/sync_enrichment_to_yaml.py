"""
Script pour synchroniser les résultats d'enrichissement avec case_normalization_data.yaml

Ce script:
1. Lit les résultats d'enrichissement depuis data/domain_enrichment_results.json
2. Lit le fichier case_normalization_data.yaml existant
3. Compare les domaines et détecte ceux qui manquent dans le YAML
4. Ajoute les domaines manquants au fichier YAML
"""

import yaml
import json
from pathlib import Path
import sys
import io
import copy

# Forcer l'encodage UTF-8 pour la sortie console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def normalize_site_name(site_name):
    """
    Normalise le nom du site en gérant les différents formats.
    """
    if isinstance(site_name, list):
        # Gérer le format de liste imbriquée [['Site Name']]
        while isinstance(site_name, list) and len(site_name) > 0:
            site_name = site_name[0]
        return str(site_name) if site_name else ""
    return str(site_name) if site_name else ""

def sync_enrichment_to_yaml():
    """
    Synchronise les résultats d'enrichissement avec case_normalization_data.yaml.
    """
    # Chemins des fichiers
    yaml_file = Path(__file__).parent.parent / "config" / "case_normalization_data.yaml"
    json_file = Path(__file__).parent.parent / "data" / "domain_enrichment_results.json"
    
    # Vérifier que les fichiers existent
    if not yaml_file.exists():
        print(f"Erreur: Fichier YAML non trouvé: {yaml_file}")
        return False
    
    if not json_file.exists():
        print(f"Erreur: Fichier JSON non trouvé: {json_file}")
        return False
    
    # Lire le fichier JSON d'enrichissement
    print(f"Lecture du fichier JSON: {json_file}")
    with open(json_file, 'r', encoding='utf-8') as f:
        enrichment_data = json.load(f)
    
    entries = enrichment_data.get('entries', [])
    print(f"Nombre d'entrées d'enrichissement: {len(entries)}")
    
    # Lire le fichier YAML
    print(f"Lecture du fichier YAML: {yaml_file}")
    with open(yaml_file, 'r', encoding='utf-8') as f:
        yaml_data = yaml.safe_load(f) or {}
    
    # Forcer la copie profonde des données
    yaml_data = copy.deepcopy(yaml_data)
    
    if 'domain_to_site_name' not in yaml_data or yaml_data['domain_to_site_name'] is None:
        print("Erreur: section 'domain_to_site_name' non trouvée dans le fichier YAML")
        return False
    
    domain_to_site_name = yaml_data['domain_to_site_name']
    original_count = len(domain_to_site_name)
    
    # Normaliser les domaines existants pour comparaison
    existing_domains = set()
    for domain in domain_to_site_name.keys():
        existing_domains.add(domain.lower())
    
    # Compteurs
    added_count = 0
    already_present_count = 0
    conflict_count = 0
    
    # Traiter chaque entrée d'enrichissement
    for entry in entries:
        domain = entry.get('domain')
        site_name = entry.get('site_name')
        status = entry.get('status')
        
        if not domain or not site_name:
            continue
        
        # Normaliser le domaine pour comparaison
        domain_lower = domain.lower()
        
        # Vérifier si le domaine existe déjà
        if domain_lower in existing_domains:
            already_present_count += 1
            print(f"Déjà présent: {domain} -> {site_name}")
            continue
        
        # Vérifier les variantes www
        www_variant = f"www.{domain_lower}" if not domain_lower.startswith('www.') else domain_lower[4:]
        if www_variant in existing_domains:
            already_present_count += 1
            print(f"Déjà présent (variante www): {domain} -> {site_name}")
            continue
        
        # Ajouter le domaine manquant
        domain_to_site_name[domain] = [[site_name]]
        existing_domains.add(domain_lower)
        added_count += 1
        print(f"Ajouté: {domain} -> {site_name}")
    
    if added_count == 0:
        print(f"\nAucun domaine à ajouter (déjà présents: {already_present_count})")
        return True
    
    # Écrire le fichier modifié
    print(f"\nÉcriture du fichier modifié: {yaml_file}")
    print(f"Domaines originaux: {original_count}")
    print(f"Domaines ajoutés: {added_count}")
    print(f"Déjà présents: {already_present_count}")
    print(f"Total après modification: {len(domain_to_site_name)}")
    
    # Sauvegarde de l'original
    backup_file = yaml_file.with_suffix('.yaml.enrichment_backup')
    with open(backup_file, 'w', encoding='utf-8') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=None, indent=2)
    print(f"Sauvegarde créée: {backup_file}")
    
    # Écriture du fichier modifié sans optimisation d'ancres/aliases
    class NoAliasSafeDumper(yaml.SafeDumper):
        """Dumper YAML qui ne crée pas d'ancres/aliases"""
        def ignore_aliases(self, data):
            return True
    
    with open(yaml_file, 'w', encoding='utf-8') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=None, indent=2, Dumper=NoAliasSafeDumper)
    
    print(f"Fichier modifié avec succès: {yaml_file}")
    return True

if __name__ == "__main__":
    print("=== Script de synchronisation d'enrichissement ===\n")
    success = sync_enrichment_to_yaml()
    if success:
        print("\n=== Terminé avec succès ===")
        sys.exit(0)
    else:
        print("\n=== Erreur ===")
        sys.exit(1)