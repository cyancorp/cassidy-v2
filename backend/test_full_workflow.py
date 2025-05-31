#!/usr/bin/env python3
"""Test complete journal workflow including save"""
import asyncio
import httpx
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

BASE_URL = "http://localhost:8000"

async def test_full_journal_workflow():
    """Test complete journal workflow including save"""
    
    print("🚀 Testing complete journal workflow...")
    
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
        
        # 3. Add journal content
        print("3. Adding journal content...")
        content_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "I am sad because the market is down and I lost money on my investments"}
        )
        
        if content_response.status_code != 200:
            print(f"❌ Content failed: {content_response.status_code}")
            return False
        
        data = content_response.json()
        print(f"✅ Content added successfully")
        print(f"   Tool calls: {len(data.get('tool_calls', []))}")
        print(f"   Draft data: {data.get('updated_draft_data')}")
        
        # 4. Test save functionality
        print("4. Testing save...")
        save_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "Please save this journal entry now. I want to finalize it."}
        )
        
        if save_response.status_code != 200:
            print(f"❌ Save failed: {save_response.status_code}")
            return False
        
        save_data = save_response.json()
        print(f"✅ Save processed")
        print(f"   Agent response: {save_data.get('text', '')[:100]}...")
        print(f"   Tool calls: {len(save_data.get('tool_calls', []))}")
        
        save_tool_calls = [call for call in save_data.get('tool_calls', []) if call['name'] == 'save_journal_tool']
        if save_tool_calls:
            print(f"   ✅ SaveJournalTool was called")
            print(f"   Save result: {save_tool_calls[0]['output']}")
        else:
            print(f"   ❌ SaveJournalTool was NOT called")
            
        # Check if journal_entry_id is in metadata
        if save_data.get('metadata', {}).get('journal_entry_id'):
            print(f"   ✅ Journal entry created: {save_data['metadata']['journal_entry_id']}")
        else:
            print(f"   ⚠️  No journal_entry_id in metadata")
            
    print("🎉 Full workflow test completed!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_full_journal_workflow())
    if not success:
        sys.exit(1)