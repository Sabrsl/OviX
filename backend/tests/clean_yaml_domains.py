"""
Script to clean case_normalization_data.yaml by removing www. duplicates.
Keeps only the non-www variant of each domain to avoid redundancy.
"""

import yaml
from pathlib import Path
from collections import defaultdict

def clean_yaml_domains():
    """Clean YAML file by removing www. duplicates, keeping only non-www variants."""
    
    yaml_path = Path(__file__).parent.parent.parent / "config" / "case_normalization_data.yaml"
    
    print(f"Loading YAML from: {yaml_path}")
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    if 'domain_to_site_name' not in data:
        print("No domain_to_site_name section found")
        return
    
    domain_mappings = data['domain_to_site_name']
    print(f"Original: {len(domain_mappings)} domain entries")
    
    # Track conflicts where www and non-www have different site names
    conflicts = []
    
    # Build cleaned mapping with only non-www variants
    cleaned_mappings = {}
    for domain, site_name in domain_mappings.items():
        # Normalize to non-www
        normalized_domain = domain[4:] if domain.startswith('www.') else domain
        
        if normalized_domain in cleaned_mappings:
            # Check if there's a conflict
            existing = cleaned_mappings[normalized_domain]
            if existing != site_name:
                conflicts.append({
                    'domain': domain,
                    'normalized': normalized_domain,
                    'existing': existing,
                    'new': site_name
                })
                # Keep the first one encountered (arbitrary but consistent)
        else:
            cleaned_mappings[normalized_domain] = site_name
    
    # Report conflicts
    if conflicts:
        print(f"\n⚠️  Found {len(conflicts)} conflicts (www/non-www with different site names):")
        for conflict in conflicts:
            print(f"  {conflict['domain']} -> {conflict['new']} vs {conflict['normalized']} -> {conflict['existing']}")
        print("  Keeping first encountered value for each normalized domain")
    
    # Update data
    data['domain_to_site_name'] = cleaned_mappings
    
    # Write back
    print(f"\nWriting cleaned YAML with {len(cleaned_mappings)} domain entries")
    
    # Atomic write
    temp_path = yaml_path.with_suffix('.yaml.tmp')
    with open(temp_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    # Replace original
    temp_path.replace(yaml_path)
    
    print(f"✓ Successfully cleaned YAML file")
    print(f"  Removed {len(domain_mappings) - len(cleaned_mappings)} duplicate entries")

if __name__ == "__main__":
    clean_yaml_domains()
