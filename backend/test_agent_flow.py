"""Test the complete agent journaling workflow"""
import asyncio
import httpx
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

BASE_URL = "http://localhost:8000"

async def test_agent_flow():
    """Test complete journaling workflow with agent"""
    
    print("🚀 Testing complete agent journaling workflow...")
    
    async with httpx.AsyncClient() as client:
        # 1. Login to get token
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
        print(f"✅ Logged in as {login_data['username']}")
        
        # 2. Create a new journaling session
        print("2. Creating journaling session...")
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
        
        # 3. Test agent interaction - sad trading entry
        print("3. Testing agent with sad trading journal entry...")
        agent_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={
                "text": "I'm feeling really sad today because I lost money in the stock market. I bought 100 shares of AAPL at $150 and had to sell at $145, losing $500. The market has been really bearish and I think we might see more downside."
            }
        )
        
        if agent_response.status_code != 200:
            print(f"❌ Agent interaction failed: {agent_response.text}")
            return False
        
        agent_data = agent_response.json()
        print(f"✅ Agent responded: {agent_data['text'][:100]}...")
        
        if agent_data.get("updated_draft_data"):
            print("✅ Draft data updated:")
            for section, content in agent_data["updated_draft_data"].items():
                print(f"   {section}: {content[:50]}...")
        
        if agent_data.get("tool_calls"):
            print(f"✅ Tool calls executed: {len(agent_data['tool_calls'])}")
            for tool_call in agent_data["tool_calls"]:
                print(f"   - {tool_call['name']}")
        
        # 4. Test follow-up interaction
        print("4. Testing follow-up interaction...")
        followup_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={
                "text": "I'm also thinking about changing my strategy to focus more on long-term investments rather than day trading."
            }
        )
        
        if followup_response.status_code != 200:
            print(f"❌ Follow-up interaction failed: {followup_response.text}")
            return False
        
        followup_data = followup_response.json()
        print(f"✅ Follow-up response: {followup_data['text'][:100]}...")
        
        # 5. Test saving the journal
        print("5. Testing journal save...")
        save_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={
                "text": "Please save this journal entry"
            }
        )
        
        if save_response.status_code != 200:
            print(f"❌ Save interaction failed: {save_response.text}")
            return False
        
        save_data = save_response.json()
        print(f"✅ Save response: {save_data['text'][:100]}...")
        
        # Check if SaveJournal tool was called
        save_tool_calls = [call for call in save_data.get("tool_calls", []) if call["name"] == "save_journal_tool"]
        if save_tool_calls:
            print("✅ Journal save tool was called")
        
        # 6. Test getting user preferences and template
        print("6. Testing user preferences and template...")
        prefs_response = await client.get(f"{BASE_URL}/api/v1/user/preferences", headers=headers)
        template_response = await client.get(f"{BASE_URL}/api/v1/user/template", headers=headers)
        
        if prefs_response.status_code == 200:
            print("✅ User preferences retrieved")
        if template_response.status_code == 200:
            template_data = template_response.json()
            print(f"✅ User template retrieved: {len(template_data.get('sections', {}))} sections")
        
    print("🎉 Complete agent workflow test completed successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_agent_flow())
    if not success:
        sys.exit(1)