"""
Test script to verify bare URL enrichment for bracketed URLs [url text]
"""

import re

# Pattern from ReferenceEnricherAnalyzer
BRACKETED_URL_PATTERN = re.compile(r'\[https?://[^\]]+\]')

# Test content from the article
content = """Originaire de [[Mayagüez]], Lugo a obtenu un baccalauréat et une maîtrise en biologie, tous deux de l'[[Université de Porto Rico]]. Il a ensuite obtenu un doctorat en écologie de l'[[Université de Caroline du Nord]] à Chapel Hill<ref name=":1" />{{,}}<ref name="SF">{{Lien web |auteur=Lugo |prénom=Ariel E. |titre=Using Research for Sustainability in the Neotropics |url=http://www.fs.fed.us/sustained/special-feature-summer-2006-lugo.html |série=Sustainable Development e-News |éditeur=[[United States Forest Service]] |date=July 19, 2006}}</ref>{{,}}<ref name="FS">[https://www.fs.fed.us/research/people/profile.php?alias=alugo Forest Service]</ref>{{,}}<ref name="PAL">[https://sustainability.asu.edu/person/ariel-lugo/ Arizona State University]</ref>{{,}}<ref name="ATB">[http://tropicalbiology.org/ariel-lugo/ Association name="ATB">{{Lien web|titre=Association for Tropical Biology and Conservation ]</ref>. Conservation|url=http://tropicalbiology.org/ariel-lugo/|site=tropicalbiology.org|consulté le=2026-08-31}}</ref>."""

print("Testing BRACKETED_URL_PATTERN detection:")
print("=" * 80)

matches = list(BRACKETED_URL_PATTERN.finditer(content))
print(f"Found {len(matches)} bracketed URLs")

for i, match in enumerate(matches, 1):
    bracketed_content = match.group(0)
    print(f"\nMatch {i}:")
    print(f"  Position: {match.start()}-{match.end()}")
    print(f"  Content: {bracketed_content}")
    
    # Extract the URL from the bracketed content
    url_match = re.search(r'(https?://[^\s\]]+)', bracketed_content)
    if url_match:
        url = url_match.group(1)
        print(f"  Extracted URL: {url}")
        
        # Extract the text after the URL (excluding the closing ])
        url_end = url_match.end()
        # Find the closing bracket position within the bracketed content
        closing_bracket_pos = bracketed_content.find(']', url_end)
        if closing_bracket_pos != -1:
            text_after = bracketed_content[url_end:closing_bracket_pos].strip()
            if text_after:
                print(f"  Text after URL (cleaned): {text_after}")
            else:
                print(f"  No text after URL (just the URL in brackets)")
        else:
            print(f"  No closing bracket found (malformed)")

print("\n" + "=" * 80)
print("Test completed")
