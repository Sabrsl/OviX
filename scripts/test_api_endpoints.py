"""
Test direct des endpoints API OviX pour validation.

Verifie que les nouveaux endpoints fonctionnent correctement.
"""

import requests
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

BASE_URL = "http://localhost:8000"

def test_endpoint(description, method, endpoint, data=None, expected_status=200):
    """Test un endpoint API."""
    print(f"\nTest: {description}")
    print(f"  {method} {endpoint}")
    
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{endpoint}", json=data, timeout=5)
        elif method == "DELETE":
            response = requests.delete(f"{BASE_URL}{endpoint}", timeout=5)
        else:
            print(f"  [ERROR] Method {method} not supported")
            return False
        
        if response.status_code == expected_status:
            print(f"  [OK] Status: {response.status_code}")
            try:
                print(f"  Response: {json.dumps(response.json(), indent=2)[:200]}...")
            except:
                print(f"  Response: {response.text[:200]}...")
            return True
        else:
            print(f"  [ERROR] Status: {response.status_code} (expected {expected_status})")
            print(f"  Response: {response.text[:200]}...")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Backend not running at {BASE_URL}")
        return False
    except Exception as e:
        print(f"  [ERROR] {str(e)}")
        return False

def main():
    """Test tous les endpoints."""
    print("=" * 80)
    print("TEST DES ENDPOINTS API OVIX")
    print("=" * 80)
    
    results = []
    
    # Test 1: Verification que le backend tourne
    print("\n1. VERIFICATION BACKEND")
    print("-" * 80)
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
        if response.status_code == 200:
            print(f"  [OK] Backend running at {BASE_URL}")
        else:
            print(f"  [WARNING] Backend responds with status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Backend not running at {BASE_URL}")
        print("  Start the backend with: cd backend && python -m uvicorn api.main:app --reload")
        return
    except Exception as e:
        print(f"  [ERROR] {str(e)}")
        return
    
    # Test 2: Endpoints de recuperation (sans auth pour le moment)
    print("\n2. ENDPOINTS DE RECUPERATION")
    print("-" * 80)
    
    # Note: Ces endpoints necessitent l'authentification Wikipedia
    # Pour l'instant, on teste juste qu'ils existent
    
    results.append(test_endpoint(
        "GET /api/articles/queue (file d'attente)",
        "GET", "/api/articles/queue",
        expected_status=200
    ))
    
    results.append(test_endpoint(
        "GET /api/articles/results (resultats globaux)",
        "GET", "/api/articles/results",
        expected_status=200
    ))
    
    # Test 3: Endpoint de resultat specifique
    print("\n3. ENDPOINT DE RESULTAT SPECIFIQUE")
    print("-" * 80)
    
    # Recuperer un article titre depuis SQLite
    from wikipedia_maintenance.utils.database import DatabaseManager
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute("SELECT article_title FROM analysis_results LIMIT 1")
    row = cursor.fetchone()
    if row:
        article_title = row[0]
        print(f"  Article de test: {article_title}")
        
        results.append(test_endpoint(
            f"GET /api/articles/results/{article_title}",
            "GET", f"/api/articles/results/{article_title}",
            expected_status=200
        ))
    else:
        print("  [WARNING] Aucun article dans analysis_results")
    
    db.close()
    
    # Test 4: Endpoints d'analyse (sans auth pour le moment)
    print("\n4. ENDPOINTS D'ANALYSE")
    print("-" * 80)
    print("  [INFO] Les endpoints d'analyse necessitent l'authentification Wikipedia")
    print("  POST /api/articles/queue/{article_id}/analyze")
    print("  POST /api/articles/queue/analyze-next")
    print("  DELETE /api/articles/queue/{article_id}")
    
    # Resume
    print("\n" + "=" * 80)
    print("RESUME DES TESTS")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passes: {passed}/{total}")
    
    if passed == total:
        print("\n[SUCCESS] Tous les tests API ont passe")
    else:
        print(f"\n[WARNING] {total - passed} test(s) ont echoue")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()