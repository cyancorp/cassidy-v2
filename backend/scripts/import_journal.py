#!/usr/bin/env python3
"""
Import Single Journal with Proper Date Handling
Imports one journal file with correct date setting and detailed progress
"""

import os
import asyncio
import re
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, init_db
from app.models.user import UserDB
from app.models.session import ChatSessionDB
from app.repositories.session import ChatSessionRepository, ChatMessageRepository, JournalDraftRepository
from app.agents.service import AgentService
from app.agents.factory import AgentFactory
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


async def import_journal_file(filename: str):
    """Import a single journal file with correct date and detailed progress"""
    
    print(f"\n🚀 IMPORTING JOURNAL: {filename}")
    print("=" * 60)
    
    # Initialize database
    log_step("Initializing database...")
    await init_db()
    
    async for db in get_db():
        try:
            # Get user
            log_step("Looking up user jg2950...")
            result = await db.execute(select(UserDB).where(UserDB.username == "jg2950"))
            user = result.scalar_one_or_none()
            
            if not user:
                print("❌ User jg2950 not found! Run: uv run python scripts/setup_user.py")
                return False
                
            log_step(f"✅ Found user: {user.username} (ID: {user.id[:8]}...)")
            
            # Create new session for this import
            log_step("Creating new import session...")
            session_repo = ChatSessionRepository()
            session = await session_repo.create_session(
                db, user_id=user.id, conversation_type="journaling",
                metadata={"import": True, "file": filename}
            )
            log_step(f"✅ Created session: {session.id[:8]}...")
                
            # Read journal file
            log_step(f"Reading journal file: {filename}")
            journal_path = Path(f"/Users/cyan/code/cassidy-claudecode/import/{filename}")
            if not journal_path.exists():
                print(f"❌ File not found: {journal_path}")
                return False
                
            content = journal_path.read_text(encoding='utf-8')
            word_count = len(content.split())
            log_step(f"✅ Read {word_count} words from {filename}")
            
            # Parse the journal date
            log_step("Parsing journal date...")
            journal_date = parse_journal_date(journal_path, content)
            
            # Create journal text
            journal_text = f"""Here's my journal entry from {journal_date.strftime('%B %d, %Y')}:

{content}

Please structure this journal entry and save it. The original date is {journal_date.strftime('%B %d, %Y')}."""
            
            log_step(f"📝 Prepared journal text ({len(journal_text)} chars)")
            
            # Create agent context
            log_step("🤖 Creating agent context...")
            agent_service = AgentService(db)
            context = await agent_service.create_agent_context(
                user.id, session.id, session.conversation_type
            )
            log_step(f"✅ Agent context created")
            
            # Get agent
            log_step("🤖 Getting agent...")
            agent = await AgentFactory.get_agent(session.conversation_type, user.id, context)
            log_step("✅ Agent created successfully")
            
            # Save user message
            log_step("💬 Saving user message...")
            message_repo = ChatMessageRepository()
            user_message = await message_repo.create_message(
                db, session_id=session.id, role="user", content=journal_text
            )
            log_step(f"✅ User message saved (ID: {user_message.id[:8]}...)")
            
            # Run agent with timeout
            log_step(f"🤖 Running AI agent on {word_count} words...")
            log_step("    ⏳ This may take 30-60 seconds...")
            
            start_time = datetime.now()
            try:
                result = await asyncio.wait_for(
                    agent.run(journal_text, deps=context),
                    timeout=120.0  # 2 minute timeout
                )
                processing_time = (datetime.now() - start_time).total_seconds()
                log_step(f"✅ AI processing completed in {processing_time:.1f} seconds", "🤖")
                log_step(f"    Response length: {len(result.output)} characters")
            except asyncio.TimeoutError:
                log_step("❌ AI processing timed out after 2 minutes", "❌")
                return False
            except Exception as e:
                log_step(f"❌ AI processing failed: {str(e)}", "❌")
                return False
            
            # Process response - this is where the journal entry gets created
            log_step("📝 Processing agent response...")
            try:
                response_data = await agent_service.process_agent_response(context, result)
                log_step("✅ Agent response processed")
                
                # Check if a journal entry was created (try multiple ways)
                journal_entry_id = None
                
                # Method 1: Check metadata
                if response_data.get('metadata', {}).get('journal_entry_id'):
                    journal_entry_id = response_data['metadata']['journal_entry_id']
                    log_step(f"📝 Found journal entry ID in metadata: {journal_entry_id[:8]}...")
                
                # Method 2: Check for journal entry created in this session
                if not journal_entry_id:
                    log_step("🔍 Looking for journal entry in session...")
                    result = await db.execute(text(f'''
                        SELECT id FROM journal_entries 
                        WHERE session_id = "{session.id}"
                        ORDER BY created_at DESC
                        LIMIT 1
                    '''))
                    entry = result.fetchone()
                    if entry:
                        journal_entry_id = entry[0]
                        log_step(f"📝 Found journal entry by session: {journal_entry_id[:8]}...")
                
                if journal_entry_id:
                    # IMMEDIATELY update the journal entry date to the correct date
                    log_step(f"📅 Setting journal entry date to {journal_date.strftime('%B %d, %Y')}")
                    await db.execute(text(f'''
                        UPDATE journal_entries 
                        SET created_at = "{journal_date.isoformat()}"
                        WHERE id = "{journal_entry_id}"
                    '''))
                    
                    # Update tasks created from this journal to have the same date
                    log_step("📅 Setting task dates to match journal date...")
                    
                    # Get tasks created in this session
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
                    
                    # Commit all date updates
                    await db.commit()
                    
                    # Get the updated journal entry to confirm
                    result = await db.execute(text(f'''
                        SELECT title, created_at FROM journal_entries 
                        WHERE id = "{journal_entry_id}"
                    '''))
                    entry_data = result.fetchone()
                    
                    if entry_data:
                        title, created_at = entry_data
                        log_step("✅ JOURNAL ENTRY SAVED SUCCESSFULLY!", "🎉")
                        log_step(f"    ID: {journal_entry_id}")
                        log_step(f"    Title: {title}")
                        log_step(f"    Date: {journal_date.strftime('%B %d, %Y')}")
                        if tasks_from_journal:
                            log_step(f"    Tasks: {len(tasks_from_journal)} tasks dated {journal_date.strftime('%B %d, %Y')}")
                else:
                    log_step("⚠️  No journal entry was created", "⚠️")
                    return False
                    
            except Exception as e:
                log_step(f"❌ Response processing failed: {str(e)}", "❌")
                return False
            
            # Save assistant response
            log_step("💬 Saving assistant response...")
            assistant_message = await message_repo.create_message(
                db, session_id=session.id, role="assistant", content=result.output
            )
            log_step(f"✅ Assistant message saved (ID: {assistant_message.id[:8]}...)")
            
            print(f"\n🎉 COMPLETED: {filename}")
            print("=" * 60)
            return True
                
        except Exception as e:
            log_step(f"❌ Import failed: {str(e)}", "❌")
            return False
        finally:
            break


async def main():
    """Main function - import one file"""
    if len(sys.argv) != 2:
        print("❌ Usage: uv run python scripts/import_journal.py <filename>")
        print("📝 Example: uv run python scripts/import_journal.py 20250323T000000.txt")
        print()
        print("📁 Available files:")
        import_dir = Path("/Users/cyan/code/cassidy-claudecode/import")
        for file_path in sorted(import_dir.glob("*.txt")):
            print(f"   - {file_path.name}")
        return
        
    filename = sys.argv[1]
    success = await import_journal_file(filename)
    
    if success:
        print("\n✅ Import completed successfully!")
    else:
        print("\n❌ Import failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())