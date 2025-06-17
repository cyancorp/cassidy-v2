from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.models.api import AgentChatRequest, AgentChatResponse
from app.agents.service import AgentService
from app.agents.factory import AgentFactory
from app.repositories.session import ChatSessionRepository, ChatMessageRepository
from app.core.deps import get_current_user
from app.models.user import UserDB

router = APIRouter()


@router.post("/chat/{session_id}", response_model=AgentChatResponse)
async def agent_chat(
    session_id: str,  # Using string instead of UUID for compatibility
    request: AgentChatRequest,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Main agent chat endpoint"""
    
    # Verify session belongs to user
    session_repo = ChatSessionRepository()
    session = await session_repo.get_by_id(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Create agent service and context
    agent_service = AgentService(db)
    context = await agent_service.create_agent_context(
        current_user.id, session_id, session.conversation_type
    )
    
    # Get agent for conversation type with user_id
    agent = await AgentFactory.get_agent(session.conversation_type, current_user.id)
    
    # Load message history
    message_history = await agent_service.get_message_history(session_id)
    
    try:
        # Run agent with message history
        try:
            result = await agent.run(
                request.text,
                deps=context,
                message_history=message_history if message_history else None
            )
        except Exception as e:
            # Fallback to no message history
            result = await agent.run(
                request.text,
                deps=context
            )
        
        # Save user message BEFORE processing
        message_repo = ChatMessageRepository()
        await message_repo.create_message(
            db, session_id=session_id, role="user", content=request.text,
            metadata=request.metadata or {}
        )
        
        # Process agent response and handle tool calls
        response_data = await agent_service.process_agent_response(context, result)
        
        # Save assistant message AFTER processing
        await message_repo.create_message(
            db, session_id=session_id, role="assistant", content=result.output,
            metadata={"tool_calls": len([part for msg in result.new_messages() for part in msg.parts if hasattr(part, 'tool_name')]) if hasattr(result, 'new_messages') else 0}
        )
        
        return AgentChatResponse(
            text=result.output,
            session_id=UUID(session_id),  # Convert back to UUID for response
            updated_draft_data=response_data.get("updated_draft_data"),
            tool_calls=response_data.get("tool_calls", []),
            metadata=response_data.get("metadata", {})
        )
        
    except Exception as e:
        # Log error and return user-friendly message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection error"
        )