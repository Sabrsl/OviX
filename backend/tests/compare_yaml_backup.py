"""
Script to compare backup YAML with current YAML to find lost www domains.
Identifies www domains that were removed but don't have a non-www variant in the current file.
"""

import yaml
from pathlib import Path

def compare_yaml_files():
    """Compare backup and current YAML files to find lost www domains."""
    
    backup_path = Path(__file__).parent.parent.parent / "config" / "case_normalization_data.yaml.backup"
    current_path = Path(__file__).parent.parent.parent / "config" / "case_normalization_data.yaml"
    
    print(f"Loading backup from: {backup_path}")
    print(f"Loading current from: {current_path}")
    
    with open(backup_path, 'r', encoding='utf-8') as f:
        backup_data = yaml.safe_load(f) or {}
    
    with open(current_path, 'r', encoding='utf-8') as f:
        current_data = yaml.safe_load(f) or {}
    
    backup_domains = backup_data.get('domain_to_site_name', {})
    current_domains = current_data.get('domain_to_site_name', {})
    
    print(f"\nBackup: {len(backup_domains)} domain entries")
    print(f"Current: {len(current_domains)} domain entries")
    
    # Find www domains in backup that are not in current
    lost_www_domains = []
    for domain, site_name in backup_domains.items():
        if domain.startswith('www.'):
            # Check if this www domain is in current
            if domain not in current_domains:
                # Check if non-www variant exists in current
                non_www_variant = domain[4:]
                if non_www_variant not in current_domains:
                    lost_www_domains.append({
                        'domain': domain,
                        'site_name': site_name,
                        'non_www_variant': non_www_variant
                    })
    
    if lost_www_domains:
        print(f"\n⚠️  Found {len(lost_www_domains)} www domains that were removed without non-www variant:")
        for item in lost_www_domains:
            print(f"  {item['domain']} -> {item['site_name']}")
            print(f"    Non-www variant {item['non_www_variant']} not found in current file")
        
        # Ask if user wants to restore them
        print(f"\n💡 To restore these domains, you can add them back to the current YAML file")
    else:
        print(f"\n✓ No www domains were lost without their non-www variant")
    
    # Also check for domains that exist in both but with different site names
    conflicts = []
    for domain in set(backup_domains.keys()) & set(current_domains.keys()):
        backup_site = backup_domains[domain]
        current_site = current_domains[domain]
        if backup_site != current_site:
            conflicts.append({
                'domain': domain,
                'backup_site': backup_site,
                'current_site': current_site
            })
    
    if conflicts:
        print(f"\n⚠️  Found {len(conflicts)} domains with different site names:")
        for conflict in conflicts:
            print(f"  {conflict['domain']}:")
            print(f"    Backup: {conflict['backup_site']}")
            print(f"    Current: {conflict['current_site']}")
    else:
        print(f"\n✓ No conflicts found between backup and current")

if __name__ == "__main__":
    compare_yaml_files()
