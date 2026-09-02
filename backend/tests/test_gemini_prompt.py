"""Test Gemini with the exact prompt used by CaseNormalizer."""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from wikipedia_maintenance.utils.gemini_client import GeminiClient

def test_gemini_with_case_normalizer_prompt():
    """Test Gemini with the exact prompt used by CaseNormalizer."""
    print("=" * 60)
    print("GEMINI WITH CASE NORMALIZER PROMPT TEST")
    print("=" * 60)
    
    # Initialize Gemini client
    client = GeminiClient()
    
    # Test values
    test_values = {"auteur": "Jean Dupont", "titre": "THE GREAT GATSBY"}
    values_json = json.dumps(test_values, ensure_ascii=False)
    
    # Exact prompt from CaseNormalizer
    prompt = f"""Tu es un module de normalisation pour les paramètres de modèles de référence Wikipédia.

Ta tâche UNIQUE est de normaliser la CASSE (majuscules/minuscules) des valeurs de paramètres
dans les modèles de référence Wikipédia ({{Lien web}}, {{Article}}, {{Ouvrage}}, {{Lien brisé}}).

PARAMÈTRES CIBLÉS (uniquement ceux-ci) :
- titre
- site
- éditeur
- auteur
- nom
- prénom

RÈGLES DE NORMALISATION CONSERVATRICES :
1. Conserver le sens original exactement
2. NE JAMAIS inventer d'information
3. NE JAMAIS ajouter d'information non présente dans l'entrée
4. NE JAMAIS supprimer une information simplement parce qu'elle semble inhabituelle
5. Appliquer les conventions typographiques françaises :
   - Noms propres : première lettre en majuscule, reste en minuscules (sauf exceptions connues)
   - Titres d'œuvres : première lettre en majuscule, reste en minuscules (sauf exceptions)
   - Noms d'institutions/entreprises : respecter la graphie officielle connue
6. Préserver les sigles et acronymes connus (ONU, USA, UNESCO, etc.)
7. NE JAMAIS modifier les URLs, identifiants, ou paramètres techniques
8. Si aucune normalisation n'est nécessaire, retourner les valeurs inchangées

INTERDICTIONS ABSOLUES :
- Ne modifier en aucun cas les URLs
- Ne modifier en aucun cas les références
- Ne modifier en aucun cas les catégories
- Ne modifier en aucun cas les liens Wikipédia
- Ne modifier en aucun cas le texte encyclopédique
- Ne modifier aucun autre paramètre de modèle
- Ne jamais ajouter ou supprimer des paramètres
- Ne jamais reformuler une phrase ou remplacer un mot par un synonyme

FORMAT DE RÉPONSE : JSON strict avec les champs suivants uniquement :
{{
  "titre": "valeur normalisée ou inchangée",
  "site": "valeur normalisée ou inchangée",
  "éditeur": "valeur normalisée ou inchangée",
  "auteur": "valeur normalisée ou inchangée",
  "nom": "valeur normalisée ou inchangée",
  "prénom": "valeur normalisée ou inchangée"
}}

Si un champ n'est pas présent dans les données d'entrée, ne l'inclus pas dans le JSON de sortie.
Ne retourne JAMAIS d'autres champs que ceux-ci.
Ne retourne JAMAIS de texte explicatif ou de commentaire.

=== VALEURS À NORMALISER (JSON) ===
{values_json}
=== FIN DES VALEURS ===

JSON normalisé :"""
    
    print(f"\nPrompt length: {len(prompt)} characters")
    print(f"Test values: {test_values}")
    
    # Call Gemini
    try:
        ok, nb_caracteres = client.verifier_longueur(prompt)
        print(f"Length check: {ok}, {nb_caracteres} characters")
        
        if ok:
            from wikipedia_maintenance.utils.verif_longueur import calculer_timeout
            timeout = calculer_timeout(nb_caracteres)
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 8192,
                }
            }
            
            response = client._appeler_api_avec_retry(payload, timeout)
            data = response.json()
            
            if "candidates" in data and len(data["candidates"]) > 0:
                text = data["candidates"][0]["content"]["parts"][0].get("text", "").strip()
                print(f"\nRaw response: {text}")
                
                # Try to parse as JSON
                try:
                    # Clean markdown if present
                    if "```" in text:
                        import re
                        match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
                        if match:
                            text = match.group(1)
                    
                    parsed = json.loads(text)
                    print(f"\nParsed JSON: {json.dumps(parsed, indent=2)}")
                except json.JSONDecodeError as e:
                    print(f"\nJSON parsing failed: {e}")
                    print(f"Text that failed: {text[:200]}")
                    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gemini_with_case_normalizer_prompt()
