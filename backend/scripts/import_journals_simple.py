#!/usr/bin/env python3
"""
Simple Journal Import Script
Imports journal entries one by one with explicit saving
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
from sqlalchemy import select


async def import_single_journal(file_path: str):
    """Import a single journal file with explicit saving"""
    
    print(f"\n🚀 IMPORTING: {file_path}")
    print("=" * 50)
    
    # Initialize database
    await init_db()
    
    async for db in get_db():
        # Get user
        result = await db.execute(select(UserDB).where(UserDB.username == "jg2950"))
        user = result.scalar_one_or_none()
        
        if not user:
            print("❌ User jg2950 not found! Run clean_import_data.py and import_journals_progress.py first")
            return
            
        print(f"✅ Found user: {user.username}")
        
        # Get or create session
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
                db, user_id=user.id, conversation_type="journaling"
            )
            print(f"✅ Created new session: {session.id[:8]}...")
        else:
            print(f"✅ Using existing session: {session.id[:8]}...")
            
        # Read journal file
        journal_path = Path(f"/Users/cyan/code/cassidy-claudecode/import/{file_path}")
        if not journal_path.exists():
            print(f"❌ File not found: {journal_path}")
            return
            
        content = journal_path.read_text(encoding='utf-8')
        word_count = len(content.split())
        print(f"✅ Read {word_count} words from {file_path}")
        
        # Create journal text
        journal_text = f"Here's my journal entry:\\n\\n{content}\\n\\nPlease structure this and save it as a journal entry."
        
        # Create agent context
        print("🤖 Creating agent context...")
        agent_service = AgentService(db)
        context = await agent_service.create_agent_context(
            user.id, session.id, session.conversation_type
        )
        
        # Get agent
        print("🤖 Getting agent...")
        agent = await AgentFactory.get_agent(session.conversation_type, user.id, context)
        
        # Save user message
        print("💬 Saving user message...")
        message_repo = ChatMessageRepository()
        await message_repo.create_message(
            db, session_id=session.id, role="user", content=journal_text
        )
        
        # Run agent
        print(f"🤖 Processing with AI ({word_count} words)...")
        start_time = datetime.now()
        result = await agent.run(journal_text, deps=context)
        processing_time = (datetime.now() - start_time).total_seconds()
        print(f"✅ AI processing completed ({processing_time:.1f}s)")
        
        # Process response
        print("📝 Processing agent response...")
        response_data = await agent_service.process_agent_response(context, result)
        
        # Save assistant response
        await message_repo.create_message(
            db, session_id=session.id, role="assistant", content=result.output
        )
        
        # EXPLICITLY try to save the journal entry
        print("💾 Attempting to save journal entry...")
        draft_repo = JournalDraftRepository()
        
        # First check if there's structured data
        draft = await draft_repo.get_by_session_id(db, session.id)
        if draft and draft.draft_data and any(draft.draft_data.values()):
            print(f"📋 Found structured data with {len(draft.draft_data)} sections:")
            for section, content in draft.draft_data.items():
                content_preview = str(content)[:50] + "..." if len(str(content)) > 50 else str(content)
                print(f"  - {section}: {content_preview}")
                
            # Try to finalize
            print("💾 Finalizing journal entry...")
            journal_entry = await draft_repo.finalize_draft(db, session.id)
            
            if journal_entry:
                print(f"✅ JOURNAL ENTRY SAVED!")
                print(f"   ID: {journal_entry.id}")
                print(f"   Title: {journal_entry.title}")
                print(f"   Created: {journal_entry.created_at}")
            else:
                print("❌ Failed to finalize journal entry")
        else:
            print("⚠️  No structured data found in draft")
            
        # Check final status
        from sqlalchemy import text
        result = await db.execute(text(f'SELECT COUNT(*) FROM journal_entries WHERE user_id = "{user.id}"'))
        entry_count = result.scalar()
        print(f"📊 Total journal entries for user: {entry_count}")
        
        print(f"🎉 COMPLETED: {file_path}")
        break


async def main():
    """Main function - import one file at a time"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python3 import_journals_simple.py <filename>")
        print("Example: python3 import_journals_simple.py 20250323T000000.txt")
        return
        
    filename = sys.argv[1]
    await import_single_journal(filename)


if __name__ == "__main__":
    asyncio.run(main())