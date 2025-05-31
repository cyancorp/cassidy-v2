"""Simple test of agent setup without API calls"""
import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_agent_setup():
    """Test agent setup without making API calls"""
    
    print("🚀 Testing agent setup...")
    
    # Test imports
    try:
        from app.agents.factory import AgentFactory
        from app.agents.service import AgentService
        from app.agents.tools import get_tools_for_conversation_type
        from app.agents.models import CassidyAgentDependencies
        print("✅ Agent imports successful")
    except Exception as e:
        print(f"❌ Agent import failed: {e}")
        return False
    
    # Test tool setup
    try:
        tools = get_tools_for_conversation_type("journaling")
        print(f"✅ Journaling tools loaded: {len(tools)} tools")
        for tool in tools:
            print(f"   - {tool.function.__name__}")
    except Exception as e:
        print(f"❌ Tool setup failed: {e}")
        return False
    
    # Test agent dependencies model
    try:
        deps = CassidyAgentDependencies(
            user_id="test-user",
            session_id="test-session",
            conversation_type="journaling",
            user_template={"sections": {}},
            user_preferences={"preferred_feedback_style": "supportive"},
            current_journal_draft={}
        )
        print("✅ Agent dependencies model works")
    except Exception as e:
        print(f"❌ Agent dependencies failed: {e}")
        return False
    
    # Test database setup with agent service
    try:
        from app.database import init_db, get_db
        await init_db()
        
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        agent_service = AgentService(db)
        print("✅ Agent service initialized with database")
        
        await db_gen.aclose()
    except Exception as e:
        print(f"❌ Agent service database setup failed: {e}")
        return False
    
    print("🎉 Agent setup test completed successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_agent_setup())
    if not success:
        sys.exit(1)