#!/usr/bin/env python3
"""Simple test for journal tool functionality"""
import asyncio
import httpx
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

BASE_URL = "http://localhost:8000"

async def test_simple_journal():
    """Test simple journal tool functionality"""
    
    print("🚀 Testing simple journal tool...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Login
        print("1. Logging in...")
        login_response = await client.post(f"{BASE_URL}/api/v1/auth/login", json={
            "username": "user_123", 
            "password": "1234"
        })
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.text}")
            return False
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Logged in")
        
        # 2. Create session
        print("2. Creating session...")
        session_response = await client.post(f"{BASE_URL}/api/v1/sessions", 
            headers=headers, json={"conversation_type": "journaling"})
        
        if session_response.status_code != 200:
            print(f"❌ Session failed: {session_response.text}")
            return False
        
        session_id = session_response.json()["session_id"]
        print(f"✅ Session created: {session_id}")
        
        # 3. Test with journal content that should trigger tool
        print("3. Testing journal content...")
        content_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "i am sad because the market is down"}
        )
        
        if content_response.status_code != 200:
            print(f"❌ Content failed: {content_response.status_code}")
            print(f"Error: {content_response.text}")
            return False
        
        data = content_response.json()
        print(f"✅ Content response received")
        print(f"   Tool calls: {len(data.get('tool_calls', []))}")
        
        if data.get('tool_calls'):
            for tool_call in data['tool_calls']:
                print(f"   - Tool: {tool_call.get('name')}")
                print(f"     Input: {tool_call.get('input')}")
                print(f"     Output: {tool_call.get('output')}")
        else:
            print("   ❌ NO TOOLS CALLED")
        
        if data.get('updated_draft_data'):
            print(f"   ✅ Draft updated: {data['updated_draft_data']}")
        else:
            print("   ❌ No draft update")
            
        print(f"   Full response: {data}")
            
    print("🎉 Test completed")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_simple_journal())
    if not success:
        sys.exit(1)