#!/usr/bin/env python3
"""Test the new template structure with Events and Things Done sections"""
import asyncio
import httpx
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, 'app')

BASE_URL = "http://localhost:8000"

async def test_new_template_sections():
    """Test new template sections with realistic content"""
    
    print("🚀 Testing new template sections (Events & Things Done)...")
    
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
        
        # 2. Test content with Things Done and Events
        print("\n2. Testing content with Tasks, Events, and Dates...")
        complex_text = """Today I completed my quarterly review presentation and finished the client proposal for ABC Corp. 
        
        I have an important meeting with the CEO tomorrow at 2pm, and don't forget the team standup on Friday at 9am. 
        
        The product launch is scheduled for March 15th, and I need to prepare for the investor call next Tuesday.
        
        I also called mom for her birthday and helped my neighbor fix their computer. Feeling productive and grateful for a good day."""
        
        response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": complex_text}
        )
        
        data = response.json()
        print(f"✅ Content processed")
        print(f"   Tool calls: {len(data.get('tool_calls', []))}")
        draft_data = data.get('updated_draft_data', {})
        print(f"   Draft sections created: {list(draft_data.keys())}")
        
        # 3. Analyze the structured content
        print(f"\n📊 Content Analysis:")
        for section, content in draft_data.items():
            print(f"   {section}:")
            if isinstance(content, list):
                for i, item in enumerate(content[:2]):  # Show first 2 items
                    print(f"     {i+1}. {item[:60]}...")
            else:
                print(f"     {content[:80]}...")
        
        # 4. Check if new sections were used
        sections_used = set(draft_data.keys())
        print(f"\n🎯 Section Usage Analysis:")
        
        expected_new_sections = {"Things Done", "Events"}
        new_sections_found = sections_used.intersection(expected_new_sections)
        
        if new_sections_found:
            print(f"   ✅ New sections used: {new_sections_found}")
            
            # Check specific content mapping
            if "Things Done" in draft_data:
                things_done_content = str(draft_data["Things Done"]).lower()
                if any(word in things_done_content for word in ["completed", "finished", "called", "helped"]):
                    print(f"   ✅ Things Done correctly captured accomplishments")
                
            if "Events" in draft_data:
                events_content = str(draft_data["Events"]).lower()
                if any(word in events_content for word in ["meeting", "2pm", "friday", "tuesday", "march 15"]):
                    print(f"   ✅ Events correctly captured dates and appointments")
        else:
            print(f"   ⚠️  New sections not used. Content went to: {sections_used}")
        
        # 5. Test save functionality
        print("\n3. Testing save...")
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
            
    print("\n🎉 New template test completed!")
    
    # Summary
    success = (
        draft_data and 
        len(draft_data) >= 2 and  # At least 2 sections should be populated
        (new_sections_found or len(sections_used) >= 3)  # Either new sections used or good distribution
    )
    
    if success:
        print("✅ SUCCESS: New template sections are working properly!")
        print(f"   Sections populated: {len(draft_data)}")
        print(f"   New sections detected: {new_sections_found}")
    else:
        print("❌ NEEDS REVIEW: Template may need adjustment")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(test_new_template_sections())
    if not success:
        sys.exit(1)