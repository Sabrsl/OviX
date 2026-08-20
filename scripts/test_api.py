import requests

# Test API endpoints
base_url = "http://127.0.0.1:8000"

# Test 1: Health check
print("Test 1: Health check")
try:
    response = requests.get(f"{base_url}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
print()

# Test 2: Get statistics (this is what the Dashboard needs)
print("Test 2: Get statistics")
try:
    response = requests.get(f"{base_url}/api/history/statistics")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
print()

# Test 3: Get analyzed history
print("Test 3: Get analyzed history")
try:
    response = requests.get(f"{base_url}/api/history/analyzed")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
print()

# Test 4: Get published history
print("Test 4: Get published history")
try:
    response = requests.get(f"{base_url}/api/history/published")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
print()

# Test 5: Get queue
print("Test 5: Get queue")
try:
    response = requests.get(f"{base_url}/api/articles/queue")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
print()

# Test 6: Get results
print("Test 6: Get results")
try:
    response = requests.get(f"{base_url}/api/articles/results")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
print()