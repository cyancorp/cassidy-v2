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
from app.models.user import UserDB
from app.models.session import JournalEntryDB, ChatSessionDB


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

    async def create_alex_template(self, conn, user_id: str) -> None:
        """Create a custom journal template for Alex"""
        template_data = {
            "Summary": {
                "description": "A brief one-sentence summary of the key insight or main event from the entry",
                "aliases": ["Summary", "Key Point", "Main Takeaway"],
                "examples": ["Realized I stress over deals I won't invest in", "Phone addiction ruined family time until I put it away"]
            },
            "Open Reflection": {
                "description": "General thoughts, daily reflections, or free-form journaling content",
                "aliases": ["Daily Notes", "Journal", "Reflection", "General", "Thoughts"],
                "examples": ["reflecting on work-life balance", "thinking about productivity patterns"]
            },
            "Things Done": {
                "description": "Specific tasks completed, accomplishments, actions taken, or work already finished",
                "aliases": ["Completed", "Accomplishments", "Activities Completed", "Work Done", "Finished"],
                "examples": ["researched angel deal founders", "played puzzle with Benjamin", "attended team meeting"]
            },
            "To Do": {
                "description": "Future tasks, things to buy, errands to run, or actions that need to be taken",
                "aliases": ["Tasks", "Todo", "Need to do", "Action Items"],
                "examples": ["create framework for idea evaluation", "schedule strategic thinking in mornings"]
            },
            "Emotional State": {
                "description": "Emotional state, mood, thoughts, feelings, concerns, or personal reflections",
                "aliases": ["Emotions", "Mood", "Feelings", "Thoughts", "Personal"],
                "examples": ["anxious about falling behind", "guilty about missing family time", "excited about breakthrough"]
            },
            "Events": {
                "description": "Important events, meetings, appointments, dates, deadlines, or scheduled activities",
                "aliases": ["Schedule", "Meetings", "Appointments", "Calendar", "Deadlines"],
                "examples": ["angel deal reviews due EOD", "team meeting", "date night with Sarah"]
            },
            "Things I'm Grateful For": {
                "description": "Express gratitude for people, events, achievements, or circumstances in your life",
                "aliases": ["Gratitude", "Grateful", "Thankful", "Appreciation"],
                "examples": ["Benjamin's excitement when we played together", "Sarah's honest feedback"]
            },
            "Benjamin": {
                "description": "Memories, thoughts, feelings and plans relating to my son Benjamin",
                "aliases": ["Benjamin", "Son"],
                "examples": ["Benjamin said 'Daddy working?' when they returned", "Benjamin fell asleep on my chest while reading"]
            }
        }
        
        # Delete existing template for this user
        await conn.execute(
            text("DELETE FROM user_templates WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        
        # Create new template
        await conn.execute(
            text("""
                INSERT INTO user_templates (id, user_id, name, sections, is_active, created_at, updated_at)
                VALUES (:id, :user_id, :name, :sections, :is_active, :created_at, :updated_at)
            """),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": "Alex's PM Journal Template",
                "sections": json.dumps(template_data),
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        )
        print("✅ Created custom template for Alex")

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
                
                # First, create a custom template for Alex
                await self.create_alex_template(conn, user.id)
                
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
                            "Summary": "Got lost in angel deal research, missed family time, realized I stress over deals I won't invest in",
                            "Open Reflection": "Had to review 2 angel deals but got distracted by research rabbit holes. Benjamin wanted to play but I was in spreadsheets. Made me realize I'm stressed about deals I probably won't invest in.",
                            "Things Done": ["researched angel deal founders", "reviewed competitive landscape", "played puzzle with Benjamin before bed"],
                            "To Do": ["evaluate which startup ideas I'd actually want to build", "finish angel deal reviews", "create framework for idea evaluation"],
                            "Emotional State": "anxious about falling behind in startup space, guilty about missing family time, overwhelmed by 47 unstructured ideas",
                            "Events": ["angel deal reviews due EOD"],
                            "Things I'm Grateful For": ["Benjamin's excitement when we finally played together"]
                        },
                        "days_ago": 21
                    },
                    {
                        "title": "Great run, idea #48, and Sarah's reality check",
                        "raw_text": "Great run this morning, had another startup idea - #48 now. It's a good one about B2B subscription analytics, but honestly, do I even care about subscription analytics? Or am I just pattern matching from successful companies? No framework for filtering these ideas by what I'd actually enjoy working on vs what seems valuable. Sarah asked what I want for my birthday next month. Told her 'just some time to think through life stuff.' She pointed out I have evenings and weekends but I fill them with 'urgent' work that's not really urgent. She's right.",
                        "structured_data": {
                            "Summary": "Another startup idea during run, but questioning if I actually care about it. Sarah called out my fake urgency problem.",
                            "Open Reflection": "Had startup idea #48 during run about B2B subscription analytics. But do I even care about this space? Just pattern matching successful companies. Sarah called out that I have time but fill it with fake urgent work.",
                            "Things Done": ["morning run", "came up with startup idea #48"],
                            "To Do": ["create framework for filtering ideas by what I'd enjoy vs what seems valuable", "figure out what I actually want for birthday"],
                            "Emotional State": "confused about whether I actually care about my ideas, slightly defensive about time management",
                            "Things I'm Grateful For": ["Sarah's honest feedback", "good morning run for thinking"]
                        },
                        "days_ago": 20
                    },
                    {
                        "title": "Mom's call, dad's memory, and Twitter comparison spiral",
                        "raw_text": "Mom called worried about dad's memory issues. Spent my lunch break and another hour after work researching memory care facilities, but I'm no closer to knowing if we should move them closer. What information would actually help me make this decision? Keep getting lost in facility reviews instead of talking to them about what they want. Meanwhile, my team is waiting on the Q2 roadmap and I keep pushing it off. Told them EOD today but that's not happening. After Benjamin went to bed, spent an hour scrolling Twitter seeing all these founders crushing it. Makes me feel like I'm falling behind, but behind in what exactly?",
                        "structured_data": {
                            "Summary": "Mom called about dad's memory. Spent hours researching but not talking to them. Delayed team deliverables. Twitter spiral made me feel behind.",
                            "Open Reflection": "Mom called about dad's memory issues. Spent hours researching facilities but not talking to them about what they want. Team waiting on Q2 roadmap. Twitter makes me feel behind but behind in what?",
                            "Things Done": ["researched memory care facilities", "took mom's call about dad"],
                            "To Do": ["talk to parents about what they actually want", "finish Q2 roadmap for team", "stop scrolling Twitter"],
                            "Emotional State": "worried about dad's memory, guilty about delayed team deliverables, inadequate from social media comparison",
                            "Events": ["Q2 roadmap due to team"],
                            "Things I'm Grateful For": ["mom reaching out when she needs support"],
                            "Benjamin": "Benjamin went to bed while I was on Twitter - missed quality time with him"
                        },
                        "days_ago": 19
                    },
                    {
                        "title": "Todo list comedy: printer ink vs life decisions",
                        "raw_text": "Looked at my todo list today and laughed. 'Buy printer ink' - done. 'Schedule dentist' - done. 'Submit expense report' - done. But 'Figure out startup timeline'? Been there since January. 'Make decision on parents'? Three months. 'Create angel investing thesis'? Six months. I'm optimizing for quick wins instead of tackling the hard decisions. What do I actually need to know to move forward on these? Maybe that's the real question.",
                        "structured_data": {
                            "Summary": "Todo list reveals I optimize for trivial wins while big decisions languish for months. Need to tackle hard choices.",
                            "Open Reflection": "Looked at todo list and laughed. All the trivial stuff gets done but big decisions languish for months. Optimizing for quick wins instead of hard choices.",
                            "Things Done": ["bought printer ink", "scheduled dentist", "submitted expense report"],
                            "To Do": ["figure out startup timeline", "make decision on parents", "create angel investing thesis", "identify what info I need for big decisions"],
                            "Emotional State": "frustrated with my own procrastination, amused by the absurdity of my priorities",
                            "Events": ["dentist appointment scheduled"]
                        },
                        "days_ago": 18
                    },
                    {
                        "title": "Crushing Jake's enthusiasm and LinkedIn comparison trap",
                        "raw_text": "Rough team meeting. Jake presented a really thoughtful feature proposal and I picked it apart pretty harshly. Saw his enthusiasm drain away. I think I'm taking my frustration about my own indecision out on the team. They're doing great work and I'm being the bottleneck. After the meeting, spent an hour on LinkedIn looking at other PMs who became founders. The comparison game is toxic but I can't stop. Need to get off this hamster wheel.",
                        "structured_data": {
                            "Summary": "Crushed Jake's proposal too harshly, taking my indecision out on team. LinkedIn comparison spiral followed.",
                            "Open Reflection": "Rough team meeting. Crushed Jake's feature proposal too harshly. Taking my own indecision frustration out on team. They're doing great work, I'm the bottleneck. LinkedIn comparison game is toxic.",
                            "Things Done": ["attended team meeting", "reviewed Jake's feature proposal", "spent hour on LinkedIn"],
                            "To Do": ["apologize to Jake", "stop comparing myself to other founders", "get off social media hamster wheel"],
                            "Emotional State": "frustrated with my own indecision, guilty about being harsh with Jake, inadequate from LinkedIn comparisons",
                            "Events": ["team meeting"],
                            "Things I'm Grateful For": ["team doing great work despite my bottlenecking"]
                        },
                        "days_ago": 17
                    },
                    {
                        "title": "Phone addiction and train track breakthrough",
                        "raw_text": "Family Saturday but I checked my phone constantly. Sarah called me out when I said 'just need to check one thing' for the fifth time. When I finally put it in the other room and built a train track with Benjamin, I felt more present than I have all week. He was so happy to have my full attention. We played for two hours straight and I had more creative ideas than I do in most meetings. Maybe presence is the secret sauce?",
                        "structured_data": {
                            "Summary": "Phone addiction ruined family Saturday until I put it away. Two hours with Benjamin = more creative ideas than most meetings.",
                            "Open Reflection": "Family Saturday ruined by constant phone checking. Sarah called me out. When I finally put phone away and built trains with Benjamin, felt more present than all week. Had more creative ideas in 2 hours than most meetings.",
                            "Things Done": ["built train track with Benjamin", "had family Saturday time"],
                            "To Do": ["put phone in other room during family time", "maintain presence during weekends"],
                            "Emotional State": "guilty about phone addiction, joyful when present with Benjamin, creative and energized after family time",
                            "Things I'm Grateful For": ["Benjamin's happiness with my attention", "Sarah's honest feedback"],
                            "Benjamin": "Built train track with Benjamin for 2 hours - he was so happy to have my full attention"
                        },
                        "days_ago": 16
                    },
                    {
                        "title": "Piano homecoming and productivity guilt",
                        "raw_text": "Finally played piano tonight - first time in two months. Just 20 minutes but it felt like coming home. Sarah came in and listened, said she missed hearing me play. Then the guilt hit - should be reviewing those deals, working on startup ideas, planning parent stuff. But you know what? After playing, I actually solved a product problem that's been bugging me all week. Maybe taking breaks isn't unproductive after all?",
                        "structured_data": {
                            "Summary": "First piano in 2 months felt like coming home. Guilt hit about productivity, but solved work problem after playing.",
                            "Open Reflection": "Played piano for first time in 2 months. Felt like coming home. Sarah missed hearing me play. Guilt hit about not being productive, but after playing I solved a work problem that's been bugging me all week.",
                            "Things Done": ["played piano for 20 minutes", "solved product problem"],
                            "To Do": ["schedule regular piano time", "review angel deals", "work on startup ideas", "plan parent stuff"],
                            "Emotional State": "joyful while playing piano, guilty about 'unproductive' time, surprised by problem-solving breakthrough",
                            "Things I'm Grateful For": ["Sarah appreciating my music", "mental reset from piano", "unexpected work breakthrough"]
                        },
                        "days_ago": 15
                    },
                    {
                        "title": "LinkedIn addiction and afternoon strategy disasters",
                        "raw_text": "Interesting observation: looked back at my calendar and every 'strategic' decision I've scheduled after 2pm has been a disaster. But I keep putting important thinking time in the afternoon because mornings are 'for meetings.' Backwards. Also caught myself - opened LinkedIn 12 times before lunch. Each time was 'just for a second' but I'd emerge 20-30 minutes later feeling inadequate. The phone is becoming a problem.",
                        "structured_data": {
                            "Summary": "Realized strategic decisions after 2pm always fail, but I keep scheduling them there. LinkedIn opened 12 times before lunch.",
                            "Open Reflection": "Realized every strategic decision after 2pm is disaster but I keep scheduling thinking time in afternoon. Also opened LinkedIn 12 times before lunch - each time was 'just a second' but lost 20-30 minutes feeling inadequate.",
                            "Things Done": ["analyzed calendar patterns", "tracked LinkedIn usage"],
                            "To Do": ["schedule strategic thinking in mornings", "put phone away during work hours", "break LinkedIn addiction"],
                            "Emotional State": "frustrated with backward scheduling, concerned about phone addiction, inadequate from social media",
                            "Events": ["need to reschedule afternoon strategy sessions to morning"]
                        },
                        "days_ago": 14
                    },
                    {
                        "title": "Idea #49 and the listening correlation",
                        "raw_text": "Morning run, another idea (#49). Tried to voice memo it but spent 6 minutes explaining context and forgot the main point. But here's the thing - looking at my list, I don't even like half these ideas. I'm writing them down because they seem 'valuable' or 'scalable.' What if I only pursued ideas I'd be excited to work on even if they failed? That would eliminate like 40 of them instantly. Team meeting went well today - I mostly listened instead of talking. Correlation?",
                        "structured_data": {
                            "Summary": "Idea #49 on run but terrible capture. Don't even like half my ideas - just writing valuable-seeming ones. Team meeting went well when listening.",
                            "Open Reflection": "Had idea #49 on run but voice memo was terrible - explained context, forgot main point. Don't even like half my ideas - writing them because they seem valuable not because I care. Team meeting went well when I listened instead of talked.",
                            "Things Done": ["morning run", "had startup idea #49", "team meeting with listening approach"],
                            "To Do": ["filter ideas by what I'd be excited to work on even if they failed", "improve idea capture method", "continue listening more in meetings"],
                            "Emotional State": "frustrated with idea capture process, curious about connection between listening and team performance",
                            "Things I'm Grateful For": ["good team meeting when I listened more"]
                        },
                        "days_ago": 13
                    },
                    {
                        "title": "15 browser tabs and Benjamin's intervention",
                        "raw_text": "Dedicated 90 minutes to research parent care options. Still spinning wheels. I have 15 browser tabs open with facility comparisons but haven't asked mom and dad what they actually want. What would help me make a decision? Budget constraints? Their preferences? Timeline? Benjamin interrupted my research spiral wanting to play. After 20 minutes of playing, I realized I was overthinking this. Need to just talk to my parents directly.",
                        "structured_data": {
                            "Summary": "90 minutes researching parent care with 15 tabs open but still spinning. Benjamin's play interruption brought clarity - just talk to them.",
                            "Open Reflection": "Spent 90 minutes researching parent care, 15 browser tabs open but still spinning wheels. Haven't asked mom and dad what they want. Benjamin interrupted research to play - after 20 minutes realized I'm overthinking.",
                            "Things Done": ["researched parent care options for 90 minutes", "played with Benjamin for 20 minutes"],
                            "To Do": ["call parents directly about their preferences", "close browser tabs", "define decision criteria"],
                            "Emotional State": "frustrated with research rabbit holes, grateful for Benjamin's interruption, clearer after play time",
                            "Benjamin": "Benjamin interrupted my research spiral wanting to play - helped me realize I was overthinking"
                        },
                        "days_ago": 12
                    },
                    {
                        "title": "Overcorrection and the silent treatment",
                        "raw_text": "Tried new approach with team - be more collaborative. Overcorrected and agreed to feature requests we definitely can't deliver this quarter. There's a middle ground between dictatorial and pushover. Had an angel deal call during Benjamin's bedtime story time. Told Sarah 'just 15 minutes' but it went for an hour. She didn't say anything but the silence was loud. When I'm present with family, work problems feel manageable. When I'm distracted, everything feels urgent and nothing gets done well.",
                        "structured_data": {
                            "Summary": "Overcorrected to pushover with team, agreed to impossible features. Angel call during bedtime went long, Sarah's silence was loud.",
                            "Open Reflection": "Tried collaborative approach with team but overcorrected - agreed to impossible features. Middle ground between dictator and pushover exists somewhere. Angel call during Benjamin's bedtime went from 15 min to hour. Sarah's silence was loud.",
                            "Things Done": ["collaborative team approach", "angel deal call"],
                            "To Do": ["find middle ground with team", "protect family time boundaries", "learn to estimate call duration"],
                            "Emotional State": "confused about team management balance, guilty about missing bedtime, stressed when distracted",
                            "Events": ["Benjamin's bedtime story time"],
                            "Things I'm Grateful For": ["clarity that comes when present with family"],
                            "Benjamin": "Missed Benjamin's bedtime story for angel call that went long"
                        },
                        "days_ago": 11
                    },
                    {
                        "title": "49 ideas, zero validation, inbox zero",
                        "raw_text": "Did an audit: 49 startup ideas, zero validated. 6 angel deals 'considering,' only 1 I'm genuinely excited about. 23 books on my 'must read' list, finished 0 this year. But my email is at inbox zero! Clearly focusing on the wrong metrics. Maybe what I need isn't more ideas but a thought partner? Someone who's good at execution while I'm good at vision? Or maybe I just need to pick ONE idea based on what energizes me, not what might have the biggest exit.",
                        "structured_data": {
                            "Summary": "Audit reveals terrible metrics: 49 ideas/0 validated, 6 deals/1 exciting, 23 books/0 read, but inbox zero. Wrong focus.",
                            "Open Reflection": "Audit results: 49 startup ideas/0 validated, 6 angel deals/1 exciting, 23 must-read books/0 finished, but inbox zero! Wrong metrics. Maybe need thought partner for execution or just pick ONE idea that energizes me.",
                            "Things Done": ["completed personal audit", "achieved inbox zero"],
                            "To Do": ["validate at least one startup idea", "pick one exciting angel deal", "read one book from list", "find thought partner or pick one energizing idea"],
                            "Emotional State": "frustrated with lack of follow-through, amused by misplaced priorities, hopeful about potential solutions"
                        },
                        "days_ago": 10
                    },
                    {
                        "title": "Twitter paralysis and 'Daddy working?'",
                        "raw_text": "Good morning - wrote in my journal for 30 minutes straight, felt amazing. Then 'quickly' checked Twitter. Two hours gone. Saw three announcements of startups doing variations of my ideas. Instead of motivating me, it paralyzed me. Sarah took Benjamin to the park and I said I'd catch up after 'one email.' Never made it to the park. They came back and Benjamin said 'Daddy working?' - he's starting to notice patterns. That hurt.",
                        "structured_data": {
                            "Summary": "Great 30-min journaling then 'quick' Twitter check = 2 hours gone. Missed park with family. Benjamin's 'Daddy working?' hurt.",
                            "Open Reflection": "Great 30-min journal session then 'quickly' checked Twitter - 2 hours gone. Saw startups doing my ideas, paralyzed instead of motivated. Missed park with family for 'one email.' Benjamin said 'Daddy working?' - he's noticing patterns.",
                            "Things Done": ["30 minutes of journaling", "checked Twitter for 2 hours"],
                            "To Do": ["stop checking Twitter", "prioritize family park time", "turn off social media notifications"],
                            "Emotional State": "proud of journaling, frustrated with Twitter time loss, hurt by Benjamin's observation",
                            "Things I'm Grateful For": ["good morning journaling session"],
                            "Benjamin": "Benjamin said 'Daddy working?' when they returned from park - he's noticing I'm always working"
                        },
                        "days_ago": 9
                    },
                    {
                        "title": "Digital noise drowning out what matters",
                        "raw_text": "Tried to play piano but kept getting Slack notifications. Not urgent ones - someone sharing an article, team chatting about weekend plans. But each one pulled me out of the music. Finally turned phone to airplane mode. Played for 45 minutes. Sarah brought me tea, Benjamin danced to the music. This is what weekends should be. Why do I let the digital noise drown out what matters?",
                        "structured_data": {
                            "Summary": "Slack notifications ruined piano until airplane mode. 45 min of music with Sarah's tea and Benjamin dancing = perfect weekend.",
                            "Open Reflection": "Tried piano but Slack notifications kept interrupting - not urgent stuff, just noise. Finally airplane mode. Played 45 min. Sarah brought tea, Benjamin danced. This is what weekends should be. Why let digital noise drown out what matters?",
                            "Things Done": ["played piano for 45 minutes", "turned phone to airplane mode"],
                            "To Do": ["use airplane mode during weekend family time", "turn off non-urgent notifications", "protect weekend boundaries"],
                            "Emotional State": "frustrated with digital interruptions, peaceful during uninterrupted piano time, questioning priorities",
                            "Things I'm Grateful For": ["Sarah bringing tea", "Benjamin dancing to music", "peaceful family moments"],
                            "Benjamin": "Benjamin danced to my piano music - pure joy"
                        },
                        "days_ago": 8
                    },
                    {
                        "title": "23-minute breakthrough and evening presence",
                        "raw_text": "Experiment: blocked 6-8am for 'creative thinking,' no phone allowed. Only lasted until 6:23am before checking email. But those 23 minutes? Had my clearest thinking in weeks. Mapped out a framework for evaluating my startup ideas. Afternoon was all meetings and admin - actually perfect for my lower energy. Why have I been fighting my natural rhythm? Evening with family, no phone at dinner. Benjamin told a whole story about his day. I actually heard it.",
                        "structured_data": {
                            "Summary": "Only lasted 23 min of phone-free morning but clearest thinking in weeks. Mapped startup framework. Benjamin told whole story at dinner.",
                            "Open Reflection": "Blocked 6-8am for creative thinking, lasted 23 min before checking email. But those 23 min = clearest thinking in weeks. Mapped startup evaluation framework. Afternoon meetings perfect for lower energy. Evening no phone - Benjamin told whole story.",
                            "Things Done": ["23 minutes of creative thinking", "mapped startup evaluation framework", "family dinner without phone"],
                            "To Do": ["extend morning creative time", "schedule meetings in afternoon", "maintain phone-free dinners"],
                            "Emotional State": "excited about morning breakthrough, aligned with natural rhythm, present and connected during dinner",
                            "Things I'm Grateful For": ["clarity from phone-free morning", "Benjamin sharing his day"],
                            "Benjamin": "Benjamin told a whole story about his day at dinner - I actually heard every word"
                        },
                        "days_ago": 7
                    },
                    {
                        "title": "Trains over deals and the saying no problem",
                        "raw_text": "Workout revelation: I don't have an angel deal evaluation problem, I have a saying no problem. Every 'quick call' turns into 2-hour due diligence because I can't admit early it's not a fit. Need a framework: only invest in industries I understand and founders I'd want to work with. That eliminates 4 of the 6 current deals. Benjamin said 'Daddy play trains?' right as I was about to take a call. Chose trains. Deal can wait.",
                        "structured_data": {
                            "Summary": "Workout revelation: saying no problem, not evaluation problem. Quick calls become 2-hour diligence. Chose trains over deal call.",
                            "Open Reflection": "Workout revelation: don't have evaluation problem, have saying no problem. Quick calls become 2-hour diligence because can't admit early it's not a fit. Benjamin wanted trains right as call was starting. Chose trains.",
                            "Things Done": ["morning workout", "played trains with Benjamin", "skipped angel deal call"],
                            "To Do": ["create angel investment framework", "practice saying no early", "only invest in industries I understand"],
                            "Emotional State": "enlightened about real problem, proud of choosing family, confident in decision",
                            "Things I'm Grateful For": ["workout clarity", "Benjamin's perfect timing"],
                            "Benjamin": "Benjamin said 'Daddy play trains?' right as I was about to take a call - chose trains, deal can wait"
                        },
                        "days_ago": 6
                    },
                    {
                        "title": "One conversation beats three months of research",
                        "raw_text": "Put 'parent planning' on calendar 10-11am. Actually used it to call them and ask direct questions. Mom was surprised but grateful. They want to stay in their home as long as possible but are open to moving closer in a year. There - more progress in one conversation than three months of research. Team shipped a feature while I was on parent call. They didn't need me hovering. Interesting.",
                        "structured_data": {
                            "Summary": "One parent call = more progress than 3 months research. They want to stay home but open to move in a year. Team shipped without me.",
                            "Open Reflection": "Put parent planning on calendar 10-11am, actually called them. Mom surprised but grateful. Want to stay home as long as possible, open to moving closer in a year. More progress in one conversation than 3 months research. Team shipped feature without me.",
                            "Things Done": ["called parents about care planning", "had direct conversation about their preferences"],
                            "To Do": ["explore timeline for potential move in one year", "research options near our location", "trust team more"],
                            "Emotional State": "relieved to have clarity, grateful for parents' openness, surprised by team's capability",
                            "Events": ["parent planning call 10-11am"],
                            "Things I'm Grateful For": ["parents being open about preferences", "team's independence"]
                        },
                        "days_ago": 5
                    },
                    {
                        "title": "Jake leads and moments that matter",
                        "raw_text": "Team crushed the sprint demo. I mostly stayed quiet and let Jake lead. He's ready for more responsibility. If I delegate better, I could free up 5-6 hours per week. For what though? That's the real question. Had startup idea during team celebration - didn't write it down. Not because I forgot, but because it wasn't that good. Growth? Benjamin and I read books before bed. He fell asleep on my chest. These moments matter more than any cap table.",
                        "structured_data": {
                            "Summary": "Team crushed demo with Jake leading. Could delegate 5-6 hours but for what? Benjamin fell asleep on my chest reading - matters more than cap tables.",
                            "Open Reflection": "Team crushed sprint demo, Jake led while I stayed quiet. He's ready for more responsibility. Could free up 5-6 hours by delegating - but for what? Had startup idea during celebration, didn't write it down because it wasn't good. Benjamin fell asleep on my chest reading.",
                            "Things Done": ["attended sprint demo", "let Jake lead", "read bedtime books with Benjamin"],
                            "To Do": ["delegate more to Jake", "figure out what to do with freed up time", "continue bedtime reading routine"],
                            "Emotional State": "proud of Jake's growth, questioning what matters, peaceful during bedtime routine",
                            "Things I'm Grateful For": ["Jake's development", "Benjamin falling asleep on my chest"],
                            "Benjamin": "Benjamin fell asleep on my chest while reading - these moments matter more than any cap table"
                        },
                        "days_ago": 4
                    },
                    {
                        "title": "What do you want? and the noise question",
                        "raw_text": "Date night with Sarah. She asked what I really want from life. Started rambling about startup potential and market opportunities. She stopped me: 'Not what could be successful. What do you want?' Sat in silence for a bit. Finally said: 'I want Benjamin to have a dad who's present. Want you to have a husband who's not always stressed. Want to build something I'm proud of, even if it's not a unicorn.' She smiled. 'Then why all the noise?' Good question.",
                        "structured_data": {
                            "Summary": "Date night clarity: want to be present dad, unstressed husband, build something I'm proud of. Sarah: 'Then why all the noise?'",
                            "Open Reflection": "Date night. Sarah asked what I really want. Started rambling about startups. She said 'Not what could be successful. What do YOU want?' Finally said: present dad, unstressed husband, build something I'm proud of even if not unicorn. 'Then why all the noise?'",
                            "Things Done": ["date night with Sarah", "had meaningful conversation about life goals"],
                            "To Do": ["reduce the noise", "focus on being present", "build something I'm proud of"],
                            "Emotional State": "initially defensive, then vulnerable, finally clear about real wants",
                            "Events": ["date night with Sarah"],
                            "Things I'm Grateful For": ["Sarah's direct questions", "clarity about what I really want"]
                        },
                        "days_ago": 3
                    },
                    {
                        "title": "Farmers market presence and 'Daddy home!'",
                        "raw_text": "Great family morning at the farmers market. Kept phone in car. Benjamin tried every sample, Sarah and I actually talked. Afternoon: reviewed my startup list with new filter - 'Would I be excited to work on this for 5 years even if it stayed small?' Down to 3 ideas. Progress. Evening: angel investor mixer. Stayed for one hour instead of three. Home for Benjamin's bedtime. He said 'Daddy home!' like it was a surprise. Need to make it not a surprise.",
                        "structured_data": {
                            "Summary": "Phone-free farmers market was perfect. New startup filter: excited for 5 years even if small? Down to 3 ideas. Benjamin: 'Daddy home!' like surprise.",
                            "Open Reflection": "Great family morning at farmers market, phone in car. Benjamin tried every sample, Sarah and I talked. Reviewed startup list with new filter - excited for 5 years even if small? Down to 3 ideas. Investor mixer only 1 hour instead of 3. Benjamin said 'Daddy home!' like surprise.",
                            "Things Done": ["farmers market with family", "reviewed startup list with new filter", "attended investor mixer for 1 hour only"],
                            "To Do": ["make being home for bedtime normal not surprise", "develop the 3 remaining startup ideas", "continue phone-free family outings"],
                            "Emotional State": "present and connected during family time, focused during idea filtering, motivated to be home more",
                            "Things I'm Grateful For": ["phone-free family time", "progress on idea filtering"],
                            "Benjamin": "Benjamin said 'Daddy home!' at bedtime like it was a surprise - need to make it not a surprise"
                        },
                        "days_ago": 2
                    },
                    {
                        "title": "Hour of peace and the enough question",
                        "raw_text": "Long piano session - full hour. No interruptions. Sarah read on the couch, Benjamin played with blocks. Peaceful. Had a startup idea midway through but kept playing. Idea was still there after, wrote it down in 30 seconds. Maybe ideas don't need essays, just capture. Looking at the week ahead - what if I blocked mornings for deep work, afternoons for meetings, evenings for family? What if I said no to 80% of opportunities to say yes to the 20% that matter? What if 'enough' is enough?",
                        "structured_data": {
                            "Summary": "Perfect hour of piano with family peace. Startup idea mid-session but kept playing. Ideas don't need essays. What if enough is enough?",
                            "Open Reflection": "Long piano session - full hour, no interruptions. Sarah read, Benjamin played blocks. Had startup idea midway but kept playing. Idea still there after, captured in 30 seconds. Ideas don't need essays. What if enough is enough?",
                            "Things Done": ["played piano for one hour", "captured startup idea in 30 seconds", "family peaceful time"],
                            "To Do": ["block mornings for deep work", "schedule meetings in afternoons", "protect evening family time", "say no to 80% of opportunities"],
                            "Emotional State": "peaceful during music, clear about priorities, questioning need for more",
                            "Things I'm Grateful For": ["uninterrupted hour of piano", "peaceful family scene", "simple idea capture"],
                            "Benjamin": "Benjamin played with blocks while I played piano - perfect peaceful scene"
                        },
                        "days_ago": 1
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