"""Test journal search functionality"""
import pytest
import asyncio
from datetime import datetime, timedelta
import json
import os
from uuid import uuid4

# Use test database
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test_journal_search.db'

from app.database import init_db, get_db
from app.repositories.user import UserRepository
from app.repositories.session import JournalEntryRepository
from app.agents.factory import AgentFactory
from app.agents.models import CassidyAgentDependencies


async def create_test_data():
    """Create test user and journal entries"""
    await init_db()
    
    async for db in get_db():
        user_repo = UserRepository()
        journal_repo = JournalEntryRepository()
        
        # Create test user
        username = f"test_user_{uuid4().hex[:8]}"
        email = f"test_{uuid4().hex[:8]}@test.com"
        password_hash = "dummy_hash"  # Not used for testing
        
        user = await user_repo.create_user(db, username, email, password_hash)
        user_id = str(user.id)
        
        # Create test journal entries with different dates and content
        test_entries = [
            {
                "title": "Morning Reflections",
                "raw_text": "Had a great morning walk in the park. Feeling energized and ready for the day.",
                "structured_data": {
                    "General Reflection": "Had a great morning walk in the park",
                    "Mood": "Energized and positive",
                    "Activities": ["Morning walk", "Park visit"]
                },
                "created_at": datetime.utcnow() - timedelta(days=0, hours=2)  # 2 hours ago
            },
            {
                "title": "Project Progress",
                "raw_text": "Made significant progress on the new feature. Completed the database schema and API endpoints.",
                "structured_data": {
                    "Work Progress": "Completed database schema and API endpoints",
                    "Goals": ["Finish feature by Friday", "Write tests"],
                    "Mood": "Accomplished"
                },
                "created_at": datetime.utcnow() - timedelta(days=1)  # Yesterday
            },
            {
                "title": "Weekend Plans",
                "raw_text": "Planning to visit family this weekend. Need to prepare some gifts and plan the route.",
                "structured_data": {
                    "Plans": "Visit family this weekend",
                    "Tasks": ["Buy gifts", "Plan route", "Prepare food"],
                    "General Reflection": "Looking forward to seeing everyone"
                },
                "created_at": datetime.utcnow() - timedelta(days=3)  # 3 days ago
            },
            {
                "title": "Learning Python",
                "raw_text": "Started learning Python decorators today. They're confusing but powerful.",
                "structured_data": {
                    "Learning": "Python decorators",
                    "Insights": "Confusing but powerful concept",
                    "Goals": ["Master decorators", "Build a project using them"]
                },
                "created_at": datetime.utcnow() - timedelta(days=7)  # A week ago
            }
        ]
        
        created_entries = []
        for entry_data in test_entries:
            # Create the entry
            entry = await journal_repo.create(
                db,
                user_id=user_id,
                raw_text=entry_data["raw_text"],
                structured_data=entry_data["structured_data"],  # Don't JSON encode here
                title=entry_data["title"]
            )
            # Update created_at manually to set specific dates
            entry.created_at = entry_data["created_at"]
            await db.commit()
            created_entries.append(entry)
        
        return user, created_entries


async def test_search_most_recent_journal():
    """Test searching for the most recent journal entry"""
    print("\n🧪 Testing: Search for most recent journal entry")
    
    # Create test data
    user, entries = await create_test_data()
    user_id = str(user.id)
    
    # Create agent context
    deps = CassidyAgentDependencies(
        user_id=user_id,
        session_id="test-session",
        conversation_type="general",
        user_template={},
        user_preferences={},
        current_journal_draft={},
        current_tasks=[]
    )
    
    # Get agent
    agent = await AgentFactory.get_agent(
        conversation_type="general",
        user_id=user_id,
        context=deps
    )
    
    # Test different ways users might ask for recent entries
    test_queries = [
        "please find and summarize my most recent journal entry",
        "show me my latest journal entry",
        "what did I write in my last journal?",
        "get my most recent journal"
    ]
    
    for query in test_queries:
        print(f"\n📝 Testing query: '{query}'")
        try:
            result = await agent.run(query, deps=deps)
            print(f"✅ Response: {result.output[:200]}...")
            
            # Check if it's an error
            if "error" in result.output.lower() or "❌" in result.output:
                print(f"❌ ERROR DETECTED in response!")
                print(f"Full response: {result.output}")
        except Exception as e:
            print(f"❌ Exception occurred: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()


async def test_search_journal_by_content():
    """Test searching journal entries by content"""
    print("\n🧪 Testing: Search journal entries by content")
    
    # Create test data
    user, entries = await create_test_data()
    user_id = str(user.id)
    
    # Create agent context
    deps = CassidyAgentDependencies(
        user_id=user_id,
        session_id="test-session",
        conversation_type="general",
        user_template={},
        user_preferences={},
        current_journal_draft={},
        current_tasks=[]
    )
    
    # Get agent
    agent = await AgentFactory.get_agent(
        conversation_type="general",
        user_id=user_id,
        context=deps
    )
    
    # Test content-based searches
    test_searches = [
        "find journal entries about Python",
        "search for entries mentioning family",
        "show me entries where I talked about work progress"
    ]
    
    for search in test_searches:
        print(f"\n🔍 Testing search: '{search}'")
        try:
            result = await agent.run(search, deps=deps)
            print(f"✅ Response: {result.output[:200]}...")
        except Exception as e:
            print(f"❌ Exception occurred: {type(e).__name__}: {str(e)}")


async def test_search_journal_by_date():
    """Test searching journal entries by date range"""
    print("\n🧪 Testing: Search journal entries by date")
    
    # Create test data
    user, entries = await create_test_data()
    user_id = str(user.id)
    
    # Create agent context
    deps = CassidyAgentDependencies(
        user_id=user_id,
        session_id="test-session",
        conversation_type="general",
        user_template={},
        user_preferences={},
        current_journal_draft={},
        current_tasks=[]
    )
    
    # Get agent
    agent = await AgentFactory.get_agent(
        conversation_type="general",
        user_id=user_id,
        context=deps
    )
    
    # Test date-based searches
    test_searches = [
        "show me journal entries from the last 3 days",
        "find entries from this week",
        "what did I write yesterday?"
    ]
    
    for search in test_searches:
        print(f"\n📅 Testing search: '{search}'")
        try:
            result = await agent.run(search, deps=deps)
            print(f"✅ Response: {result.output[:200]}...")
        except Exception as e:
            print(f"❌ Exception occurred: {type(e).__name__}: {str(e)}")


async def test_direct_tool_call():
    """Test calling the search journal tool directly"""
    print("\n🧪 Testing: Direct journal search tool call")
    
    # Create test data
    user, entries = await create_test_data()
    user_id = str(user.id)
    
    # Create agent context
    deps = CassidyAgentDependencies(
        user_id=user_id,
        session_id="test-session",
        conversation_type="general",
        user_template={},
        user_preferences={},
        current_journal_draft={},
        current_tasks=[]
    )
    
    # Import and test the tool directly
    from app.agents.tools import search_journal_entries_agent_tool
    from pydantic_ai import RunContext
    
    # Create a mock context
    class MockContext:
        def __init__(self, deps):
            self.deps = deps
    
    ctx = MockContext(deps)
    
    # Test direct tool calls
    print("\n1️⃣ Testing: Get most recent entry (no query)")
    result = await search_journal_entries_agent_tool(ctx, limit=1)
    print(f"Result: {result[:500]}...")
    
    print("\n2️⃣ Testing: Search by content")
    result = await search_journal_entries_agent_tool(ctx, query="Python", limit=5)
    print(f"Result: {result[:500]}...")
    
    print("\n3️⃣ Testing: Search by date range")
    date_from = (datetime.utcnow() - timedelta(days=2)).isoformat()
    result = await search_journal_entries_agent_tool(ctx, date_from=date_from, limit=5)
    print(f"Result: {result[:500]}...")


async def main():
    """Run all tests"""
    print("=" * 80)
    print("🧪 JOURNAL SEARCH FUNCTIONALITY TESTS")
    print("=" * 80)
    
    await test_direct_tool_call()
    await test_search_most_recent_journal()
    await test_search_journal_by_content()
    await test_search_journal_by_date()
    
    print("\n" + "=" * 80)
    print("✅ All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())