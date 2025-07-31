"""Test journal search when user has no entries"""
import asyncio
import os

# Use test database
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test_journal_search_no_entries.db'

from app.database import init_db, get_db
from app.repositories.user import UserRepository
from app.agents.factory import AgentFactory
from app.agents.models import CassidyAgentDependencies


async def test_no_journal_entries():
    """Test when user has no journal entries"""
    
    # Initialize database
    await init_db()
    print("✅ Database initialized")
    
    async for db in get_db():
        user_repo = UserRepository()
        
        # Create test user WITHOUT any journal entries
        username = "test_user_no_journals"
        email = "test_no_journals@test.com"
        user = await user_repo.create_user(db, username, email, "dummy_hash")
        user_id = str(user.id)
        print(f"✅ Created user: {username} (ID: {user_id})")
        print("📝 Note: No journal entries created for this user")
        
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
        
        # Test the query when no entries exist
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
            else:
                print("\n✅ Response handled gracefully")
                
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
    print("🧪 TESTING JOURNAL SEARCH WITH NO ENTRIES")
    print("=" * 80)
    
    await test_no_journal_entries()
    
    # Cleanup test database
    try:
        os.remove("test_journal_search_no_entries.db")
        print("\n✅ Cleaned up test database")
    except:
        pass


if __name__ == "__main__":
    asyncio.run(main())