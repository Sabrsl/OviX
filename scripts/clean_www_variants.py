"""
Script pour nettoyer les variantes www du fichier case_normalization_data.yaml

Ce script:
1. Supprime les variantes www quand la version sans www existe déjà
2. Normalise les domaines www quand seule la version www existe (renomme en sans www)
3. Garde les données cohérentes
"""

import yaml
from pathlib import Path
import sys
import io
import copy

# Forcer l'encodage UTF-8 pour la sortie console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def clean_www_variants():
    """
    Nettoie les variantes www du fichier case_normalization_data.yaml.
    """
    # Chemin du fichier
    yaml_file = Path(__file__).parent.parent / "config" / "case_normalization_data.yaml"
    
    if not yaml_file.exists():
        print(f"Erreur: Fichier non trouvé: {yaml_file}")
        return False
    
    # Lire le fichier YAML
    print(f"Lecture du fichier: {yaml_file}")
    with open(yaml_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    # Forcer la copie profonde des données
    data = copy.deepcopy(data)
    
    if 'domain_to_site_name' not in data or data['domain_to_site_name'] is None:
        print("Erreur: section 'domain_to_site_name' non trouvée dans le fichier")
        return False
    
    domain_to_site_name = data['domain_to_site_name']
    original_count = len(domain_to_site_name)
    
    # Compteurs
    removed_count = 0  # Variantes www supprimées (version sans www existe)
    normalized_count = 0  # Domaines www normalisés (seule version www existe)
    kept_count = 0  # Domaines www gardés (cas rares ou spécifiques)
    
    # Liste des domaines à supprimer
    domains_to_remove = []
    # Liste des domaines à renommer (www.domain -> domain)
    domains_to_rename = {}
    
    # Analyser tous les domaines
    for domain in list(domain_to_site_name.keys()):
        if domain.startswith('www.'):
            domain_without_www = domain[4:]  # Retirer www.
            
            if domain_without_www in domain_to_site_name:
                # La version sans www existe déjà, supprimer la variante www
                domains_to_remove.append(domain)
                print(f"À supprimer: {domain} (version sans www existe: {domain_without_www})")
                removed_count += 1
            else:
                # Seule la version www existe, normaliser (renommer)
                domains_to_rename[domain] = domain_without_www
                print(f"À normaliser: {domain} -> {domain_without_www}")
                normalized_count += 1
        else:
            # Domaine sans www, on le garde
            kept_count += 1
    
    # Supprimer les variantes www inutiles
    for domain in domains_to_remove:
        del domain_to_site_name[domain]
    
    # Normaliser les domaines www (renommer)
    for old_domain, new_domain in domains_to_rename.items():
        site_name = domain_to_site_name[old_domain]
        del domain_to_site_name[old_domain]
        domain_to_site_name[new_domain] = site_name
    
    if removed_count == 0 and normalized_count == 0:
        print(f"\nAucun changement nécessaire (domaines sans www: {kept_count})")
        return True
    
    # Écrire le fichier modifié
    print(f"\nÉcriture du fichier modifié: {yaml_file}")
    print(f"Domaines originaux: {original_count}")
    print(f"Variantes www supprimées: {removed_count}")
    print(f"Domaines www normalisés: {normalized_count}")
    print(f"Domaines sans www gardés: {kept_count}")
    print(f"Total après nettoyage: {len(domain_to_site_name)}")
    
    # Sauvegarde de l'original
    backup_file = yaml_file.with_suffix('.yaml.www_cleanup_backup')
    with open(backup_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=None, indent=2)
    print(f"Sauvegarde créée: {backup_file}")
    
    # Écriture du fichier modifié sans optimisation d'ancres/aliases
    class NoAliasSafeDumper(yaml.SafeDumper):
        """Dumper YAML qui ne crée pas d'ancres/aliases"""
        def ignore_aliases(self, data):
            return True
    
    with open(yaml_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=None, indent=2, Dumper=NoAliasSafeDumper)
    
    print(f"Fichier modifié avec succès: {yaml_file}")
    return True

if __name__ == "__main__":
    print("=== Script de nettoyage des variantes www ===\n")
    success = clean_www_variants()
    if success:
        print("\n=== Terminé avec succès ===")
        sys.exit(0)
    else:
        print("\n=== Erreur ===")
        sys.exit(1)