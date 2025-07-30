#!/usr/bin/env python3
"""
Journal Import Script with Progress Monitoring
Imports journal entries with clear step-by-step progress reporting
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


class ProgressJournalImporter:
    def __init__(self, import_dir: str = "/Users/cyan/code/cassidy-claudecode/import"):
        self.import_dir = Path(import_dir)
        self.username = "jg2950"
        self.password = "3qwerty"
        
    def log_step(self, step: str, status: str = "📝"):
        """Log a step with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{status} [{timestamp}] {step}")
        
    async def create_user_if_not_exists(self, db: AsyncSession) -> UserDB:
        """Create user jg2950 if it doesn't exist"""
        self.log_step("Checking if user jg2950 exists...")
        
        result = await db.execute(
            select(UserDB).where(UserDB.username == self.username)
        )
        user = result.scalar_one_or_none()
        
        if user:
            self.log_step(f"User {self.username} already exists", "✅")
            return user
            
        self.log_step("Creating new user jg2950...")
        hashed_password = SecurityService.hash_password(self.password)
        
        user = UserDB(
            username=self.username,
            email=f"{self.username}@example.com",
            password_hash=hashed_password,
            is_active=True
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        self.log_step(f"Created user: {self.username}", "✅")
        return user
        
    async def create_session_for_import(self, db: AsyncSession, user: UserDB) -> ChatSessionDB:
        """Create a session for importing journal entries"""
        self.log_step("Creating import session...")
        
        session_repo = ChatSessionRepository()
        session = await session_repo.create_session(
            db,
            user_id=user.id,
            conversation_type="journaling",
            metadata={"import": True, "import_date": datetime.now().isoformat()}
        )
        
        self.log_step(f"Created session: {session.id[:8]}...", "✅")
        return session
        
    def parse_journal_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse a journal file and extract content"""
        self.log_step(f"Parsing file: {file_path.name}")
        
        content = file_path.read_text(encoding='utf-8')
        
        # Extract timestamp from filename
        filename = file_path.stem
        try:
            timestamp_str = filename.replace('T', '')
            if len(timestamp_str) == 8:
                timestamp_str += "000000"
            timestamp = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        except ValueError:
            self.log_step(f"Warning: Could not parse timestamp from {filename}", "⚠️")
            timestamp = datetime.now()
            
        word_count = len(content.split())
        self.log_step(f"Parsed {word_count} words from {file_path.name}", "✅")
            
        return {
            "timestamp": timestamp,
            "raw_text": content,
            "filename": filename,
            "word_count": word_count
        }
        
    async def import_journal_entry(self, db: AsyncSession, user: UserDB, session: ChatSessionDB, journal_data: Dict[str, Any]):
        """Import a single journal entry with detailed progress"""
        filename = journal_data['filename']
        self.log_step(f"🚀 Starting import: {filename}")
        
        try:
            # Create journal text
            journal_text = f"Here's my journal entry from {journal_data['timestamp'].strftime('%B %d, %Y')}:\\n\\n"
            journal_text += journal_data['raw_text']
            
            self.log_step(f"Creating agent context for {filename}...")
            
            # Create agent service and context
            agent_service = AgentService(db)
            context = await agent_service.create_agent_context(
                user.id, session.id, session.conversation_type
            )
            
            self.log_step(f"Getting agent for {filename}...")
            
            # Get agent
            agent = await AgentFactory.get_agent(session.conversation_type, user.id, context)
            
            self.log_step(f"Saving user message for {filename}...")
            
            # Save user message
            message_repo = ChatMessageRepository()
            await message_repo.create_message(
                db, session_id=session.id, role="user", content=journal_text
            )
            
            self.log_step(f"🤖 Running AI agent for {filename} ({journal_data['word_count']} words)...")
            
            # Run agent (this is the slow part)
            start_time = datetime.now()
            result = await agent.run(journal_text, deps=context)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            self.log_step(f"✅ Agent completed for {filename} ({processing_time:.1f}s)", "🤖")
            
            # Process response and handle tools
            self.log_step(f"Processing agent response for {filename}...")
            response_data = await agent_service.process_agent_response(context, result)
            
            # Save assistant response
            await message_repo.create_message(
                db, session_id=session.id, role="assistant", content=result.output
            )
            
            # Check if journal was saved
            draft_repo = JournalDraftRepository()
            draft = await draft_repo.get_by_session_id(db, session.id)
            
            if draft and draft.draft_data:
                self.log_step(f"Journal structured with {len(draft.draft_data)} sections", "📋")
                
                # Try to finalize the journal entry
                self.log_step(f"Finalizing journal entry for {filename}...")
                journal_entry = await draft_repo.finalize_draft(db, session.id)
                
                if journal_entry:
                    self.log_step(f"✅ Journal entry saved: {journal_entry.title}", "💾")
                else:
                    self.log_step(f"⚠️ Journal entry not finalized for {filename}", "⚠️")
            else:
                self.log_step(f"⚠️ No structured data found for {filename}", "⚠️")
            
            self.log_step(f"✅ COMPLETED: {filename}", "🎉")
                
        except Exception as e:
            self.log_step(f"❌ ERROR importing {filename}: {str(e)}", "❌")
            raise
            
    async def import_all_journals(self, db: AsyncSession):
        """Import all journal files with progress monitoring"""
        self.log_step("🚀 Starting journal import process", "🚀")
        
        # Create/get user
        user = await self.create_user_if_not_exists(db)
        
        # Create session
        session = await self.create_session_for_import(db, user)
        
        # Get journal files
        journal_files = list(self.import_dir.glob("*.txt"))
        journal_files.sort()
        
        self.log_step(f"Found {len(journal_files)} journal files to import")
        for i, file_path in enumerate(journal_files, 1):
            print(f"  {i}. {file_path.name}")
            
        print("=" * 60)
        
        # Import each file
        for i, file_path in enumerate(journal_files, 1):
            self.log_step(f"📁 PROCESSING FILE {i}/{len(journal_files)}: {file_path.name}", "📁")
            
            try:
                journal_data = self.parse_journal_file(file_path)
                await self.import_journal_entry(db, user, session, journal_data)
                
                self.log_step(f"✅ File {i}/{len(journal_files)} completed", "✅")
                
            except Exception as e:
                self.log_step(f"❌ File {i}/{len(journal_files)} failed: {str(e)}", "❌")
                
            print("-" * 40)
                
        self.log_step(f"🎉 IMPORT COMPLETE! Processed {len(journal_files)} files", "🎉")
        
    async def run_import(self):
        """Run the import process"""
        print("🚀 CASSIDY JOURNAL IMPORT WITH PROGRESS")
        print("=" * 60)
        print(f"Import directory: {self.import_dir}")
        print(f"Target user: {self.username}")
        print("=" * 60)
        
        # Initialize database
        await init_db()
        
        # Get database session
        async for db in get_db():
            await self.import_all_journals(db)
            break


async def main():
    """Main function"""
    importer = ProgressJournalImporter()
    await importer.run_import()


if __name__ == "__main__":
    asyncio.run(main())