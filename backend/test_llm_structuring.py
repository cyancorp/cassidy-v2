#!/usr/bin/env python3
"""Test LLM-based journal structuring"""
import asyncio
import httpx
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, 'app')

BASE_URL = "http://localhost:8000"

async def test_llm_structuring():
    """Test LLM-based content structuring with complex input"""
    
    print("🚀 Testing LLM-based journal structuring...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Login and create session
        print("1. Setting up session...")
        login_response = await client.post(f"{BASE_URL}/api/v1/auth/login", json={
            "username": "user_123", "password": "1234"
        })
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        session_response = await client.post(f"{BASE_URL}/api/v1/sessions", 
            headers=headers, json={"conversation_type": "journaling"})
        session_id = session_response.json()["session_id"]
        print(f"✅ Session: {session_id}")
        
        # 2. Test complex multi-section content
        print("\n2. Testing complex content structuring...")
        complex_text = """Today was a mixed day. The market opened down 1.5% which made me feel anxious about my portfolio, especially my tech stocks. I had three important events happen:
        
        1. Morning meeting with Sarah went really well - we discussed the new project timeline
        2. Lunch with my brother where we talked about mom's birthday plans
        3. Evening workout at the gym which helped clear my head
        
        I'm grateful for having supportive family and colleagues who understand my work stress. Tomorrow I plan to review my investment strategy and maybe rebalance my portfolio to be less tech-heavy. I also want to call mom and finalize the birthday dinner plans.
        
        Emotionally, I started the day anxious but ended feeling more optimistic and focused."""
        
        response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": complex_text}
        )
        
        data = response.json()
        print(f"✅ Content processed")
        print(f"   Tool calls: {len(data.get('tool_calls', []))}")
        print(f"   Draft data structure: {data.get('updated_draft_data')}")
        
        # Check if content was intelligently structured
        draft_data = data.get('updated_draft_data', {})
        if draft_data:
            print(f"\n📊 Structured Content Analysis:")
            for section, content in draft_data.items():
                print(f"   {section}: {type(content).__name__}")
                if isinstance(content, list):
                    print(f"     - {len(content)} items")
                    for i, item in enumerate(content[:2]):  # Show first 2 items
                        print(f"       {i+1}. {item[:50]}...")
                else:
                    print(f"     - {content[:100]}...")
        
        # 3. Test another entry that should merge intelligently
        print("\n3. Testing content merging...")
        followup_text = """Quick update: I also realized I need to:
        - Book the restaurant for mom's birthday 
        - Send follow-up email to Sarah about the project
        
        Feeling much better now after talking to my therapist about the market anxiety."""
        
        response2 = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": followup_text}
        )
        
        data2 = response2.json()
        print(f"✅ Follow-up content processed")
        print(f"   Updated draft: {data2.get('updated_draft_data')}")
        
        # 4. Save the entry
        print("\n4. Saving structured journal...")
        save_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "Please save this journal entry"}
        )
        
        save_data = save_response.json()
        save_calls = [call for call in save_data.get('tool_calls', []) if call['name'] == 'save_journal_tool']
        
        if save_calls and save_data.get('metadata', {}).get('journal_entry_id'):
            print(f"✅ Journal saved successfully: {save_data['metadata']['journal_entry_id']}")
        else:
            print(f"❌ Save failed")
            
    print("\n🎉 LLM structuring test completed!")


if __name__ == "__main__":
    asyncio.run(test_llm_structuring())