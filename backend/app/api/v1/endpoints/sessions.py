from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.api import CreateSessionRequest, CreateSessionResponse, ChatSessionResponse
from app.repositories.session import ChatSessionRepository, JournalEntryRepository
from app.core.deps import get_current_user
from app.models.user import UserDB
from app.models.session import JournalEntryDB

router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new chat session"""
    session_repo = ChatSessionRepository()
    session = await session_repo.create_session(
        db,
        user_id=current_user.id,
        conversation_type=request.conversation_type,
        metadata=request.metadata
    )
    
    return CreateSessionResponse(
        session_id=session.id,
        conversation_type=session.conversation_type,
        created_at=session.created_at
    )


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_sessions(
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's chat sessions"""
    session_repo = ChatSessionRepository()
    sessions = await session_repo.get_active_sessions(db, current_user.id)
    
    return [
        ChatSessionResponse(
            id=session.id,
            user_id=session.user_id,
            conversation_type=session.conversation_type,
            is_active=session.is_active,
            metadata=session.session_metadata,
            created_at=session.created_at,
            updated_at=session.updated_at
        )
        for session in sessions
    ]


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: UUID,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific session"""
    session_repo = ChatSessionRepository()
    session = await session_repo.get_by_id(db, session_id)
    
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return ChatSessionResponse(
        id=session.id,
        user_id=session.user_id,
        conversation_type=session.conversation_type,
        is_active=session.is_active,
        metadata=session.session_metadata,
        created_at=session.created_at,
        updated_at=session.updated_at
    )


@router.get("/journal-entries", response_model=List[dict])
async def list_journal_entries(
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's journal entries"""
    journal_repo = JournalEntryRepository()
    entries = await journal_repo.get_by_user_id(db, current_user.id)
    
    return [
        {
            "id": str(entry.id),
            "session_id": str(entry.session_id) if entry.session_id else None,
            "created_at": entry.created_at.isoformat(),
            "raw_text": entry.raw_text or "",
            "structured_data": entry.structured_data or {},
            "metadata": entry.entry_metadata or {}
        }
        for entry in entries
    ]


@router.get("/journal-entries/{entry_id}", response_model=dict)
async def get_journal_entry(
    entry_id: UUID,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific journal entry"""
    journal_repo = JournalEntryRepository()
    entry = await journal_repo.get_by_id(db, entry_id)
    
    if not entry or entry.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found"
        )
    
    return {
        "id": str(entry.id),
        "session_id": str(entry.session_id) if entry.session_id else None,
        "created_at": entry.created_at.isoformat(),
        "raw_text": entry.raw_text or "",
        "structured_data": entry.structured_data or {},
        "metadata": entry.entry_metadata or {}
    }