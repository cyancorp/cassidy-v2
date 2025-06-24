from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import json
import asyncio

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
    
    # Get agent for conversation type with user_id and context
    agent = await AgentFactory.get_agent(session.conversation_type, current_user.id, context)
    
    # Load message history
    message_history = await agent_service.get_message_history(session_id)
    
    try:
        # Run agent with message history
        print(f"[DEBUG] About to call agent.run() with text: '{request.text[:100]}{'...' if len(request.text) > 100 else ''}'")
        print(f"[DEBUG] Message history length: {len(message_history) if message_history else 0}")
        print(f"[DEBUG] Context user_id: {context.user_id}, session_id: {context.session_id}")
        
        import time
        start_time = time.time()
        
        try:
            # Test basic internet connectivity first
            print(f"[DEBUG] Testing basic internet connectivity...")
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    response = await client.get("https://httpbin.org/get")
                    print(f"[DEBUG] Basic internet connectivity test: {response.status_code}")
                except Exception as conn_e:
                    print(f"[DEBUG] Basic internet connectivity FAILED: {conn_e}")
                
                try:
                    response = await client.get("https://api.anthropic.com/")
                    print(f"[DEBUG] Anthropic API connectivity test: {response.status_code}")
                except Exception as conn_e:
                    print(f"[DEBUG] Anthropic API connectivity FAILED: {conn_e}")
            
            print(f"[DEBUG] Calling agent.run() with message history...")
            result = await agent.run(
                request.text,
                deps=context,
                message_history=message_history if message_history else None
            )
            print(f"[DEBUG] agent.run() completed successfully in {time.time() - start_time:.2f}s")
        except Exception as e:
            print(f"[DEBUG] agent.run() with history failed after {time.time() - start_time:.2f}s: {e}")
            print(f"[DEBUG] Falling back to agent.run() without history...")
            start_time = time.time()
            result = await agent.run(
                request.text,
                deps=context
            )
            print(f"[DEBUG] agent.run() fallback completed in {time.time() - start_time:.2f}s")
        
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


@router.post("/chat/{session_id}/stream")
async def agent_chat_stream(
    session_id: str,
    request: AgentChatRequest,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Streaming agent chat endpoint using Server-Sent Events"""
    
    # Verify session belongs to user
    session_repo = ChatSessionRepository()
    session = await session_repo.get_by_id(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    async def stream_generator():
        try:
            # Create agent service and context
            agent_service = AgentService(db)
            context = await agent_service.create_agent_context(
                current_user.id, session_id, session.conversation_type
            )
            
            # Get agent for conversation type with user_id and context
            agent = await AgentFactory.get_agent(session.conversation_type, current_user.id, context)
            
            # Load message history
            message_history = await agent_service.get_message_history(session_id)
            
            # Save user message BEFORE processing
            message_repo = ChatMessageRepository()
            await message_repo.create_message(
                db, session_id=session_id, role="user", content=request.text,
                metadata=request.metadata or {}
            )
            
            # Stream the agent response
            full_response = ""
            previous_text = ""
            result = None
            
            async with agent.run_stream(
                request.text,
                deps=context,
                message_history=message_history if message_history else None
            ) as response:
                # Stream without delta=True to get accumulated text
                async for text_chunk in response.stream_text():
                    # Calculate the actual delta by comparing with previous text
                    delta = text_chunk[len(previous_text):] if len(text_chunk) > len(previous_text) else ""
                    
                    if delta:
                        # Send only the new delta as Server-Sent Event
                        event_data = {
                            "type": "text_delta",
                            "content": delta,
                            "session_id": session_id
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                    
                    previous_text = text_chunk
                    full_response = text_chunk  # Keep the final full response
                
                # Get the actual result after streaming
                result = response
            
            # Process agent response for tool calls after streaming completes
            response_data = await agent_service.process_agent_response(context, result)
            
            # Send tool calls if any
            if response_data.get("tool_calls"):
                tool_event = {
                    "type": "tool_calls",
                    "tool_calls": response_data["tool_calls"],
                    "session_id": session_id
                }
                yield f"data: {json.dumps(tool_event)}\n\n"
            
            # Send completion event with metadata
            completion_event = {
                "type": "completion",
                "session_id": session_id,
                "updated_draft_data": response_data.get("updated_draft_data"),
                "metadata": response_data.get("metadata", {}),
                "full_text": full_response
            }
            yield f"data: {json.dumps(completion_event)}\n\n"
            
            # Save assistant message AFTER processing
            await message_repo.create_message(
                db, session_id=session_id, role="assistant", content=full_response,
                metadata={"tool_calls": len(response_data.get("tool_calls", []))}
            )
            
        except Exception as e:
            # Send error event
            error_event = {
                "type": "error",
                "error": str(e),
                "session_id": session_id
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )