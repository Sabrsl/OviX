import requests

# Test publication endpoints
base_url = "http://127.0.0.1:8000"

# Test 1: Health check
print("Test 1: Health check")
response = requests.get(f"{base_url}/api/health")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
print()

# Test 2: Publication validation
print("Test 2: Publication validation")
data = {
    "article_title": "Test Article",
    "corrected_content": "Test content",
    "original_content": "Original content",
    "summary": "Test publication",
    "dry_run": True
}
response = requests.post(f"{base_url}/api/publication/validate", json=data)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
print()