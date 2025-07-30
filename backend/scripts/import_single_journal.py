#!/usr/bin/env python3
"""
Import Single Journal with Correct Date
Imports one journal file with proper date setting and detailed progress
"""

import os
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db, init_db
from app.models.user import UserDB
from app.models.session import ChatSessionDB
from app.repositories.session import ChatSessionRepository, ChatMessageRepository, JournalDraftRepository
from app.agents.service import AgentService
from app.agents.factory import AgentFactory
from app.core.security import SecurityService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text


def log_step(step: str, status: str = "📝"):
    """Log a step with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{status} [{timestamp}] {step}")


def parse_journal_date(file_path: Path, content: str) -> datetime:
    """Parse journal date from filename and content"""
    filename = file_path.stem
    
    # Try to parse date from filename (YYYYMMDDTHHMMSS)
    try:
        timestamp_str = filename.replace('T', '')
        if len(timestamp_str) == 8:  # YYYYMMDD format
            timestamp_str += "000000"  # Add HHMMSS
        parsed_date = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        log_step(f"Parsed date from filename: {parsed_date.strftime('%B %d, %Y')}")
        return parsed_date
    except ValueError:
        log_step(f"Could not parse date from filename: {filename}", "⚠️")
    
    # Try to parse from content header
    date_patterns = [
        r"Journal Entry.*?(\w+ \d{1,2}, \d{4})",  # "Journal Entry - March 23, 2025"
        r"### Journal Entry.*?(\w+ \d{1,2}, \d{4})",  # "### Journal Entry 1 - March 23, 2025"
        r"# Journal Entry.*?(\w+ \d{1,2}, \d{4})",   # "# Journal Entry - May 15, 2025"
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, content)
        if match:
            date_str = match.group(1)
            try:
                parsed_date = datetime.strptime(date_str, "%B %d, %Y")
                log_step(f"Parsed date from content: {parsed_date.strftime('%B %d, %Y')}")
                return parsed_date
            except ValueError:
                continue
    
    # Fallback to current date
    log_step("Using current date as fallback", "⚠️")
    return datetime.now()


async def import_single_journal(file_path: str):
    """Import a single journal file with correct date and detailed progress"""
    
    print(f"\n🚀 IMPORTING JOURNAL: {file_path}")
    print("=" * 60)
    
    # Initialize database
    log_step("Initializing database...")
    await init_db()
    
    async for db in get_db():
        # Get user
        log_step("Looking up user jg2950...")
        result = await db.execute(select(UserDB).where(UserDB.username == "jg2950"))
        user = result.scalar_one_or_none()
        
        if not user:
            print("❌ User jg2950 not found! Run import_journals_progress.py first to create user")
            return
            
        log_step(f"✅ Found user: {user.username} (ID: {user.id[:8]}...)")
        
        # Get or create session
        log_step("Getting import session...")
        session_repo = ChatSessionRepository()
        result = await db.execute(
            select(ChatSessionDB).where(
                ChatSessionDB.user_id == user.id,
                ChatSessionDB.conversation_type == "journaling"
            ).order_by(ChatSessionDB.created_at.desc()).limit(1)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            session = await session_repo.create_session(
                db, user_id=user.id, conversation_type="journaling",
                metadata={"import": True, "single_file": file_path}
            )
            log_step(f"✅ Created new session: {session.id[:8]}...")
        else:
            log_step(f"✅ Using existing session: {session.id[:8]}...")
            
        # Read journal file
        log_step(f"Reading journal file: {file_path}")
        journal_path = Path(f"/Users/cyan/code/cassidy-claudecode/import/{file_path}")
        if not journal_path.exists():
            print(f"❌ File not found: {journal_path}")
            return
            
        content = journal_path.read_text(encoding='utf-8')
        word_count = len(content.split())
        log_step(f"✅ Read {word_count} words from {file_path}")
        
        # Parse the journal date
        log_step("Parsing journal date...")
        journal_date = parse_journal_date(journal_path, content)
        
        # Create journal text with explicit instructions
        journal_text = f"""Here's my journal entry from {journal_date.strftime('%B %d, %Y')}:

{content}

Please structure this journal entry and save it. Set the journal entry date to {journal_date.strftime('%B %d, %Y')}."""
        
        log_step(f"📝 Prepared journal text ({len(journal_text)} chars)")
        
        # Create agent context
        log_step("🤖 Creating agent context...")
        agent_service = AgentService(db)
        context = await agent_service.create_agent_context(
            user.id, session.id, session.conversation_type
        )
        log_step(f"✅ Agent context created (user: {context.user_id[:8]}...)")
        
        # Get agent
        log_step("🤖 Getting agent...")
        agent = await AgentFactory.get_agent(session.conversation_type, user.id, context)
        log_step("✅ Agent created successfully")
        
        # Save user message
        log_step("💬 Saving user message to database...")
        message_repo = ChatMessageRepository()
        user_message = await message_repo.create_message(
            db, session_id=session.id, role="user", content=journal_text
        )
        log_step(f"✅ User message saved (ID: {user_message.id[:8]}...)")
        
        # Run agent with detailed progress
        log_step(f"🤖 Running AI agent on {word_count} words...")
        log_step("    ⏳ This may take 30-60 seconds...")
        
        start_time = datetime.now()
        try:
            result = await agent.run(journal_text, deps=context)
            processing_time = (datetime.now() - start_time).total_seconds()
            log_step(f"✅ AI processing completed in {processing_time:.1f} seconds", "🤖")
            log_step(f"    Response length: {len(result.output)} characters")
        except Exception as e:
            log_step(f"❌ AI processing failed: {str(e)}", "❌")
            raise
        
        # Process response
        log_step("📝 Processing agent response...")
        try:
            response_data = await agent_service.process_agent_response(context, result)
            log_step("✅ Agent response processed")
        except Exception as e:
            log_step(f"❌ Response processing failed: {str(e)}", "❌")
            raise
        
        # Save assistant response
        log_step("💬 Saving assistant response to database...")
        assistant_message = await message_repo.create_message(
            db, session_id=session.id, role="assistant", content=result.output
        )
        log_step(f"✅ Assistant message saved (ID: {assistant_message.id[:8]}...)")
        
        # Check for structured data and try to save journal
        log_step("💾 Checking for journal data to save...")
        draft_repo = JournalDraftRepository()
        
        draft = await draft_repo.get_by_session_id(db, session.id)
        if draft and draft.draft_data and any(draft.draft_data.values()):
            log_step(f"📋 Found structured data with {len(draft.draft_data)} sections:")
            for section, content in draft.draft_data.items():
                content_preview = str(content)[:50] + "..." if len(str(content)) > 50 else str(content)
                print(f"        - {section}: {content_preview}")
                
            # Manually set the journal entry date by updating the draft's created_at
            log_step(f"📅 Setting journal entry date to {journal_date.strftime('%B %d, %Y')}")
            
            # Finalize the draft
            log_step("💾 Finalizing journal entry...")
            journal_entry = await draft_repo.finalize_draft(db, session.id)
            
            if journal_entry:
                # Update the journal entry's created_at to match the original date
                await db.execute(text(f'''
                    UPDATE journal_entries 
                    SET created_at = "{journal_date.isoformat()}"
                    WHERE id = "{journal_entry.id}"
                '''))
                
                # Update tasks created from this journal to have the same date
                log_step("📅 Setting task dates to match journal date...")
                
                # Get tasks created in this session (during this import)
                result = await db.execute(text(f'''
                    SELECT id, title FROM tasks 
                    WHERE source_session_id = "{session.id}"
                    AND user_id = "{user.id}"
                '''))
                tasks_from_journal = result.fetchall()
                
                if tasks_from_journal:
                    log_step(f"📋 Found {len(tasks_from_journal)} tasks to update:")
                    
                    for task_id, task_title in tasks_from_journal:
                        # Update each task's created_at date
                        await db.execute(text(f'''
                            UPDATE tasks 
                            SET created_at = "{journal_date.isoformat()}"
                            WHERE id = "{task_id}"
                        '''))
                        
                        # Show task preview
                        task_preview = task_title[:40] + "..." if len(task_title) > 40 else task_title
                        print(f"        ✅ {task_preview}")
                
                await db.commit()
                
                log_step("✅ JOURNAL ENTRY SAVED SUCCESSFULLY!", "🎉")
                log_step(f"    ID: {journal_entry.id}")
                log_step(f"    Title: {journal_entry.title}")
                log_step(f"    Date: {journal_date.strftime('%B %d, %Y')}")
                if tasks_from_journal:
                    log_step(f"    Tasks: {len(tasks_from_journal)} tasks dated {journal_date.strftime('%B %d, %Y')}")
            else:
                log_step("❌ Failed to finalize journal entry", "❌")
        else:
            log_step("⚠️  No structured data found in draft", "⚠️")
            
        # Final status check
        log_step("📊 Checking final status...")
        result = await db.execute(text(f'SELECT COUNT(*) FROM journal_entries WHERE user_id = "{user.id}"'))
        entry_count = result.scalar()
        
        result = await db.execute(text(f'SELECT COUNT(*) FROM tasks WHERE user_id = "{user.id}"'))
        task_count = result.scalar()
        
        log_step(f"📊 FINAL STATUS:")
        print(f"        📝 Total journal entries: {entry_count}")
        print(f"        ✅ Total tasks: {task_count}")
        
        print(f"\n🎉 COMPLETED: {file_path}")
        print("=" * 60)
        break


async def main():
    """Main function - import one file"""
    if len(sys.argv) != 2:
        print("❌ Usage: python3 import_single_journal.py <filename>")
        print("📝 Example: python3 import_single_journal.py 20250323T000000.txt")
        print()
        print("📁 Available files:")
        import_dir = Path("/Users/cyan/code/cassidy-claudecode/import")
        for file_path in sorted(import_dir.glob("*.txt")):
            print(f"   - {file_path.name}")
        return
        
    filename = sys.argv[1]
    await import_single_journal(filename)


if __name__ == "__main__":
    asyncio.run(main())