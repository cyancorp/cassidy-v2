#!/usr/bin/env python3
"""
Simple test for insights generation
"""

import asyncio
import json
from datetime import datetime, timedelta
from app.database import get_db
from app.models.session import JournalEntryDB
from app.models.user import UserDB
from app.services.insights_service import InsightsService
from app.agents.insights_formatter import InsightsFormatter
from sqlalchemy import select

async def create_test_data():
    """Create some test journal entries"""
    async for db in get_db():
        # Get the test user
        result = await db.execute(select(UserDB).where(UserDB.username == "user_123"))
        user = result.scalar_one_or_none()
        
        if not user:
            print("❌ Test user not found")
            return None
        
        # Create sample journal entries
        test_entries = [
            {
                "title": "Great day at work",
                "raw_text": "Had an amazing day at work today. Completed my project and felt really accomplished. Went for a run afterwards.",
                "structured_data": json.dumps({
                    "mood": {"current_mood": "happy", "energy_level": 8},
                    "activities": ["work", "exercise", "running"],
                    "tags": ["productivity", "fitness", "accomplishment"]
                }),
                "created_at": datetime.utcnow() - timedelta(days=1)
            },
            {
                "title": "Stressful meeting",
                "raw_text": "Had a difficult meeting with the client today. Feeling a bit anxious about the project timeline. Need to meditate tonight.",
                "structured_data": json.dumps({
                    "mood": {"current_mood": "anxious", "energy_level": 4},
                    "activities": ["work", "meeting", "meditation"],
                    "tags": ["stress", "work", "anxiety"]
                }),
                "created_at": datetime.utcnow() - timedelta(days=3)
            },
            {
                "title": "Weekend vibes",
                "raw_text": "Spent the weekend with family. Went hiking and had a picnic. Feeling grateful for good weather and time together.",
                "structured_data": json.dumps({
                    "mood": {"current_mood": "grateful", "energy_level": 7},
                    "activities": ["hiking", "family", "outdoor"],
                    "tags": ["family", "nature", "gratitude", "weekend"]
                }),
                "created_at": datetime.utcnow() - timedelta(days=5)
            },
            {
                "title": "Feeling tired",
                "raw_text": "Long day today. Didn't sleep well last night. Planning to go to bed early tonight and maybe take a yoga class tomorrow.",
                "structured_data": json.dumps({
                    "mood": {"current_mood": "tired", "energy_level": 3},
                    "activities": ["work", "yoga"],
                    "tags": ["sleep", "tired", "self-care"]
                }),
                "created_at": datetime.utcnow() - timedelta(days=7)
            }
        ]
        
        # Check if entries already exist
        existing = await db.execute(select(JournalEntryDB).where(JournalEntryDB.user_id == user.id))
        if existing.scalars().first():
            print("📝 Test entries already exist")
            return user
        
        # Create entries
        for entry_data in test_entries:
            entry = JournalEntryDB(
                user_id=user.id,
                **entry_data
            )
            db.add(entry)
        
        await db.commit()
        print(f"✅ Created {len(test_entries)} test journal entries")
        return user

async def test_insights():
    """Test insights generation"""
    print("🔍 Testing insights generation...\n")
    
    # Create test data
    user = await create_test_data()
    if not user:
        return
    
    # Generate insights
    async for db in get_db():
        insights_service = InsightsService()
        insights = await insights_service.generate_insights(user, db, days_back=30)
        
        # Format and display
        formatted = InsightsFormatter.format_insights(insights)
        print(formatted)
        
        break

if __name__ == "__main__":
    asyncio.run(test_insights())