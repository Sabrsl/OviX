"""Test Unicode URL matching fix."""

import re

# Old pattern (ASCII-only)
OLD_PATTERN = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=%]+', re.IGNORECASE)

# New pattern (with Unicode support)
NEW_PATTERN = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=%\u0080-\uFFFF]+', re.IGNORECASE)

test_urls = [
    'https://www.mük.hu/',
    'https://diuf.unifr.ch/pai/people/juillera/Sudoku/Sudoku.html',
    'https://www.example.com/',
    'https://www.fürst.de/',
    'https://www.école.fr/',
]

print("Testing URL pattern matching with Unicode characters:\n")

for url in test_urls:
    old_match = OLD_PATTERN.fullmatch(url)
    new_match = NEW_PATTERN.fullmatch(url)
    
    print(f"URL: {url}")
    print(f"  Old pattern: {'✓ MATCH' if old_match else '✗ NO MATCH'}")
    print(f"  New pattern: {'✓ MATCH' if new_match else '✗ NO MATCH'}")
    print()

# Test the specific case from the bug report
template_content = '{{Lien web|titre="Magyar Ügyvédi Kamara". Magyar Ügyvédi Kamara|url=https://www.mük.hu/}}'
print(f"Template content: {template_content}")
print(f"Old pattern finds: {OLD_PATTERN.findall(template_content)}")
print(f"New pattern finds: {NEW_PATTERN.findall(template_content)}")
