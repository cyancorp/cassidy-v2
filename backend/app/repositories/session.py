from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from datetime import datetime

from .base import BaseRepository
from app.models.session import ChatSessionDB, ChatMessageDB, JournalDraftDB, JournalEntryDB


class ChatSessionRepository(BaseRepository[ChatSessionDB]):
    def __init__(self):
        super().__init__(ChatSessionDB)
    
    async def get_active_sessions(self, db: AsyncSession, user_id: str) -> List[ChatSessionDB]:
        """Get active sessions for user"""
        result = await db.execute(
            select(ChatSessionDB)
            .where(ChatSessionDB.user_id == user_id, ChatSessionDB.is_active == True)
            .order_by(desc(ChatSessionDB.updated_at))
        )
        return result.scalars().all()
    
    async def create_session(
        self,
        db: AsyncSession,
        user_id: str,
        conversation_type: str = "journaling",
        metadata: Dict[str, Any] = None
    ) -> ChatSessionDB:
        """Create new chat session"""
        session = ChatSessionDB(
            user_id=user_id,
            conversation_type=conversation_type,
            session_metadata=metadata or {}
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session


class ChatMessageRepository(BaseRepository[ChatMessageDB]):
    def __init__(self):
        super().__init__(ChatMessageDB)
    
    async def get_by_session_id(self, db: AsyncSession, session_id: str) -> List[ChatMessageDB]:
        """Get all messages for a session ordered by created_at"""
        result = await db.execute(
            select(ChatMessageDB)
            .where(ChatMessageDB.session_id == session_id)
            .order_by(ChatMessageDB.created_at)
        )
        return result.scalars().all()
    
    async def create_message(
        self,
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> ChatMessageDB:
        """Create new chat message"""
        message = ChatMessageDB(
            session_id=session_id,
            role=role,
            content=content,
            message_metadata=metadata or {}
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message
    
    def to_pydantic_message(self, message: ChatMessageDB):
        """Convert ChatMessage to pydantic-ai message format"""
        from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart
        
        if message.role == "user":
            return ModelRequest(parts=[UserPromptPart(content=message.content)])
        elif message.role == "assistant":
            return ModelResponse(parts=[TextPart(content=message.content)])
        else:
            # For system messages or other roles, default to user for now
            return ModelRequest(parts=[UserPromptPart(content=message.content)])


class JournalDraftRepository(BaseRepository[JournalDraftDB]):
    def __init__(self):
        super().__init__(JournalDraftDB)
    
    async def get_by_session_id(self, db: AsyncSession, session_id: str) -> Optional[JournalDraftDB]:
        """Get draft by session ID"""
        result = await db.execute(
            select(JournalDraftDB).where(JournalDraftDB.session_id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def create_draft(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: str,
        draft_data: Dict[str, Any] = None
    ) -> JournalDraftDB:
        """Create new journal draft"""
        draft = JournalDraftDB(
            session_id=session_id,
            user_id=user_id,
            draft_data=draft_data or {}
        )
        db.add(draft)
        await db.commit()
        await db.refresh(draft)
        return draft
    
    async def update_draft_data(
        self,
        db: AsyncSession,
        session_id: str,
        draft_data: Dict[str, Any]
    ) -> Optional[JournalDraftDB]:
        """Update draft data and raw text"""
        # Get concatenated raw text from user messages in this session
        raw_text = await self._get_session_raw_text(db, session_id)
        
        await db.execute(
            update(JournalDraftDB)
            .where(JournalDraftDB.session_id == session_id)
            .values(draft_data=draft_data, raw_text=raw_text, updated_at=datetime.utcnow())
        )
        await db.commit()
        return await self.get_by_session_id(db, session_id)
    
    async def finalize_draft(self, db: AsyncSession, session_id: str) -> Optional[JournalEntryDB]:
        """Finalize draft into journal entry"""
        print(f"Starting finalize_draft for session: {session_id}")
        
        # Allow multiple journal entries per session - don't check for existing entries
        # This enables creating multiple journal entries in the same chat session
        
        # Get the draft
        draft = await self.get_by_session_id(db, session_id)
        if not draft or not draft.draft_data:
            print(f"No draft found or empty data: {draft}")
            return None
        
        # Create a new journal entry even if draft was previously finalized
        # This allows multiple entries per session
        
        print(f"Found draft: {draft.draft_data}")
        
        # Get raw text if not already in draft (for backwards compatibility)
        raw_text = draft.raw_text if draft.raw_text else await self._get_session_raw_text(db, session_id)
        
        # Create journal entry
        entry = JournalEntryDB(
            user_id=draft.user_id,
            session_id=draft.session_id,
            structured_data=draft.draft_data,
            raw_text=raw_text,
            title=self._generate_title(draft.draft_data)
        )
        print(f"Created journal entry object: {entry.title}")
        db.add(entry)
        
        # Clear draft data to allow new entries in the same session
        print("Clearing draft data for new entries...")
        await db.execute(
            update(JournalDraftDB)
            .where(JournalDraftDB.session_id == session_id)
            .values(
                draft_data={},  # Clear the draft content
                is_finalized=False,  # Allow new content to be added
                updated_at=datetime.utcnow()
            )
        )
        
        print("Committing transaction...")
        try:
            await db.commit()
            print("Transaction committed successfully")
            await db.refresh(entry)
            print(f"Entry refreshed, ID: {entry.id}")
            return entry
        except Exception as e:
            print(f"Error during commit: {e}")
            await db.rollback()
            return None
    
    def _generate_title(self, draft_data: Dict[str, Any]) -> str:
        """Generate title from draft content"""
        if not draft_data:
            return f"Journal Entry - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Find first non-empty section
        for section_name, content in draft_data.items():
            if content and isinstance(content, str):
                # Take first 50 characters
                title = content.strip()[:50]
                if len(content) > 50:
                    title += "..."
                return title
            elif content and isinstance(content, list) and content:
                # Take first item if it's a list
                title = str(content[0])[:50]
                if len(str(content[0])) > 50:
                    title += "..."
                return title
        
        return f"Journal Entry - {datetime.now().strftime('%Y-%m-%d')}"
    
    async def _get_session_raw_text(self, db: AsyncSession, session_id: str) -> str:
        """Get concatenated raw text from all user messages in session"""
        result = await db.execute(
            select(ChatMessageDB.content)
            .where(
                ChatMessageDB.session_id == session_id,
                ChatMessageDB.role == "user"
            )
            .order_by(ChatMessageDB.created_at)
        )
        user_messages = result.scalars().all()
        return "\n\n".join(user_messages) if user_messages else ""


class JournalEntryRepository(BaseRepository[JournalEntryDB]):
    def __init__(self):
        super().__init__(JournalEntryDB)
    
    async def get_by_user_id(
        self, 
        db: AsyncSession, 
        user_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[JournalEntryDB]:
        """Get journal entries for user"""
        result = await db.execute(
            select(JournalEntryDB)
            .where(JournalEntryDB.user_id == user_id)
            .order_by(desc(JournalEntryDB.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()