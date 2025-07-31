"""Test journal search returns structured data"""
import asyncio
import os
from datetime import datetime
import json

# Use test database
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test_journal_search_structured.db'

from app.database import init_db, get_db
from app.repositories.user import UserRepository
from app.repositories.session import JournalEntryRepository
from app.agents.factory import AgentFactory
from app.agents.models import CassidyAgentDependencies


async def test_structured_data_return():
    """Test that journal search returns structured data, not just raw text"""
    
    # Initialize database
    await init_db()
    print("✅ Database initialized")
    
    async for db in get_db():
        user_repo = UserRepository()
        journal_repo = JournalEntryRepository()
        
        # Create test user
        username = "test_user_structured"
        email = "test_structured@test.com"
        user = await user_repo.create_user(db, username, email, "dummy_hash")
        user_id = str(user.id)
        print(f"✅ Created user: {username} (ID: {user_id})")
        
        # Create journal entries with rich structured data
        test_entries = [
            {
                "title": "Productive Day with Multiple Insights",
                "raw_text": "Had a very productive day working on the new feature.",
                "structured_data": {
                    "General Reflection": "Productive day with great progress on the new feature",
                    "Work Progress": "Completed database schema, API endpoints, and unit tests",
                    "Mood": "Energized and focused",
                    "Goals": ["Finish feature by Friday", "Write documentation", "Deploy to staging"],
                    "Insights": "Breaking down complex tasks into smaller chunks really helps with productivity",
                    "Challenges": "Had some issues with async database connections but resolved them",
                    "Learning": ["Async programming patterns", "SQLAlchemy best practices"],
                    "Gratitude": "Thankful for the supportive team and good documentation"
                }
            },
            {
                "title": "Personal Growth Reflection",
                "raw_text": None,  # Test with no raw text, only structured data
                "structured_data": {
                    "Personal Reflection": "Feeling more confident in my abilities",
                    "Growth Areas": ["Public speaking", "Time management", "Technical writing"],
                    "Achievements": ["Gave first tech talk", "Mentored junior developer", "Contributed to open source"],
                    "Future Plans": "Continue building expertise in distributed systems",
                    "Mood": "Optimistic and motivated"
                }
            }
        ]
        
        for entry_data in test_entries:
            entry = await journal_repo.create(
                db,
                user_id=user_id,
                raw_text=entry_data["raw_text"],
                structured_data=entry_data["structured_data"],
                title=entry_data["title"]
            )
            print(f"✅ Created journal entry: {entry.title}")
        
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
        print("\n🤖 Creating agent...")
        agent = await AgentFactory.get_agent(
            conversation_type="general",
            user_id=user_id,
            context=deps
        )
        
        # Test queries that should return structured data
        test_queries = [
            "please find and summarize my most recent journal entry",
            "show me journal entries about work progress",
            "find entries where I mentioned goals"
        ]
        
        for query in test_queries:
            print(f"\n📝 Testing query: '{query}'")
            
            result = await agent.run(query, deps=deps)
            print(f"\n🔍 Agent response:")
            print("-" * 80)
            print(result.output)
            print("-" * 80)
            
            # Check if structured data is being shown
            if "Structured Content:" in result.output:
                print("✅ SUCCESS - Structured data is included in response!")
            else:
                print("⚠️  WARNING - Response may not include structured data")
        
        # Test the tool directly
        print("\n🔧 Testing search tool directly...")
        from app.agents.tools import search_journal_entries_agent_tool
        from pydantic_ai import RunContext
        
        class MockContext:
            def __init__(self, deps):
                self.deps = deps
        
        ctx = MockContext(deps)
        tool_result = await search_journal_entries_agent_tool(ctx, limit=2)
        print(f"\nDirect tool result:\n{tool_result}")
        
        if "Structured Content:" in tool_result:
            print("\n✅ Tool is returning structured data correctly!")
        else:
            print("\n❌ Tool is not returning structured data!")
        
        # Cleanup
        await db.close()
        break


async def main():
    """Run the test"""
    print("=" * 80)
    print("🧪 TESTING JOURNAL SEARCH STRUCTURED DATA RETURN")
    print("=" * 80)
    
    await test_structured_data_return()
    
    # Cleanup test database
    try:
        os.remove("test_journal_search_structured.db")
        print("\n✅ Cleaned up test database")
    except:
        pass


if __name__ == "__main__":
    asyncio.run(main())