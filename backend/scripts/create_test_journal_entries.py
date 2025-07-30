#!/usr/bin/env python3
"""
Create test journal entries for the test user
"""

import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy import select
from app.database import get_db, init_db
from app.models.user import UserDB
from app.models.session import JournalEntryDB, ChatSessionDB
import uuid

async def create_test_entries():
    """Create sample journal entries"""
    
    # Initialize database
    await init_db()
    
    async for db in get_db():
        try:
            # Find the test user
            result = await db.execute(
                select(UserDB).where(UserDB.username == "user_123")
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print("❌ Test user 'user_123' not found")
                return
                
            print(f"✅ Found user: {user.username} (ID: {user.id})")
            
            # Check if entries already exist
            existing_result = await db.execute(
                select(JournalEntryDB).where(JournalEntryDB.user_id == user.id).limit(1)
            )
            if existing_result.scalar_one_or_none():
                print("📝 Journal entries already exist for this user")
                return
            
            # Create a session for the entries
            session = ChatSessionDB(
                id=str(uuid.uuid4()),
                user_id=user.id,
                conversation_type="journaling",
                is_active=False
            )
            db.add(session)
            
            # Create sample entries
            entries = [
                {
                    "title": "Morning meditation and workout",
                    "raw_text": "Started the day with 20 minutes of meditation followed by a great workout at the gym. Feeling energized and ready to tackle my projects. The meditation really helped clear my mind.",
                    "structured_data": {
                        "mood": {"current_mood": "energized", "energy_level": 9},
                        "activities": ["meditation", "exercise", "gym"],
                        "tags": ["wellness", "morning routine", "fitness"]
                    },
                    "days_ago": 1
                },
                {
                    "title": "Productive work day",
                    "raw_text": "Had a really productive day at work. Finished the presentation for tomorrow's meeting and helped a colleague debug their code. Feeling accomplished but a bit tired now.",
                    "structured_data": {
                        "mood": {"current_mood": "accomplished", "energy_level": 6},
                        "activities": ["work", "coding", "helping others"],
                        "tags": ["productivity", "teamwork", "achievement"]
                    },
                    "days_ago": 2
                },
                {
                    "title": "Stressful deadline",
                    "raw_text": "Today was tough. Had a last-minute deadline change that threw off my entire schedule. Managed to get everything done but feeling pretty stressed and anxious about the quality.",
                    "structured_data": {
                        "mood": {"current_mood": "stressed", "energy_level": 4},
                        "activities": ["work", "deadline", "problem-solving"],
                        "tags": ["stress", "challenges", "time management"]
                    },
                    "days_ago": 3
                },
                {
                    "title": "Weekend nature hike",
                    "raw_text": "Went on a beautiful hike with friends today. The weather was perfect and we saw some amazing views. Really helped me disconnect from work stress and feel grateful for nature.",
                    "structured_data": {
                        "mood": {"current_mood": "grateful", "energy_level": 8},
                        "activities": ["hiking", "socializing", "nature"],
                        "tags": ["outdoors", "friends", "relaxation", "gratitude"]
                    },
                    "days_ago": 4
                },
                {
                    "title": "Cooking experiment",
                    "raw_text": "Tried a new recipe tonight - homemade pasta! It took longer than expected but turned out delicious. Feeling proud of trying something new, even if the kitchen is a mess now.",
                    "structured_data": {
                        "mood": {"current_mood": "proud", "energy_level": 7},
                        "activities": ["cooking", "learning", "creativity"],
                        "tags": ["food", "new experiences", "accomplishment"]
                    },
                    "days_ago": 5
                },
                {
                    "title": "Family video call",
                    "raw_text": "Had a long video call with family today. It's been a while since we all talked. Hearing about everyone's lives made me feel connected but also a bit homesick.",
                    "structured_data": {
                        "mood": {"current_mood": "nostalgic", "energy_level": 5},
                        "activities": ["family", "communication", "video call"],
                        "tags": ["relationships", "family", "connection"]
                    },
                    "days_ago": 7
                },
                {
                    "title": "Reading and reflection",
                    "raw_text": "Spent the evening reading and reflecting on my goals. Realized I need to be more intentional about work-life balance. The book about mindfulness is really resonating with me.",
                    "structured_data": {
                        "mood": {"current_mood": "thoughtful", "energy_level": 6},
                        "activities": ["reading", "reflection", "planning"],
                        "tags": ["self-improvement", "mindfulness", "goals"]
                    },
                    "days_ago": 10
                }
            ]
            
            # Create entries
            for entry_data in entries:
                days_ago = entry_data.pop("days_ago")
                entry_date = datetime.utcnow() - timedelta(days=days_ago)
                
                entry = JournalEntryDB(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    session_id=session.id,
                    title=entry_data["title"],
                    raw_text=entry_data["raw_text"],
                    structured_data=json.dumps(entry_data["structured_data"]),
                    created_at=entry_date,
                    updated_at=entry_date
                )
                db.add(entry)
                print(f"✅ Created entry: {entry_data['title']} ({days_ago} days ago)")
            
            # Commit all entries
            await db.commit()
            print(f"\n🎉 Successfully created {len(entries)} journal entries!")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            await db.rollback()
        finally:
            break

if __name__ == "__main__":
    asyncio.run(create_test_entries())