#!/usr/bin/env python3
import requests

base_url = "http://localhost:8000/api/v1"

# Login to get token
login_response = requests.post(f"{base_url}/auth/login", json={
    "username": "user_123",
    "password": "1234"
})

if login_response.status_code != 200:
    print(f"Login failed: {login_response.text}")
    exit(1)

token = login_response.json()["access_token"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Create first session and send message
print("=== Test 1: Fresh session ===")
session_response = requests.post(f"{base_url}/sessions", 
    json={"conversation_type": "journaling"}, 
    headers=headers
)
session_id = session_response.json()["session_id"]
print(f"Created session: {session_id}")

response = requests.post(f"{base_url}/agent/chat/{session_id}",
    json={"text": "Hello, this is my first message"}, 
    headers=headers
)
print(f"First message status: {response.status_code}")
if response.status_code != 200:
    print(f"Error: {response.text}")
else:
    print("Success!")

# Create second session and send message
print("\n=== Test 2: Another fresh session ===")
session_response = requests.post(f"{base_url}/sessions", 
    json={"conversation_type": "journaling"}, 
    headers=headers
)
session_id = session_response.json()["session_id"]
print(f"Created session: {session_id}")

response = requests.post(f"{base_url}/agent/chat/{session_id}",
    json={"text": "Hello, this is a message in a new session"}, 
    headers=headers
)
print(f"Second session message status: {response.status_code}")
if response.status_code != 200:
    print(f"Error: {response.text}")
else:
    print("Success!")