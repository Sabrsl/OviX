"""Test direct Gemini call to see response format."""

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

def test_gemini_direct():
    """Test direct Gemini call with simple prompt."""
    print("=" * 60)
    print("DIRECT GEMINI TEST")
    print("=" * 60)
    
    # Initialize Gemini client
    client = GeminiClient()
    
    # Simple JSON prompt
    prompt = """Return a JSON with the following fields:
{
  "titre": "normalized title",
  "auteur": "normalized author"
}

Input values:
{
  "titre": "TEST TITLE",
  "auteur": "JEAN DUPONT"
}

JSON:"""
    
    print(f"\nPrompt: {prompt}")
    
    # Call Gemini
    try:
        ok, nb_caracteres = client.verifier_longueur(prompt)
        print(f"Length check: {ok}, {nb_caracteres} characters")
        
        if ok:
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
            
            response = client._appeler_api_avec_retry(payload, 30)
            data = response.json()
            
            print(f"\nFull response: {json.dumps(data, indent=2)[:1000]}")
            
            if "candidates" in data and len(data["candidates"]) > 0:
                text = data["candidates"][0]["content"]["parts"][0].get("text", "").strip()
                print(f"\nExtracted text: {text}")
                
                # Try to parse as JSON
                try:
                    parsed = json.loads(text)
                    print(f"\nParsed JSON: {json.dumps(parsed, indent=2)}")
                except json.JSONDecodeError as e:
                    print(f"\nJSON parsing failed: {e}")
                    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gemini_direct()
