#!/usr/bin/env python3
"""Test multi-turn journal construction and saving"""
import asyncio
import httpx
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

BASE_URL = "http://localhost:8000"

async def test_multi_turn_journal():
    """Test multi-turn journal construction and saving"""
    
    print("🚀 Testing multi-turn journal workflow...")
    
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
        
        # 2. First journal entry - market thoughts
        print("\n2. Adding first journal content...")
        first_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "Today the market dropped 2% and I'm feeling anxious about my portfolio"}
        )
        first_data = first_response.json()
        print(f"✅ First entry added")
        print(f"   Tool calls: {len(first_data.get('tool_calls', []))}")
        print(f"   Draft data: {first_data.get('updated_draft_data')}")
        
        # 3. Second journal entry - add more thoughts (this tests message history)
        print("\n3. Adding second journal content...")
        second_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "I also had lunch with my friend Sarah today and we talked about career goals"}
        )
        second_data = second_response.json()
        print(f"✅ Second entry added")
        print(f"   Tool calls: {len(second_data.get('tool_calls', []))}")
        print(f"   Draft data: {second_data.get('updated_draft_data')}")
        
        # 4. Third entry - more content
        print("\n4. Adding third journal content...")
        third_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "I'm grateful for having supportive friends like Sarah who listen to my concerns"}
        )
        third_data = third_response.json()
        print(f"✅ Third entry added") 
        print(f"   Tool calls: {len(third_data.get('tool_calls', []))}")
        print(f"   Draft data: {third_data.get('updated_draft_data')}")
        
        # 5. Save the journal (this is the key test - can the agent see previous content?)
        print("\n5. Saving journal...")
        save_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "Please save my journal entry now"}
        )
        save_data = save_response.json()
        print(f"✅ Save command processed")
        print(f"   Agent response: {save_data.get('text', '')[:100]}...")
        print(f"   Tool calls: {len(save_data.get('tool_calls', []))}")
        
        # Check if save was successful
        save_tool_calls = [call for call in save_data.get('tool_calls', []) if call['name'] == 'save_journal_tool']
        if save_tool_calls:
            print(f"   ✅ SaveJournalTool was called")
            save_result = save_tool_calls[0]['output']
            print(f"   Save status: {save_result.get('status')}")
            if save_data.get('metadata', {}).get('journal_entry_id'):
                print(f"   ✅ Journal entry created: {save_data['metadata']['journal_entry_id']}")
            else:
                print(f"   ❌ No journal_entry_id in metadata")
        else:
            print(f"   ❌ SaveJournalTool was NOT called - this means the agent didn't understand the save request")
        
        # 6. Verify final state in database
        print("\n6. Checking database state...")
        from app.database import init_db, get_db
        from app.repositories.session import JournalDraftRepository, JournalEntryRepository
        
        await init_db()
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        draft_repo = JournalDraftRepository()
        entry_repo = JournalEntryRepository()
        
        draft = await draft_repo.get_by_session_id(db, session_id)
        entries = await entry_repo.get_by_user_id(db, "user_123", limit=1)
        
        print(f"   Draft finalized: {draft.is_finalized if draft else 'No draft'}")
        if draft:
            print(f"   Final draft data: {draft.draft_data}")
        print(f"   Journal entries created: {len(entries)}")
        if entries:
            print(f"   Latest entry content: {entries[0].structured_data}")
        
        await db_gen.aclose()
        
    print("\n🎉 Multi-turn journal test completed!")
    
    # Determine success
    success = (
        save_tool_calls and 
        save_data.get('metadata', {}).get('journal_entry_id') and
        entries and len(entries) > 0
    )
    
    if success:
        print("✅ SUCCESS: Multi-turn journal construction and saving works!")
    else:
        print("❌ FAILURE: Multi-turn workflow has issues")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(test_multi_turn_journal())
    if not success:
        sys.exit(1)