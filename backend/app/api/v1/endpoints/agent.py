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
    print(f"Agent chat endpoint called with session_id: {session_id}, text: {request.text}")
    
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
    
    # Get agent for conversation type
    agent = await AgentFactory.get_agent(session.conversation_type)
    
    # Load message history
    message_history = await agent_service.get_message_history(session_id)
    print(f"Loaded {len(message_history)} messages from history")
    
    try:
        # Run agent with context
        print(f"About to run agent with text: {request.text}")
        print(f"Context: {context}")
        print(f"Agent tools: {[str(tool) for tool in agent.tools] if hasattr(agent, 'tools') else 'No tools attr'}")
        print(f"Message history format: {message_history[:1] if message_history else 'Empty'}")
        
        # Run agent with message history
        try:
            print(f"Running agent with {len(message_history)} messages in history")
            result = await agent.run(
                request.text,
                deps=context,
                message_history=message_history if message_history else None
            )
        except Exception as e:
            print(f"Failed with message_history: {e}")
            print(f"Error type: {type(e)}")
            # Fallback to no message history
            result = await agent.run(
                request.text,
                deps=context
            )
        print(f"Agent run completed successfully")
        print(f"Result has tool calls: {hasattr(result, 'all_tool_calls')}")
        if hasattr(result, 'all_tool_calls'):
            tool_calls = result.all_tool_calls()
            print(f"Number of tool calls: {len(tool_calls)}")
            for call in tool_calls:
                print(f"  Tool call: {call.tool_name if hasattr(call, 'tool_name') else call}")
        else:
            print(f"Result type: {type(result)}")
            print(f"Result attributes: {dir(result)}")
        
        # Save user message
        message_repo = ChatMessageRepository()
        print("About to save user message")
        await message_repo.create_message(
            db, session_id=session_id, role="user", content=request.text,
            metadata=request.metadata or {}
        )
        
        # Save assistant message
        print("About to save assistant message")
        await message_repo.create_message(
            db, session_id=session_id, role="assistant", content=result.output,
            metadata={"tool_calls": len([part for msg in result.new_messages() for part in msg.parts if hasattr(part, 'tool_name')]) if hasattr(result, 'new_messages') else 0}
        )
        
        # Process agent response and handle tool calls
        response_data = await agent_service.process_agent_response(context, result)
        
        return AgentChatResponse(
            text=result.output,
            session_id=UUID(session_id),  # Convert back to UUID for response
            updated_draft_data=response_data.get("updated_draft_data"),
            tool_calls=response_data.get("tool_calls", []),
            metadata=response_data.get("metadata", {})
        )
        
    except Exception as e:
        # Log error and return user-friendly message
        print(f"Agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sorry, I encountered an error while processing your request. Please try again."
        )