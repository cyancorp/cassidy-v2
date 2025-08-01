#!/usr/bin/env python3
"""
Manage Demo Journal Entries - Local and Production
==================================================

This script can:
1. Delete existing journal entries for the test user
2. Create strategic demo entries that showcase productivity insights
3. Work with both local SQLite and production PostgreSQL
4. Handle environment detection automatically

Usage:
    # Local development (uses local SQLite)
    uv run python scripts/manage_demo_entries.py --reset-demo
    
    # Production (uses AWS RDS PostgreSQL)
    uv run python scripts/manage_demo_entries.py --reset-demo --production
    
    # Just view current entries
    uv run python scripts/manage_demo_entries.py --list
    
    # Delete only (without adding new)
    uv run python scripts/manage_demo_entries.py --delete-only
"""

import asyncio
import json
import sys
import os
import argparse
from datetime import datetime, timedelta
from typing import Optional

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from app.database import get_db, init_db
from app.models.user import UserDB
from app.models.session import JournalEntryDB, ChatSessionDB
import uuid


class DemoEntryManager:
    """Manages demo journal entries for local and production environments"""
    
    def __init__(self, production_mode: bool = False):
        self.production_mode = production_mode
        
    async def initialize(self):
        """Initialize database connection"""
        if self.production_mode:
            # Production: Set environment variables for production database
            await self._setup_production_env()
        
        print(f"🔗 Connecting to {'production' if self.production_mode else 'local'} database...")
        
        # Use the app's database initialization
        await init_db()
        
    async def _setup_production_env(self):
        """Set up environment variables for production database"""
        try:
            import boto3
            
            # Get database endpoint from CloudFormation
            cf_client = boto3.client('cloudformation')
            
            response = cf_client.describe_stacks(StackName='CassidyBackendStack')
            stack_outputs = response['Stacks'][0]['Outputs']
            
            db_endpoint = None
            db_secret_arn = None
            
            for output in stack_outputs:
                if output['OutputKey'] == 'DatabaseEndpoint':
                    db_endpoint = output['OutputValue']
                elif output['OutputKey'] == 'DatabaseSecretArn':
                    db_secret_arn = output['OutputValue']
                    
            if not db_endpoint or not db_secret_arn:
                raise ValueError("Could not find database endpoint or secret ARN in stack outputs")
                
            # Get database credentials from Secrets Manager
            secrets_client = boto3.client('secretsmanager')
            secret_response = secrets_client.get_secret_value(SecretId=db_secret_arn)
            secret_data = json.loads(secret_response['SecretString'])
            
            username = secret_data['username']
            password = secret_data['password']
            
            # Set environment variable for the app to use
            database_url = f"postgresql+asyncpg://{username}:{password}@{db_endpoint}/cassidy"
            os.environ['DATABASE_URL'] = database_url
            
        except Exception as e:
            print(f"❌ Error connecting to production database: {e}")
            print("💡 Make sure you have AWS CLI configured and access to the production stack")
            sys.exit(1)
            
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
                select(JournalEntryDB)
                .where(JournalEntryDB.user_id == user.id)
                .order_by(JournalEntryDB.created_at.desc())
            )
            entries = result.scalars().all()
            break  # Exit the async generator
            
        if not entries:
            print("📝 No journal entries found for test user")
            return
            
        print(f"\n📊 Found {len(entries)} journal entries for user '{user.username}':")
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
                    # Additional 20 entries would be added here for full demo
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
                            "insights": ["More than 4 meetings kills productivity", "Need buffer time between meetings"]
                        },
                        "days_ago": 12
                    },
                    {
                        "title": "Morning workout and mindful start to the day",
                        "raw_text": "Started the day perfectly with a 45-minute workout followed by 15 minutes of meditation. The difference in my mental clarity and energy is incredible compared to days when I skip exercise. Had a healthy breakfast and took time to thoughtfully plan my top 3 priorities for the day. I feel calm, energized, and ready to tackle whatever comes my way. This morning routine is becoming a game-changer for my overall performance and well-being.",
                        "structured_data": {
                            "mood": {"current_mood": "calm", "energy_level": 8, "mental_clarity": 9},
                            "activities": ["morning workout", "meditation", "healthy breakfast", "daily planning"],
                            "tasks_completed": ["45-min strength training", "15-min meditation", "Planned top 3 priorities"],
                            "physical_state": {"workout_duration": 45, "workout_type": "strength_training", "meditation_duration": 15},
                            "tags": ["morning routine", "exercise", "meditation", "wellness", "planning"],
                            "productivity_score": 8,
                            "work_type": "self_care_and_planning",
                            "wellness_activities": ["exercise", "meditation", "healthy_eating"]
                        },
                        "days_ago": 11
                    },
                    {
                        "title": "Weekly review and learning synthesis",
                        "raw_text": "Spent the afternoon doing my weekly review and I'm feeling really satisfied with the progress. Delivered the first major milestone on the project, learned a new framework that's already proving useful, and significantly improved our team communication processes. It's amazing how documenting these wins boosts my motivation. Also spent time planning next week's priorities which always helps reduce Monday morning stress. The weekly review practice is becoming one of my most valuable habits.",
                        "structured_data": {
                            "mood": {"current_mood": "satisfied", "energy_level": 7, "motivation_level": 8},
                            "activities": ["weekly review", "goal assessment", "learning summary", "planning"],
                            "tasks_completed": ["Completed weekly review", "Updated OKRs", "Planned next week priorities"],
                            "accomplishments": ["Delivered first milestone", "Learned new framework", "Improved team communication"],
                            "tags": ["weekly review", "reflection", "goal tracking", "learning", "planning"],
                            "productivity_score": 8,
                            "work_type": "reflection_and_planning",
                            "goal_progress": {"milestone_completion": "first_major_milestone", "learning_goals": "new_framework_mastery"}
                        },
                        "days_ago": 10
                    },
                    {
                        "title": "Quality time with friends and creative pursuits",
                        "raw_text": "Had such a wonderful evening with friends! We went out for dinner, played some board games, and I spent some time on my photography hobby. It's incredible how much these social connections and creative outlets restore my energy and inspire new ideas. Even managed to do some reading before bed. These weekend boundaries and social activities seem to improve my Monday motivation significantly. Feeling grateful for good friends and the space to pursue creative interests.",
                        "structured_data": {
                            "mood": {"current_mood": "joyful", "energy_level": 8, "social_satisfaction": 9},
                            "activities": ["dinner with friends", "board games", "photography", "reading"],
                            "social_connections": ["quality_friend_time", "shared_activities"],
                            "creative_activities": ["photography", "reading"],
                            "tags": ["social connection", "creativity", "friendship", "hobbies", "work-life balance"],
                            "work_type": "social_and_creative",
                            "wellbeing_score": 9
                        },
                        "days_ago": 9
                    },
                    {
                        "title": "Technical setbacks and problem-solving under pressure",
                        "raw_text": "Woke up to a production issue that needed immediate attention. Spent the morning debugging under pressure with a tight deadline and unclear requirements. It was stressful, but I'm proud of how I handled it - broke the problem into smaller pieces, coordinated effectively with the team, and systematically worked through solutions. Successfully identified the root cause and implemented a hotfix. Communicated transparently with stakeholders throughout. These high-pressure situations are getting easier to handle as I gain more experience.",
                        "structured_data": {
                            "mood": {"current_mood": "stressed but resilient", "energy_level": 6, "stress_level": 8},
                            "activities": ["debugging", "crisis management", "team coordination", "stakeholder communication"],
                            "challenges": ["Production issue", "Tight deadline", "Unclear requirements", "High pressure"],
                            "tasks_completed": ["Identified root cause", "Implemented hotfix", "Coordinated team response", "Stakeholder communication"],
                            "tags": ["problem solving", "crisis management", "debugging", "teamwork", "resilience"],
                            "productivity_score": 7,
                            "work_type": "crisis_management",
                            "stress_management": ["problem_breakdown", "team_coordination", "systematic_approach"]
                        },
                        "days_ago": 7
                    },
                    {
                        "title": "Online course progress and skill development",
                        "raw_text": "Had a great evening focused on learning! Completed 3 modules of my online course and immediately applied the concepts by building a small practice project. The evening learning sessions are really working well for me - my brain seems more receptive to new information after work. Applied some of the new concepts I learned directly to work tasks, which really reinforced the learning. Taking structured notes and building practical examples is boosting my confidence with the new skills.",
                        "structured_data": {
                            "mood": {"current_mood": "curious", "energy_level": 7, "learning_satisfaction": 8},
                            "activities": ["online course", "practice coding", "note-taking", "concept application"],
                            "tasks_completed": ["Completed 3 course modules", "Built practice project", "Applied concepts to work"],
                            "learning_activities": {"course_modules": 3, "practice_project": 1, "concept_application": "work_integration"},
                            "tags": ["learning", "skill development", "evening study", "practical application"],
                            "productivity_score": 8,
                            "work_type": "learning_and_development",
                            "learning_effectiveness": "high_due_to_immediate_application"
                        },
                        "days_ago": 6
                    },
                    {
                        "title": "Productive day with healthy boundaries",
                        "raw_text": "This was one of those ideal days where everything felt balanced and sustainable. Had focused work in the morning, took an actual lunch break with a walk outside, finished a major feature in the afternoon, spent time mentoring a junior colleague, and then had quality family time in the evening including cooking dinner together. The clear boundaries between work and personal time seem to improve both domains. The lunch break walk definitely boosted my afternoon productivity.",
                        "structured_data": {
                            "mood": {"current_mood": "balanced", "energy_level": 8, "satisfaction_level": 9},
                            "activities": ["focused work", "lunch break walk", "mentoring", "family time", "cooking"],
                            "tasks_completed": ["Major feature completion", "Team mentoring session", "Quality family dinner"],
                            "work_life_balance": {"clear_boundaries": True, "lunch_break": True, "family_time": True},
                            "tags": ["work-life balance", "boundaries", "mentoring", "family", "productivity"],
                            "productivity_score": 9,
                            "work_type": "balanced_productivity",
                            "boundary_effectiveness": "high_satisfaction_both_domains"
                        },
                        "days_ago": 5
                    },
                    {
                        "title": "Sprint retrospective and strategic planning",
                        "raw_text": "What an amazing end to the sprint! We delivered all our goals and our team velocity increased by 25% compared to last sprint. Facilitated a really productive retrospective where we identified what's working well and areas for improvement. Spent time planning the next quarter and feeling optimistic about our trajectory. This was our best sprint performance yet and stakeholder satisfaction is at an all-time high. Celebrated the wins with the team. It's clear that consistent daily progress beats heroic last-minute efforts.",
                        "structured_data": {
                            "mood": {"current_mood": "accomplished", "energy_level": 8, "team_satisfaction": 9},
                            "activities": ["sprint review", "retrospective", "strategic planning", "team celebration"],
                            "tasks_completed": ["Delivered all sprint goals", "Facilitated team retrospective", "Planned next quarter"],
                            "accomplishments": ["Best sprint performance", "25% velocity increase", "High stakeholder satisfaction"],
                            "team_performance": {"velocity_increase": "25%", "goal_completion": "100%", "stakeholder_satisfaction": "high"},
                            "tags": ["sprint completion", "team performance", "retrospective", "strategic planning", "celebration"],
                            "productivity_score": 9,
                            "work_type": "strategic_and_reflective",
                            "key_insight": "consistent_daily_progress_beats_heroic_efforts"
                        },
                        "days_ago": 3
                    }
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
                print("   • Productivity pattern recognition (peak times, energy drains)")
                print("   • Mood-activity correlations (exercise → clarity, meetings → fatigue)")
                print("   • Work-life balance insights (boundaries improve both domains)")
                print("   • Stress management patterns (structured approaches reduce overwhelm)")
                print("   • Learning optimization (evening study, immediate application)")
                print("   • Goal tracking and achievement recognition")
                print("   • Team collaboration impact on motivation")
                print("   • Wellness-performance connections")
                
        except Exception as e:
            print(f"❌ Error resetting demo entries: {e}")
            raise e
            
    async def create_demo_entries(self) -> None:
        """Create strategic demo journal entries"""
        user = await self.find_test_user()
        if not user:
            print("❌ Test user 'user_123' not found")
            return
            
        async for db in get_db():
            try:
                # Create a session for the entries
                session_obj = ChatSessionDB(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    conversation_type="journaling",
                    is_active=False
                )
                db.add(session_obj)
                
                # Strategic demo entries designed to showcase insights
                demo_entries = [
                {
                    "title": "New project launch and team alignment",
                    "raw_text": "Started an exciting new project today! Had a great kickoff meeting with the team where we aligned on goals and created our roadmap. I'm feeling energized about the challenges ahead, though there's a bit of nervousness about the tight deadline. Set up our communication channels and defined clear success metrics. The team seems motivated and I love that we're all on the same page. Need to research competitor analysis and schedule stakeholder interviews this week. Also want to start working on wireframes soon.",
                    "structured_data": {
                        "mood": {"current_mood": "excited", "energy_level": 8, "stress_level": 3},
                        "activities": ["team meeting", "project planning", "goal setting", "documentation", "team alignment"],
                        "tasks_completed": ["Created project roadmap", "Set up team channels", "Defined success metrics"],
                        "tasks_pending": ["Research competitor analysis", "Schedule stakeholder interviews", "Create wireframes"],
                        "tags": ["project management", "teamwork", "goal setting", "planning", "new beginnings"],
                        "productivity_score": 8,
                        "social_interactions": ["team meeting", "collaborative planning"],
                        "work_type": "planning_and_coordination"
                    },
                    "days_ago": 14
                },
                {
                    "title": "Focused coding session and breakthrough moment", 
                    "raw_text": "Had an incredible afternoon of deep work today! Spent 4 straight hours between 2-6 PM working on the core algorithm and finally had a breakthrough. The solution clicked and I was able to implement the entire feature, including unit tests. There's something magical about those uninterrupted coding sessions where everything just flows. I feel so accomplished and energized. This reinforces that my peak focus time is definitely in the afternoon. Need to protect these time blocks better.",
                    "structured_data": {
                        "mood": {"current_mood": "accomplished", "energy_level": 9, "focus_level": 9},
                        "activities": ["coding", "debugging", "algorithm design", "unit testing", "deep work"],
                        "tasks_completed": ["Solved complex algorithm issue", "Implemented core feature", "Wrote comprehensive unit tests"],
                        "time_insights": "Peak productivity 2-6 PM, deep work session of 4 hours",
                        "tags": ["deep work", "coding", "breakthrough", "flow state", "problem solving"],
                        "productivity_score": 9,
                        "work_type": "technical_development",
                        "focus_blocks": [{"start": "14:00", "end": "18:00", "type": "deep_work", "effectiveness": 9}]
                    },
                    "days_ago": 13
                },
                {
                    "title": "Back-to-back meetings and context switching chaos",
                    "raw_text": "What a draining day. Had 6 meetings back-to-back from 9 AM to 4 PM with barely any breaks. By the afternoon I felt completely scattered and couldn't focus on anything meaningful. Spent most of the time between meetings just responding to urgent emails and doing quick status updates. Feel like I was in reactive mode all day instead of making real progress. Really need to find a better balance between collaboration and actual work time. The constant context switching is killing my productivity.",
                    "structured_data": {
                        "mood": {"current_mood": "drained", "energy_level": 4, "stress_level": 7},
                        "activities": ["meetings", "emails", "status updates", "context switching"],
                        "tasks_completed": ["Attended 6 meetings", "Responded to urgent emails", "Updated project status"],
                        "challenges": ["No time for deep work", "Constant interruptions", "Meeting fatigue"],
                        "tags": ["meeting overload", "context switching", "productivity drain", "communication"],
                        "productivity_score": 3,
                        "meeting_count": 6,
                        "work_type": "meetings_and_communication",
                        "insights": ["More than 4 meetings kills productivity", "Need buffer time between meetings"]
                    },
                    "days_ago": 12
                },
                {
                    "title": "Morning workout and mindful start to the day",
                    "raw_text": "Started the day perfectly with a 45-minute workout followed by 15 minutes of meditation. The difference in my mental clarity and energy is incredible compared to days when I skip exercise. Had a healthy breakfast and took time to thoughtfully plan my top 3 priorities for the day. I feel calm, energized, and ready to tackle whatever comes my way. This morning routine is becoming a game-changer for my overall performance and well-being.",
                    "structured_data": {
                        "mood": {"current_mood": "calm", "energy_level": 8, "mental_clarity": 9},
                        "activities": ["morning workout", "meditation", "healthy breakfast", "daily planning"],
                        "tasks_completed": ["45-min strength training", "15-min meditation", "Planned top 3 priorities"],
                        "physical_state": {"workout_duration": 45, "workout_type": "strength_training", "meditation_duration": 15},
                        "tags": ["morning routine", "exercise", "meditation", "wellness", "planning"],
                        "productivity_score": 8,
                        "work_type": "self_care_and_planning",
                        "wellness_activities": ["exercise", "meditation", "healthy_eating"]
                    },
                    "days_ago": 11
                },
                {
                    "title": "Weekly review and learning synthesis",
                    "raw_text": "Spent the afternoon doing my weekly review and I'm feeling really satisfied with the progress. Delivered the first major milestone on the project, learned a new framework that's already proving useful, and significantly improved our team communication processes. It's amazing how documenting these wins boosts my motivation. Also spent time planning next week's priorities which always helps reduce Monday morning stress. The weekly review practice is becoming one of my most valuable habits.",
                    "structured_data": {
                        "mood": {"current_mood": "satisfied", "energy_level": 7, "motivation_level": 8},
                        "activities": ["weekly review", "goal assessment", "learning summary", "planning"],
                        "tasks_completed": ["Completed weekly review", "Updated OKRs", "Planned next week priorities"],
                        "accomplishments": ["Delivered first milestone", "Learned new framework", "Improved team communication"],
                        "tags": ["weekly review", "reflection", "goal tracking", "learning", "planning"],
                        "productivity_score": 8,
                        "work_type": "reflection_and_planning",
                        "goal_progress": {"milestone_completion": "first_major_milestone", "learning_goals": "new_framework_mastery"}
                    },
                    "days_ago": 10
                },
                {
                    "title": "Quality time with friends and creative pursuits",
                    "raw_text": "Had such a wonderful evening with friends! We went out for dinner, played some board games, and I spent some time on my photography hobby. It's incredible how much these social connections and creative outlets restore my energy and inspire new ideas. Even managed to do some reading before bed. These weekend boundaries and social activities seem to improve my Monday motivation significantly. Feeling grateful for good friends and the space to pursue creative interests.",
                    "structured_data": {
                        "mood": {"current_mood": "joyful", "energy_level": 8, "social_satisfaction": 9},
                        "activities": ["dinner with friends", "board games", "photography", "reading"],
                        "social_connections": ["quality_friend_time", "shared_activities"],
                        "creative_activities": ["photography", "reading"],
                        "tags": ["social connection", "creativity", "friendship", "hobbies", "work-life balance"],
                        "work_type": "social_and_creative",
                        "wellbeing_score": 9
                    },
                    "days_ago": 9
                },
                {
                    "title": "Technical setbacks and problem-solving under pressure",
                    "raw_text": "Woke up to a production issue that needed immediate attention. Spent the morning debugging under pressure with a tight deadline and unclear requirements. It was stressful, but I'm proud of how I handled it - broke the problem into smaller pieces, coordinated effectively with the team, and systematically worked through solutions. Successfully identified the root cause and implemented a hotfix. Communicated transparently with stakeholders throughout. These high-pressure situations are getting easier to handle as I gain more experience.",
                    "structured_data": {
                        "mood": {"current_mood": "stressed but resilient", "energy_level": 6, "stress_level": 8},
                        "activities": ["debugging", "crisis management", "team coordination", "stakeholder communication"],
                        "challenges": ["Production issue", "Tight deadline", "Unclear requirements", "High pressure"],
                        "tasks_completed": ["Identified root cause", "Implemented hotfix", "Coordinated team response", "Stakeholder communication"],
                        "tags": ["problem solving", "crisis management", "debugging", "teamwork", "resilience"],
                        "productivity_score": 7,
                        "work_type": "crisis_management",
                        "stress_management": ["problem_breakdown", "team_coordination", "systematic_approach"]
                    },
                    "days_ago": 7
                },
                {
                    "title": "Online course progress and skill development",
                    "raw_text": "Had a great evening focused on learning! Completed 3 modules of my online course and immediately applied the concepts by building a small practice project. The evening learning sessions are really working well for me - my brain seems more receptive to new information after work. Applied some of the new concepts I learned directly to work tasks, which really reinforced the learning. Taking structured notes and building practical examples is boosting my confidence with the new skills.",
                    "structured_data": {
                        "mood": {"current_mood": "curious", "energy_level": 7, "learning_satisfaction": 8},
                        "activities": ["online course", "practice coding", "note-taking", "concept application"],
                        "tasks_completed": ["Completed 3 course modules", "Built practice project", "Applied concepts to work"],
                        "learning_activities": {"course_modules": 3, "practice_project": 1, "concept_application": "work_integration"},
                        "tags": ["learning", "skill development", "evening study", "practical application"],
                        "productivity_score": 8,
                        "work_type": "learning_and_development",
                        "learning_effectiveness": "high_due_to_immediate_application"
                    },
                    "days_ago": 6
                },
                {
                    "title": "Productive day with healthy boundaries",
                    "raw_text": "This was one of those ideal days where everything felt balanced and sustainable. Had focused work in the morning, took an actual lunch break with a walk outside, finished a major feature in the afternoon, spent time mentoring a junior colleague, and then had quality family time in the evening including cooking dinner together. The clear boundaries between work and personal time seem to improve both domains. The lunch break walk definitely boosted my afternoon productivity.",
                    "structured_data": {
                        "mood": {"current_mood": "balanced", "energy_level": 8, "satisfaction_level": 9},
                        "activities": ["focused work", "lunch break walk", "mentoring", "family time", "cooking"],
                        "tasks_completed": ["Major feature completion", "Team mentoring session", "Quality family dinner"],
                        "work_life_balance": {"clear_boundaries": True, "lunch_break": True, "family_time": True},
                        "tags": ["work-life balance", "boundaries", "mentoring", "family", "productivity"],
                        "productivity_score": 9,
                        "work_type": "balanced_productivity",
                        "boundary_effectiveness": "high_satisfaction_both_domains"
                    },
                    "days_ago": 5
                },
                {
                    "title": "Sprint retrospective and strategic planning",
                    "raw_text": "What an amazing end to the sprint! We delivered all our goals and our team velocity increased by 25% compared to last sprint. Facilitated a really productive retrospective where we identified what's working well and areas for improvement. Spent time planning the next quarter and feeling optimistic about our trajectory. This was our best sprint performance yet and stakeholder satisfaction is at an all-time high. Celebrated the wins with the team. It's clear that consistent daily progress beats heroic last-minute efforts.",
                    "structured_data": {
                        "mood": {"current_mood": "accomplished", "energy_level": 8, "team_satisfaction": 9},
                        "activities": ["sprint review", "retrospective", "strategic planning", "team celebration"],
                        "tasks_completed": ["Delivered all sprint goals", "Facilitated team retrospective", "Planned next quarter"],
                        "accomplishments": ["Best sprint performance", "25% velocity increase", "High stakeholder satisfaction"],
                        "team_performance": {"velocity_increase": "25%", "goal_completion": "100%", "stakeholder_satisfaction": "high"},
                        "tags": ["sprint completion", "team performance", "retrospective", "strategic planning", "celebration"],
                        "productivity_score": 9,
                        "work_type": "strategic_and_reflective",
                        "key_insight": "consistent_daily_progress_beats_heroic_efforts"
                    },
                    "days_ago": 3
                }
                ]
                
                # Create entries with strategic timing
                for entry_data in demo_entries:
                    days_ago = entry_data.pop("days_ago")
                    entry_date = datetime.utcnow() - timedelta(days=days_ago)
                    
                    entry = JournalEntryDB(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        session_id=session_obj.id,
                        title=entry_data["title"],
                        raw_text=entry_data["raw_text"],
                        structured_data=entry_data["structured_data"],
                        created_at=entry_date,
                        updated_at=entry_date
                    )
                    db.add(entry)
                    print(f"✅ Created demo entry: {entry_data['title']} ({days_ago} days ago)")
                
                # Commit all entries
                await db.commit()
                print(f"\n🎉 Successfully created {len(demo_entries)} strategic demo journal entries!")
                print("\n📊 These entries will demonstrate:")
                print("   • Productivity pattern recognition (peak times, energy drains)")
                print("   • Mood-activity correlations (exercise → clarity, meetings → fatigue)")
                print("   • Work-life balance insights (boundaries improve both domains)")
                print("   • Stress management patterns (structured approaches reduce overwhelm)")
                print("   • Learning optimization (evening study, immediate application)")
                print("   • Goal tracking and achievement recognition")
                print("   • Team collaboration impact on motivation")
                print("   • Wellness-performance connections")
                break  # Exit the async generator
                
            except Exception as e:
                await db.rollback()
                print(f"❌ Error creating demo entries: {e}")
                raise e


async def main():
    parser = argparse.ArgumentParser(description='Manage demo journal entries for Cassidy AI')
    parser.add_argument('--production', action='store_true', 
                       help='Use production database (AWS RDS)')
    parser.add_argument('--reset-demo', action='store_true',
                       help='Delete existing entries and create new demo entries')
    parser.add_argument('--list', action='store_true',
                       help='List current journal entries')
    parser.add_argument('--delete-only', action='store_true',
                       help='Delete existing entries without creating new ones')
    
    args = parser.parse_args()
    
    if not any([args.reset_demo, args.list, args.delete_only]):
        parser.print_help()
        return
        
    manager = DemoEntryManager(production_mode=args.production)
    
    try:
        await manager.initialize()
        
        if args.list:
            await manager.list_entries()
            
        elif args.delete_only:
            print("🗑️  Deleting existing journal entries...")
            deleted = await manager.delete_entries()
            if deleted > 0:
                print(f"✅ Successfully deleted {deleted} entries")
            else:
                print("ℹ️  No entries to delete")
                
        elif args.reset_demo:
            print("🔄 Resetting demo journal entries...")
            await manager.reset_demo_entries()
            
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 