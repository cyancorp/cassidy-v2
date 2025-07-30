#!/usr/bin/env python3
"""
Direct Journal Import - Bypass AI entirely
Create journal entries directly without any AI processing
"""

import os
import asyncio
import re
from datetime import datetime
from pathlib import Path
import sys
import uuid

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, init_db
from app.models.user import UserDB
from app.models.session import ChatSessionDB, JournalEntryDB
from app.repositories.session import ChatSessionRepository
from app.agents.task_tools import create_task_tool
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
    
    # Fallback to current date
    log_step("Using current date as fallback", "⚠️")
    return datetime.now()


def extract_tasks_from_content(content: str) -> list:
    """Extract tasks from journal content manually"""
    tasks = []
    
    # Look for "Goals for Next Week" section
    goals_match = re.search(r'#### Goals for Next Week\s*\n((?:- .*\n?)*)', content, re.IGNORECASE)
    if goals_match:
        goals_text = goals_match.group(1)
        # Extract each bullet point
        for line in goals_text.split('\n'):
            if line.strip().startswith('-'):
                task_title = line.strip()[1:].strip()
                if task_title:
                    tasks.append(task_title)
    
    # Also look for "Todos" section
    todos_match = re.search(r'#### (?:Todos?|TODO)\s*\n((?:- .*\n?)*)', content, re.IGNORECASE)
    if todos_match:
        todos_text = todos_match.group(1)
        for line in todos_text.split('\n'):
            if line.strip().startswith('-'):
                task_title = line.strip()[1:].strip()
                if task_title and task_title not in tasks:
                    tasks.append(task_title)
    
    return tasks


def structure_journal_content(content: str) -> dict:
    """Structure journal content manually into sections"""
    sections = {}
    
    # Extract sections using regex
    section_patterns = {
        'open_reflection': r'#### Open Reflection\s*\n(.*?)(?=####|\Z)',
        'goals_for_next_week': r'#### Goals for Next Week\s*\n(.*?)(?=####|\Z)', 
        'wins_this_week': r'#### Wins This Week\s*\n(.*?)(?=####|\Z)',
        'challenges_this_week': r'#### Challenges This Week\s*\n(.*?)(?=####|\Z)',
        'grateful_for': r'#### Things I\'m Grateful For\s*\n(.*?)(?=####|\Z)',
        'learning': r'#### Learning\s*\n(.*?)(?=####|\Z)',
        'personal_development': r'#### Personal Development\s*\n(.*?)(?=####|\Z)',
        'relationships': r'#### Relationships\s*\n(.*?)(?=####|\Z)',
        'health_fitness': r'#### Health & Fitness\s*\n(.*?)(?=####|\Z)',
        'business_work': r'#### Business & Work\s*\n(.*?)(?=####|\Z)',
        'finances': r'#### Finances\s*\n(.*?)(?=####|\Z)',
        'creativity_projects': r'#### Creativity & Projects\s*\n(.*?)(?=####|\Z)',
        'travel_experiences': r'#### Travel & Experiences\s*\n(.*?)(?=####|\Z)',
        'todo': r'#### (?:Todos?|TODO)\s*\n(.*?)(?=####|\Z)'
    }
    
    for section_key, pattern in section_patterns.items():
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            section_content = match.group(1).strip()
            if section_content:
                sections[section_key] = section_content
    
    return sections


async def import_journal_file(filename: str):
    """Import a single journal file directly"""
    
    print(f"\n🚀 DIRECT IMPORT: {filename}")
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
                metadata={"import": True, "file": filename, "direct_mode": True}
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
            
            # Extract tasks manually
            log_step("📋 Extracting tasks from content...")
            extracted_tasks = extract_tasks_from_content(content)
            log_step(f"📋 Found {len(extracted_tasks)} tasks to create")
            
            # Structure content manually
            log_step("📝 Structuring journal content...")
            structured_data = structure_journal_content(content)
            log_step(f"📝 Structured into {len(structured_data)} sections")
            
            # Create journal entry directly
            log_step("📝 Creating journal entry...")
            
            # Generate title from first 50 chars of open reflection or content
            title_content = structured_data.get('open_reflection', content)
            title = title_content[:47] + "..." if len(title_content) > 50 else title_content
            title = title.replace('\n', ' ').strip()
            
            # Create journal entry directly
            journal_entry = JournalEntryDB(
                id=str(uuid.uuid4()),
                user_id=user.id,
                session_id=session.id,
                title=title,
                structured_data=structured_data,
                raw_text=content,
                created_at=journal_date,
                updated_at=journal_date
            )
            
            db.add(journal_entry)
            await db.flush()  # Get the ID
            
            log_step(f"📅 Journal entry dated {journal_date.strftime('%B %d, %Y')}")
            
            log_step(f"✅ Journal entry created: {journal_entry.id[:8]}...")
            
            # Now create tasks manually
            if extracted_tasks:
                log_step(f"📋 Creating {len(extracted_tasks)} tasks...")
                created_count = 0
                
                for task_title in extracted_tasks:
                    try:
                        task_result = await create_task_tool(
                            user_id=user.id,
                            title=task_title,
                            source_session_id=session.id
                        )
                        if task_result.get('success'):
                            created_count += 1
                            # Update task date to match journal
                            task_id = task_result['task']['id']
                            await db.execute(text(f'''
                                UPDATE tasks 
                                SET created_at = :date
                                WHERE id = :task_id
                            '''), {"date": journal_date.isoformat(), "task_id": task_id})
                            print(f"      ✅ {task_title}")
                    except Exception as e:
                        log_step(f"⚠️  Failed to create task '{task_title[:30]}...': {e}", "⚠️")
                
                log_step(f"✅ Created {created_count}/{len(extracted_tasks)} tasks")
            
            # Commit all updates
            await db.commit()
            
            print(f"\n🎉 COMPLETED: {filename}")
            print(f"📝 Journal entry: {title}")
            print(f"📅 Date: {journal_date.strftime('%B %d, %Y')}")
            if extracted_tasks:
                print(f"📋 Tasks: {created_count} tasks created and dated {journal_date.strftime('%B %d, %Y')}")
            print("=" * 60)
            
        except Exception as e:
            log_step(f"❌ Import failed: {str(e)}", "❌")
            return False
        finally:
            break
    
    return True


async def main():
    """Main function - import one file"""
    if len(sys.argv) != 2:
        print("❌ Usage: uv run python scripts/import_journal_direct.py <filename>")
        print("📝 Example: uv run python scripts/import_journal_direct.py 20250422T000000.txt")
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