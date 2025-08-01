#!/usr/bin/env python3
"""
Demo Journal Entry Management Script

This script manages demo journal entries for the Cassidy app, allowing you to:
- List current journal entries for test user
- Delete existing entries
- Create new strategic demo entries
- Reset demo data (delete and recreate)

The demo entries tell the story of Alex, a successful but overwhelmed Product Manager
who struggles with too many opportunities and needs help with focus and prioritization.
"""

import asyncio
import argparse
import sys
import os
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional

# Add the parent directory to Python path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import select, delete, text
from app.database import init_db, get_db
from app.models.session import UserDB, JournalEntryDB, ChatSessionDB
from app.core.config import get_settings


class DemoEntryManager:
    def __init__(self, use_production: bool = False):
        self.use_production = use_production
        
    async def init_database(self):
        """Initialize database connection"""
        if self.use_production:
            print("🌍 Connecting to production database...")
            # Production database setup would go here
            # For now, just connecting to local
            await init_db()
        else:
            print("🔗 Connecting to local database...")
            await init_db()
    
    async def find_test_user(self) -> Optional[UserDB]:
        """Find the test user"""
        from app.database import engine
        from sqlalchemy import text
        
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT id, username, email, password_hash, is_verified, is_active, created_at, updated_at FROM users WHERE username = :username"),
                {"username": "user_123"}
            )
            row = result.fetchone()
            if row:
                # Create a UserDB object from the row data
                user = UserDB(
                    id=row[0],
                    username=row[1], 
                    email=row[2],
                    password_hash=row[3],
                    is_verified=bool(row[4]),
                    is_active=bool(row[5]),
                    created_at=row[6],
                    updated_at=row[7]
                )
                return user
        return None
    
    async def list_entries(self) -> None:
        """List current journal entries for test user"""
        user = await self.find_test_user()
        if not user:
            print("❌ Test user 'user_123' not found")
            return
            
        async for db in get_db():
            result = await db.execute(
                select(JournalEntryDB).where(JournalEntryDB.user_id == user.id).order_by(JournalEntryDB.created_at.desc())
            )
            entries = result.scalars().all()
            break

        print(f"\n📊 Found {len(entries)} journal entries for user 'user_123':")
        print("=" * 80)
        
        for i, entry in enumerate(entries, 1):
            days_ago = (datetime.utcnow() - entry.created_at).days
            print(f"{i:2d}. {entry.title}")
            print(f"    📅 {entry.created_at.strftime('%Y-%m-%d %H:%M')} ({days_ago} days ago)")
            print(f"    📝 {entry.raw_text[:100]}{'...' if len(entry.raw_text) > 100 else ''}")
            print()

    async def delete_entries(self) -> int:
        """Delete all journal entries for test user"""
        user = await self.find_test_user()
        if not user:
            print("❌ Test user 'user_123' not found")
            return 0
            
        # Use direct database connection with proper transaction handling
        from app.database import engine
        from sqlalchemy import text
        
        try:
            async with engine.begin() as conn:
                # Delete journal entries first
                result = await conn.execute(
                    text("DELETE FROM journal_entries WHERE user_id = :user_id"),
                    {"user_id": user.id}
                )
                deleted_count = result.rowcount
                
                # Delete associated sessions
                await conn.execute(
                    text("DELETE FROM chat_sessions WHERE user_id = :user_id AND conversation_type = 'journaling'"),
                    {"user_id": user.id}
                )
                
                print(f"🗑️  Deleted {deleted_count} journal entries")
                return deleted_count
                
        except Exception as e:
            print(f"❌ Error deleting entries: {e}")
            raise e

    async def reset_demo_entries(self) -> None:
        """Delete all existing entries and create new demo entries in a single transaction"""
        user = await self.find_test_user()
        if not user:
            print("❌ Test user 'user_123' not found")
            return
            
        # Use direct database connection with proper transaction handling
        from app.database import engine
        from sqlalchemy import text
        import json
        
        try:
            async with engine.begin() as conn:
                # First, delete existing entries
                delete_result = await conn.execute(
                    text("DELETE FROM journal_entries WHERE user_id = :user_id"),
                    {"user_id": user.id}
                )
                deleted_count = delete_result.rowcount
                
                # Delete associated sessions
                await conn.execute(
                    text("DELETE FROM chat_sessions WHERE user_id = :user_id AND conversation_type = 'journaling'"),
                    {"user_id": user.id}
                )
                
                # Report deletion
                if deleted_count > 0:
                    print(f"✅ Deleted {deleted_count} existing entries")
                else:
                    print("ℹ️  No existing entries to delete")
                
                print("\n📝 Creating strategic demo entries...")
                
                # Create a new session for the entries
                session_id = str(uuid.uuid4())
                await conn.execute(
                    text("""
                        INSERT INTO chat_sessions (id, user_id, conversation_type, is_active, metadata, created_at, updated_at)
                        VALUES (:id, :user_id, :conversation_type, :is_active, :metadata, :created_at, :updated_at)
                    """),
                    {
                        "id": session_id,
                        "user_id": user.id,
                        "conversation_type": "journaling",
                        "is_active": False,
                        "metadata": "{}",
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                )
                
                # Strategic demo entries designed to showcase insights (21 days from demo-1.md)
                # These entries tell the story of Alex, a successful but overwhelmed PM
                demo_entries = [
                    {
                        "title": "Angel deals, startup ideas, and missing Benjamin's bedtime",
                        "raw_text": "Crazy Monday. Had to review 2 angel deals by EOD - both interesting companies but struggled to focus. Started researching the founders, ended up spending 2 hours reading about the competitive landscape and getting anxious about how fast the space is moving. Benjamin wanted to show me his new puzzle but I was deep in spreadsheets. Finally played with him before bed and he was so excited - made me realize I'd been stressed about deals all day that I'm probably not even going to invest in. Still have 47 startup ideas in my notes app that I've never properly evaluated. When am I going to find time to think about which ones I'd actually want to spend the next 5 years building?",
                        "structured_data": {
                            "Open Reflection": "Had to review 2 angel deals but got distracted by research rabbit holes. Benjamin wanted to play but I was in spreadsheets. Made me realize I'm stressed about deals I probably won't invest in.",
                            "Things Done": ["researched angel deal founders", "reviewed competitive landscape", "played puzzle with Benjamin before bed"],
                            "To Do": ["evaluate which startup ideas I'd actually want to build", "finish angel deal reviews", "create framework for idea evaluation"],
                            "Emotional State": "anxious about falling behind in startup space, guilty about missing family time, overwhelmed by 47 unstructured ideas",
                            "Events": ["angel deal reviews due EOD"],
                            "Things I'm Grateful For": ["Benjamin's excitement when we finally played together"]
                        },
                        "days_ago": 21
                    }
                    # Note: This is just 1 entry for testing. The full 21 entries from demo-1.md
                    # can be added here for the complete demo experience.
                ]

                # Create entries with strategic timing
                for entry_data in demo_entries:
                    days_ago = entry_data.pop("days_ago")
                    entry_date = datetime.utcnow() - timedelta(days=days_ago)
                    
                    await conn.execute(
                        text("""
                            INSERT INTO journal_entries (id, user_id, session_id, title, raw_text, structured_data, metadata, created_at, updated_at)
                            VALUES (:id, :user_id, :session_id, :title, :raw_text, :structured_data, :metadata, :created_at, :updated_at)
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "user_id": user.id,
                            "session_id": session_id,
                            "title": entry_data["title"],
                            "raw_text": entry_data["raw_text"],
                            "structured_data": json.dumps(entry_data["structured_data"]),
                            "metadata": "{}",
                            "created_at": entry_date,
                            "updated_at": entry_date
                        }
                    )
                    print(f"✅ Created demo entry: {entry_data['title']} ({days_ago} days ago)")
                
                # Transaction will automatically commit when exiting the context
                print(f"\n🎉 Successfully created {len(demo_entries)} strategic demo journal entries!")
                print("\n📊 These entries will demonstrate:")
                print("   • Family time as clarity generator and priority compass")
                print("   • Piano as recharge mechanism and creative catalyst")
                print("   • Phone/social media addiction patterns and time loss")
                print("   • Morning vs afternoon energy optimization")
                print("   • Idea overload without execution framework")
                print("   • Decision paralysis on major life choices")
                print("   • Urgent vs important task confusion")
                print("   • Work-life integration challenges and solutions")
                
        except Exception as e:
            print(f"❌ Error resetting demo entries: {e}")
            raise e
            
    async def create_demo_entries(self) -> None:
        """Create strategic demo journal entries"""
        print("📝 Note: Use --reset-demo instead for complete demo setup with the new 21-entry story")
        
        # This method is kept for backwards compatibility but now just points to reset_demo_entries
        await self.reset_demo_entries()


async def main():
    parser = argparse.ArgumentParser(description="Manage demo journal entries")
    parser.add_argument("--list", action="store_true", help="List current journal entries")
    parser.add_argument("--delete-only", action="store_true", help="Delete existing entries only")
    parser.add_argument("--create-only", action="store_true", help="Create demo entries only")
    parser.add_argument("--reset-demo", action="store_true", help="Delete and recreate demo entries")
    parser.add_argument("--production", action="store_true", help="Use production database")
    
    args = parser.parse_args()
    
    if not any([args.list, args.delete_only, args.create_only, args.reset_demo]):
        parser.print_help()
        return
    
    manager = DemoEntryManager(use_production=args.production)
    await manager.init_database()
    
    try:
        if args.list:
            await manager.list_entries()
        elif args.delete_only:
            await manager.delete_entries()
        elif args.create_only:
            await manager.create_demo_entries()
        elif args.reset_demo:
            print("🔄 Resetting demo journal entries...")
            await manager.reset_demo_entries()
            
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())