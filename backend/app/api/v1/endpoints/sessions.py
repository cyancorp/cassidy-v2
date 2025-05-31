from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.api import CreateSessionRequest, CreateSessionResponse, ChatSessionResponse
from app.repositories.session import ChatSessionRepository
from app.core.deps import get_current_user
from app.models.user import UserDB

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