from src.wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper

# Test the improved _resolve_site_display_name method
helper = ReferenceTemplateHelper()

# Test cases
test_cases = [
    ('lapresse.ca', '[[La Presse]]'),  # Should map to [[La Presse]]
    ('www.lapresse.ca', '[[La Presse]]'),  # Should map to [[La Presse]] (remove www)
    ('lemonde.fr', '[[Le Monde]]'),  # Should map to [[Le Monde]]
    ('unknown-site.com', 'unknown-site.com'),  # Should return as-is (no mapping)
    ('Le Monde', 'Le Monde'),  # Should return as-is (not a domain)
    ('[[Le Monde]]', '[[Le Monde]]'),  # Should return as-is (already wikilink)
]

print('Testing _resolve_site_display_name improvements:')
for input_val, expected in test_cases:
    result = helper._resolve_site_display_name(input_val)
    status = 'PASS' if result == expected else 'FAIL'
    print(f'{status} Input: {input_val!r} -> Expected: {expected!r}, Got: {result!r}')
