#!/usr/bin/env python3
"""Test journal entry functionality"""
import asyncio
import httpx
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

BASE_URL = "http://localhost:8000"

async def test_journal_functionality():
    """Test that journal tools are working correctly"""
    
    print("🚀 Testing journal entry functionality...")
    
    async with httpx.AsyncClient() as client:
        # 1. Login
        print("1. Logging in...")
        login_response = await client.post(f"{BASE_URL}/api/v1/auth/login", json={
            "username": "user_123",
            "password": "1234"
        })
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.text}")
            return False
        
        login_data = login_response.json()
        token = login_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"✅ Logged in")
        
        # 2. Create session
        print("2. Creating session...")
        session_response = await client.post(f"{BASE_URL}/api/v1/sessions", 
            headers=headers,
            json={"conversation_type": "journaling"}
        )
        
        if session_response.status_code != 200:
            print(f"❌ Session creation failed: {session_response.text}")
            return False
        
        session_data = session_response.json()
        session_id = session_data["session_id"]
        print(f"✅ Created session: {session_id}")
        
        # 3. Test agent can respond without crashing
        print("3. Testing agent response...")
        agent_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "hi i want to create a journal entry"}
        )
        
        if agent_response.status_code != 200:
            print(f"❌ Agent failed: {agent_response.status_code} - {agent_response.text}")
            return False
        
        agent_data = agent_response.json()
        print(f"✅ Agent responded successfully")
        print(f"   Response: {agent_data['text'][:100]}...")
        print(f"   Tool calls: {len(agent_data.get('tool_calls', []))}")
        
        # 4. Test with journal content
        print("4. Testing journal content processing...")
        content_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "i am sad because the market is down"}
        )
        
        if content_response.status_code != 200:
            print(f"❌ Content processing failed: {content_response.status_code} - {content_response.text}")
            return False
        
        content_data = content_response.json()
        print(f"✅ Content processed successfully")
        print(f"   Response: {content_data['text'][:100]}...")
        print(f"   Tool calls: {len(content_data.get('tool_calls', []))}")
        print(f"   Updated draft: {content_data.get('updated_draft_data') is not None}")
        
        # Check if StructureJournalTool was called
        structure_calls = [call for call in content_data.get("tool_calls", []) if call["name"] == "structure_journal_tool"]
        if structure_calls:
            print(f"   ✅ StructureJournalTool was called")
        else:
            print(f"   ⚠️  StructureJournalTool was NOT called")
        
        # 5. Test save functionality
        print("5. Testing save functionality...")
        save_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "save the journal"}
        )
        
        if save_response.status_code != 200:
            print(f"❌ Save failed: {save_response.status_code} - {save_response.text}")
            return False
        
        save_data = save_response.json()
        print(f"✅ Save processed successfully")
        print(f"   Response: {save_data['text'][:100]}...")
        print(f"   Tool calls: {len(save_data.get('tool_calls', []))}")
        
        # Check if SaveJournalTool was called
        save_calls = [call for call in save_data.get("tool_calls", []) if call["name"] == "save_journal_tool"]
        if save_calls:
            print(f"   ✅ SaveJournalTool was called")
        else:
            print(f"   ⚠️  SaveJournalTool was NOT called")
    
    print("🎉 Journal functionality test completed!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_journal_functionality())
    if not success:
        sys.exit(1)