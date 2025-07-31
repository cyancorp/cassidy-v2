"""Simple test to reproduce journal search issue"""
import asyncio
import os
from datetime import datetime, timedelta
import json

# Use test database
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test_journal_search_simple.db'

from app.database import init_db, get_db
from app.repositories.user import UserRepository
from app.repositories.session import JournalEntryRepository
from app.agents.factory import AgentFactory
from app.agents.models import CassidyAgentDependencies


async def test_journal_search_issue():
    """Test the specific issue: 'please find and summarize my most recent journal entry'"""
    
    # Initialize database
    await init_db()
    print("✅ Database initialized")
    
    async for db in get_db():
        user_repo = UserRepository()
        journal_repo = JournalEntryRepository()
        
        # Create test user
        username = "test_user_journal_search"
        email = "test_journal@test.com"
        user = await user_repo.create_user(db, username, email, "dummy_hash")
        user_id = str(user.id)
        print(f"✅ Created user: {username} (ID: {user_id})")
        
        # Create a test journal entry
        test_entry = await journal_repo.create(
            db,
            user_id=user_id,
            raw_text="Today was a great day. I finished my project and feel accomplished.",
            structured_data={
                "General Reflection": "Today was a great day",
                "Work Progress": "Finished my project",
                "Mood": "Accomplished and happy"
            },
            title="Great Day - Project Complete"
        )
        print(f"✅ Created journal entry: {test_entry.title}")
        
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
        print("✅ Agent created")
        
        # Test the problematic query
        query = "please find and summarize my most recent journal entry"
        print(f"\n📝 Testing query: '{query}'")
        
        try:
            print("Calling agent.run()...")
            result = await agent.run(query, deps=deps)
            print(f"\n🔍 Agent response:")
            print("-" * 80)
            print(result.output)
            print("-" * 80)
            
            # Check for errors
            if "error" in result.output.lower() or "❌" in result.output:
                print("\n❌ ERROR DETECTED in response!")
                
                # Try to understand what went wrong
                print("\n🔍 Debugging information:")
                print(f"User ID in context: {deps.user_id}")
                print(f"Conversation type: {deps.conversation_type}")
                
                # Test the tool directly
                from app.agents.tools import search_journal_entries_agent_tool
                from pydantic_ai import RunContext
                
                class MockContext:
                    def __init__(self, deps):
                        self.deps = deps
                
                ctx = MockContext(deps)
                print("\n🔧 Testing search tool directly...")
                tool_result = await search_journal_entries_agent_tool(ctx, limit=1)
                print(f"Direct tool result:\n{tool_result}")
                
            else:
                print("\n✅ SUCCESS - No error detected!")
                
        except Exception as e:
            print(f"\n❌ Exception occurred: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Cleanup
        await db.close()
        break


async def main():
    """Run the test"""
    print("=" * 80)
    print("🧪 TESTING JOURNAL SEARCH ISSUE")
    print("=" * 80)
    
    await test_journal_search_issue()
    
    # Cleanup test database
    try:
        os.remove("test_journal_search_simple.db")
        print("\n✅ Cleaned up test database")
    except:
        pass


if __name__ == "__main__":
    asyncio.run(main())