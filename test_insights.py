#!/usr/bin/env python3
"""
Test script for insights generation
"""

import requests
import json
import sys

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USER = "user_123"
TEST_PASSWORD = "password123"

def login():
    """Login and get access token"""
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", data={
        "username": TEST_USER,
        "password": TEST_PASSWORD
    })
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None
    
    token_data = response.json()
    return token_data["access_token"]

def create_session(token):
    """Create a new chat session"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/api/v1/sessions/", headers=headers)
    
    if response.status_code != 201:
        print(f"❌ Session creation failed: {response.status_code} - {response.text}")
        return None
    
    return response.json()["session_id"]

def send_message(token, session_id, message):
    """Send a message to the chat"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {
        "text": message,
        "metadata": {}
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/sessions/{session_id}/messages", 
                           headers=headers, json=data)
    
    if response.status_code != 200:
        print(f"❌ Message failed: {response.status_code} - {response.text}")
        return None
    
    return response.json()

def test_insights():
    """Test insights generation"""
    print("🔐 Logging in...")
    token = login()
    if not token:
        return
    
    print("💬 Creating session...")
    session_id = create_session(token)
    if not session_id:
        return
    
    print("🔍 Requesting insights...")
    response = send_message(token, session_id, "Can you generate insights from my journal entries?")
    
    if response:
        print("✅ Insights request sent successfully!")
        print("📊 Response preview:")
        if "message" in response:
            print(response["message"][:500] + "..." if len(response["message"]) > 500 else response["message"])
    else:
        print("❌ Failed to get insights")

if __name__ == "__main__":
    test_insights()