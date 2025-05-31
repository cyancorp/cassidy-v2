#!/usr/bin/env python3
import asyncio
import requests
import json

async def test_agent_flow():
    base_url = "http://localhost:8000/api/v1"
    
    # Login to get token
    login_response = requests.post(f"{base_url}/auth/login", json={
        "username": "user_123",
        "password": "1234"
    })
    
    if login_response.status_code != 200:
        print(f"Login failed: {login_response.text}")
        return
    
    token = login_response.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Create session
    session_response = requests.post(f"{base_url}/sessions", 
        json={"conversation_type": "journaling"}, 
        headers=headers
    )
    
    if session_response.status_code != 200:
        print(f"Session creation failed: {session_response.text}")
        return
    
    session_id = session_response.json()["session_id"]
    print(f"Created session: {session_id}")
    
    # Send first message
    print("\n--- Sending first message ---")
    first_response = requests.post(f"{base_url}/agent/chat/{session_id}",
        json={"text": "Hi there!"}, 
        headers=headers
    )
    
    print(f"First message status: {first_response.status_code}")
    if first_response.status_code == 200:
        print(f"First response: {first_response.json()['text'][:100]}...")
    else:
        print(f"First message error: {first_response.text}")
        return
    
    # Send second message
    print("\n--- Sending second message ---")
    second_response = requests.post(f"{base_url}/agent/chat/{session_id}",
        json={"text": "I had a good day today. I went for a walk in the park."}, 
        headers=headers
    )
    
    print(f"Second message status: {second_response.status_code}")
    if second_response.status_code == 200:
        print(f"Second response: {second_response.json()['text'][:100]}...")
    else:
        print(f"Second message error: {second_response.text}")

if __name__ == "__main__":
    asyncio.run(test_agent_flow())