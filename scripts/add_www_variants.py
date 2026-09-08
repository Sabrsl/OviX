"""
Script pour ajouter les variantes www aux domaines qui ne l'ont pas
dans le fichier case_normalization_data.yaml.
"""

import yaml
from pathlib import Path
import sys
import io
import copy

# Forcer l'encodage UTF-8 pour la sortie console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def add_www_variants():
    """
    Ajoute les variantes www aux domaines qui ne l'ont pas dans case_normalization_data.yaml.
    """
    # Chemin du fichier case_normalization_data.yaml
    yaml_file = Path(__file__).parent.parent / "config" / "case_normalization_data.yaml"
    
    if not yaml_file.exists():
        print(f"Erreur: Fichier non trouvé: {yaml_file}")
        return False
    
    # Lire le fichier YAML avec le loader standard pour éviter les problèmes d'ancres
    print(f"Lecture du fichier: {yaml_file}")
    with open(yaml_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    # Forcer la copie profonde des données pour éviter les références partagées
    data = copy.deepcopy(data)
    
    if 'domain_to_site_name' not in data or data['domain_to_site_name'] is None:
        print("Erreur: section 'domain_to_site_name' non trouvée dans le fichier")
        return False
    
    domain_to_site_name = data['domain_to_site_name']
    original_count = len(domain_to_site_name)
    added_count = 0
    
    # Pour chaque domaine, ajouter la variante www si elle n'existe pas
    for domain, site_name in list(domain_to_site_name.items()):
        # Vérifier si le domaine commence déjà par www.
        if domain.startswith('www.'):
            # Si c'est www., ajouter la variante sans www si elle n'existe pas
            non_www_variant = domain[4:]  # Retirer www.
            if non_www_variant not in domain_to_site_name:
                domain_to_site_name[non_www_variant] = site_name
                added_count += 1
                print(f"Ajouté: {non_www_variant} -> {site_name}")
        else:
            # Si ce n'est pas www., ajouter la variante www si elle n'existe pas
            www_variant = f"www.{domain}"
            if www_variant not in domain_to_site_name:
                domain_to_site_name[www_variant] = site_name
                added_count += 1
                print(f"Ajouté: {www_variant} -> {site_name}")
    
    if added_count == 0:
        print("Aucune variante www à ajouter (toutes existent déjà)")
        return True
    
    # Écrire le fichier modifié
    print(f"\nÉcriture du fichier modifié: {yaml_file}")
    print(f"Domaines originaux: {original_count}")
    print(f"Domaines ajoutés: {added_count}")
    print(f"Total après modification: {len(domain_to_site_name)}")
    
    # Sauvegarde de l'original
    backup_file = yaml_file.with_suffix('.yaml.backup')
    with open(backup_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=None, indent=2)
    print(f"Sauvegarde créée: {backup_file}")
    
    # Écriture du fichier modifié sans optimisation d'ancres/aliases
    # Utilisation explicite de SafeDumper avec désactivation des aliases
    class NoAliasSafeDumper(yaml.SafeDumper):
        """Dumper YAML qui ne crée pas d'ancres/aliases"""
        def ignore_aliases(self, data):
            return True
    
    with open(yaml_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=None, indent=2, Dumper=NoAliasSafeDumper)
    
    print(f"Fichier modifié avec succès: {yaml_file}")
    return True

if __name__ == "__main__":
    print("=== Script d'ajout de variantes www ===\n")
    success = add_www_variants()
    if success:
        print("\n=== Terminé avec succès ===")
        sys.exit(0)
    else:
        print("\n=== Erreur ===")
        sys.exit(1)