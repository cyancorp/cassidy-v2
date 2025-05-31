#!/usr/bin/env python3
"""Test tools directly"""
import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_tools_directly():
    """Test tools directly without agent"""
    
    print("🚀 Testing tools directly...")
    
    try:
        from app.agents.tools import structure_journal_tool, save_journal_tool
        from app.agents.models import (
            CassidyAgentDependencies, 
            StructureJournalRequest, 
            SaveJournalRequest
        )
        print("✅ Tool imports successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Create test context
    context = CassidyAgentDependencies(
        user_id="test-user",
        session_id="test-session", 
        conversation_type="journaling",
        user_template={
            "name": "Test Template",
            "sections": {
                "Thoughts & Feelings": {
                    "description": "Emotional state, mood, thoughts, and internal experiences",
                    "aliases": ["Emotions", "Mood", "Feelings", "Thoughts"]
                }
            }
        },
        user_preferences={"preferred_feedback_style": "supportive"},
        current_journal_draft={}
    )
    
    print("✅ Context created")
    
    # Test structure_journal_tool
    try:
        print("Testing structure_journal_tool...")
        request = StructureJournalRequest(user_text="i am sad because the market is down")
        result = await structure_journal_tool(context, request)
        print(f"✅ Tool result: {result}")
        print(f"   Sections updated: {result.sections_updated}")
        print(f"   Status: {result.status}")
        print(f"   Updated context draft: {context.current_journal_draft}")
    except Exception as e:
        print(f"❌ structure_journal_tool failed: {e}")
        return False
    
    # Test save_journal_tool
    try:
        print("Testing save_journal_tool...")
        save_request = SaveJournalRequest(confirmation=True)
        save_result = await save_journal_tool(context, save_request)
        print(f"✅ Save result: {save_result}")
        print(f"   Status: {save_result.status}")
    except Exception as e:
        print(f"❌ save_journal_tool failed: {e}")
        return False
        
    print("🎉 Direct tool testing completed successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_tools_directly())
    if not success:
        sys.exit(1)