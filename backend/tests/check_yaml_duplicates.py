"""
Script to check for duplicates in case_normalization_data.yaml.
Checks for:
1. Duplicate domain entries
2. Duplicate site names (same site name for different domains)
3. Domain formatting issues
"""

import yaml
from pathlib import Path
from collections import defaultdict

def check_yaml_duplicates():
    """Check YAML file for duplicates and inconsistencies."""
    
    yaml_path = Path(__file__).parent.parent.parent / "config" / "case_normalization_data.yaml"
    
    print(f"Loading YAML from: {yaml_path}")
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    if 'domain_to_site_name' not in data:
        print("No domain_to_site_name section found")
        return
    
    domain_mappings = data['domain_to_site_name']
    print(f"\nTotal domain entries: {len(domain_mappings)}")
    
    # Check for exact duplicate domains
    domain_counts = defaultdict(list)
    for domain, site_name in domain_mappings.items():
        domain_counts[domain].append(site_name)
    
    exact_duplicates = {domain: sites for domain, sites in domain_counts.items() if len(sites) > 1}
    
    if exact_duplicates:
        print(f"\n⚠️  Found {len(exact_duplicates)} exact duplicate domains:")
        for domain, sites in exact_duplicates.items():
            print(f"  {domain}: {len(sites)} entries")
            for site in sites:
                print(f"    - {site}")
    else:
        print(f"\n✓ No exact duplicate domains found")
    
    # Check for duplicate site names (same site name for different domains)
    site_to_domains = defaultdict(list)
    for domain, site_name in domain_mappings.items():
        # Extract the actual site name from the list format
        if isinstance(site_name, list) and len(site_name) > 0:
            actual_site = site_name[0]
            if isinstance(actual_site, list) and len(actual_site) > 0:
                actual_site = actual_site[0]
        else:
            actual_site = str(site_name)
        
        site_to_domains[actual_site].append(domain)
    
    duplicate_sites = {site: domains for site, domains in site_to_domains.items() if len(domains) > 1}
    
    if duplicate_sites:
        print(f"\n⚠️  Found {len(duplicate_sites)} site names used for multiple domains:")
        for site, domains in sorted(duplicate_sites.items()):
            print(f"  {site}: {len(domains)} domains")
            for domain in domains:
                print(f"    - {domain}")
    else:
        print(f"\n✓ No duplicate site names found")
    
    # Check for www/non-www pairs (these are expected but can be reported)
    www_pairs = []
    for domain in domain_mappings.keys():
        if domain.startswith('www.'):
            non_www = domain[4:]
            if non_www in domain_mappings:
                www_pairs.append((domain, non_www))
    
    if www_pairs:
        print(f"\nℹ️  Found {len(www_pairs)} www/non-www pairs (expected):")
        for www, non_www in www_pairs[:10]:  # Show first 10
            print(f"  {www} ↔ {non_www}")
        if len(www_pairs) > 10:
            print(f"  ... and {len(www_pairs) - 10} more")
    
    # Check for potential formatting issues
    formatting_issues = []
    for domain, site_name in domain_mappings.items():
        # Check if domain has spaces
        if ' ' in domain:
            formatting_issues.append(f"Domain '{domain}' contains spaces")
        
        # Check if site name is empty
        if not site_name:
            formatting_issues.append(f"Domain '{domain}' has empty site name")
    
    if formatting_issues:
        print(f"\n⚠️  Found {len(formatting_issues)} formatting issues:")
        for issue in formatting_issues:
            print(f"  - {issue}")
    else:
        print(f"\n✓ No formatting issues found")
    
    # Summary
    print(f"\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total domains: {len(domain_mappings)}")
    print(f"Exact duplicates: {len(exact_duplicates)}")
    print(f"Duplicate site names: {len(duplicate_sites)}")
    print(f"www/non-www pairs: {len(www_pairs)}")
    print(f"Formatting issues: {len(formatting_issues)}")
    
    if not exact_duplicates and not duplicate_sites and not formatting_issues:
        print(f"\n✓ YAML file is clean - no issues found")
    else:
        print(f"\n⚠️  YAML file has issues that should be reviewed")

if __name__ == "__main__":
    check_yaml_duplicates()
