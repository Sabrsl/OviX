"""
Script de test pour comparer les statistiques entre l'ancien et le nouveau système.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_compare_summary():
    """Test le endpoint de comparaison summary."""
    try:
        response = requests.get(f"{BASE_URL}/api/stats/compare/summary")
        response raise_for_status()
        data = response.json()
        print("=== COMPARISON SUMMARY ===")
        print(json.dumps(data, indent=2))
        return data
    except Exception as e:
        print(f"Erreur lors de la comparaison: {e}")
        return None

def test_compare_full():
    """Test le endpoint de comparaison complet."""
    try:
        response = requests.get(f"{BASE_URL}/api/stats/compare")
        response.raise_for_status()
        data = response.json()
        print("=== FULL COMPARISON ===")
        print(json.dumps(data, indent=2))
        return data
    except Exception as e:
        print(f"Erreur lors de la comparaison complète: {e}")
        return None

if __name__ == "__main__":
    print("Test de comparaison des statistiques...")
    print()
    
    summary = test_compare_summary()
    print()
    
    full = test_compare_full()
    print()
    
    if summary:
        print(f"Consistent: {summary.get('consistent', 'N/A')}")
        print(f"Differences count: {summary.get('differences_count', 'N/A')}")
