# New API endpoint for agent interactions. 

import logging
from fastapi import APIRouter, HTTPException, Body, Depends, Path as FastApiPath # Removed Request
from typing import Dict, Any, List

# from pydantic_ai.message_history import SQLiteChatMessageHistory # Old import
from pydantic_ai.messages import ModelMessage # For type hinting message lists

# from app.agents.main import get_dynamic_instructions # Removed cassidy_agent from import, now also get_dynamic_instructions
from app.agents.models import ( # Changed import
    AgentUserInput,
    AgentResponseOutput,
    CassidyAgentDependencies,
    ChatSessionState,
    JournalDraft
)
from app.models.user import UserPreferences, UserTemplate # Changed import
from app.repositories import json_repository # For loading prefs/template

# Import the agent creation function from app.agents.main
from app.agents.main import create_cassidy_agent, get_dynamic_instructions
# from app.agents.main import get_dynamic_instructions # Keep commented out for now

logger = logging.getLogger(__name__)
router = APIRouter()

# Placeholder for ChatSessionState persistence - In-memory dictionary for now
# Key: tuple (user_id, session_id)
# Value: ChatSessionState object
# TODO: Replace with actual database persistence (SQLite or other) in a later task.
_session_states: Dict[tuple[str, str], ChatSessionState] = {}

# Placeholder for Chat Message History persistence - In-memory dictionary for now
# Key: tuple (user_id, session_id)
# Value: List[ModelMessage]
_session_chat_histories: Dict[tuple[str, str], List[ModelMessage]] = {}

# Placeholder for User ID - normally this would come from an auth system
# TODO: Integrate with a proper authentication mechanism.
TEMP_USER_ID = "user_123"

# --- Agent Chat Endpoint --- 

@router.post("/chat/{session_id}", response_model=AgentResponseOutput)
async def agent_chat(
    # request: Request, # Removed request parameter
    session_id: str = FastApiPath(..., title="The ID of the chat session"),
    user_input: AgentUserInput = Body(...)
):
    """Processes user input through the Cassidy agent for a given session."""
    user_id = TEMP_USER_ID # Use placeholder user_id

    logger.info(f"Agent chat request for user_id: {user_id}, session_id: {session_id}, input: '{user_input.text}'")

    # 1. Load user preferences and template
    try:
        # First try to load existing preferences and template
        user_prefs = json_repository.load_user_preferences(user_id)
        user_template = json_repository.load_user_template(user_id)
        
        # If either is empty or missing important parts, create defaults
        if not user_prefs or not user_prefs.purpose_statement:
            logger.warning(f"Creating default preferences for user {user_id} as none found or incomplete")
            # Create a reasonable default
            from app.models.user import UserPreferences
            from datetime import datetime
            user_prefs = UserPreferences(
                purpose_statement="General journaling assistance",
                long_term_goals=["Personal growth", "Better self-understanding"],
                known_challenges=["Finding time to reflect"],
                preferred_feedback_style="supportive",
                last_updated=datetime.utcnow()  # Explicitly set last_updated
            )
            # Save the default
            json_repository.save_user_preferences(user_id, user_prefs)
            
        if not user_template or not user_template.sections:
            logger.warning(f"Creating default template for user {user_id} as none found or incomplete")
            # Create a reasonable default with common journal sections
            from app.models.user import UserTemplate, SectionDetailDef
            from datetime import datetime
            user_template = UserTemplate(
                sections={
                    "Events": SectionDetailDef(description="Key events from your day"),
                    "Thoughts": SectionDetailDef(description="Reflections and ideas"),
                    "Feelings": SectionDetailDef(description="Emotional state and mood")
                },
                last_updated=datetime.utcnow()  # Explicitly set last_updated
            )
            # Save the default
            json_repository.save_user_template(user_id, user_template)
        
        # Ensure last_updated is set for both objects
        if not user_prefs.last_updated:
            user_prefs.last_updated = datetime.utcnow()
            
        if not user_template.last_updated:
            user_template.last_updated = datetime.utcnow()
            
    except FileNotFoundError as e:
        logger.error(f"Preferences or template not found for user_id: {user_id}. Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="User preferences or template not found. Cannot initialize agent.")
    except Exception as e:
        logger.error(f"Error loading preferences or template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error loading user data: {str(e)}")

    # 2. Create agent with user preferences
    try:
        agent_instance = await create_cassidy_agent(user_preferences=user_prefs)
    except Exception as e:
        logger.error(f"Exception during agent creation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent creation threw an exception: {str(e)}")
        
    if not agent_instance:
        logger.error("CRITICAL: Failed to create Cassidy agent instance for the request. Agent instance is None.")
        raise HTTPException(status_code=500, detail="Agent not available. Initialization failed.")
    
    if not agent_instance.model:
        logger.error("CRITICAL: Agent instance created, but agent.model is NOT SET.")
        # This check is important to ensure the core issue we were debugging is caught here too.
        raise HTTPException(status_code=500, detail="Agent model not initialized.")

    # 3. Load or create ChatSessionState
    session_state_key = (user_id, session_id)
    if session_state_key not in _session_states:
        logger.info(f"Creating new ChatSessionState for {session_state_key}")
        _session_states[session_state_key] = ChatSessionState(user_id=user_id, session_id=session_id)
        _session_chat_histories[session_state_key] = [] # Initialize empty history
    
    current_session_state = _session_states[session_state_key]
    current_message_history: List[ModelMessage] = _session_chat_histories.get(session_state_key, [])

    if current_session_state.is_journal_entry_finalized:
        # If journal is finalized, we might want different behavior (e.g., start new or just chat)
        # For now, let's just let it respond generally.
        logger.info(f"Journal entry for session {session_id} is already finalized.")
        # We could potentially clear the draft here or prevent further structuring tools.

    # 4. Prepare CassidyAgentDependencies
    agent_deps = CassidyAgentDependencies(
        user_id=user_id,
        current_chat_id=session_id,
        chat_type=current_session_state.chat_type, # Default is 'journaling'
        user_template=user_template,
        user_preferences=user_prefs,
        current_journal_draft=JournalDraft(data=current_session_state.current_journal_draft_data.copy()) # Important to pass a copy
    )

    logger.debug(f"Using in-memory chat history for session: {session_state_key} with {len(current_message_history)} messages.")

    # 5. Run the agent
    try:
        # Check if this is a direct save command
        is_save_command = user_input.text.lower().strip() in ["save", "yes", "finalize", "ok", "save it", "ok save"]
        
        # The @agent.instruction for get_dynamic_instructions will be invoked by Pydantic AI
        logger.info(f"Running agent with user_input: {user_input.text}")
        agent_run_result = await agent_instance.run( # Use agent_instance from app.state
            user_input.text,
            context=agent_deps,
            message_history=current_message_history # Pass the list of messages
        )
        agent_response_text = agent_run_result.output # Get the textual output
        
        # Debug the agent_run_result
        logger.info(f"DEBUG: agent_run_result attributes: {dir(agent_run_result)}")
        logger.info(f"DEBUG: agent_run_result has tool_calls: {hasattr(agent_run_result, 'tool_calls')}")
        
        # Dump more information about the response to diagnose the issue
        logger.info(f"DEBUG: agent_run_result.data: {getattr(agent_run_result, 'data', 'No data attribute')}")
        logger.info(f"DEBUG: Response messages: {agent_run_result.new_messages}")
        
        # FALLBACK: If this was a save command and no tool calls were made,
        # manually invoke the SaveJournal tool
        if is_save_command and (not hasattr(agent_run_result, 'tool_calls') or not agent_run_result.tool_calls):
            logger.warning("Save command detected but no tool calls made - using fallback mechanism")
            
            # Import and call the SaveJournal tool directly
            from app.agents.tools import save_journal
            
            save_result = save_journal(agent_deps)
            logger.info(f"Fallback SaveJournal call result: {save_result}")
            
            # Append confirmation message to agent response if needed
            if "confirmation_message" in save_result:
                if save_result["confirmation_message"] not in agent_response_text:
                    agent_response_text = f"{agent_response_text}\n\n[SYSTEM: {save_result['confirmation_message']}]"
                
                # Mark the journal as finalized
                if "success" in save_result["confirmation_message"].lower():
                    current_session_state.is_journal_entry_finalized = True
                    logger.info(f"Journal entry for session {session_id} has been finalized via fallback mechanism.")
        
        # Update and store the complete message history for the next turn
        _session_chat_histories[session_state_key] = agent_run_result.all_messages()

    except Exception as e:
        logger.error(f"Error during agent execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}")

    logger.info(f"Agent raw response for {session_state_key}: '{agent_response_text}'")

    # 6. Process agent's response and update ChatSessionState (post-tool execution)
    # Now we need to process the agent's response, especially state changes from tools
    try:
        # Get the updated journal draft from the agent response (it might have changed from tools)
        # Look for StructureJournalTool calls to update draft data
        if hasattr(agent_run_result, 'tool_calls') and agent_run_result.tool_calls:
            logger.info(f"DEBUG: Found {len(agent_run_result.tool_calls)} tool calls")
            for i, tool_call in enumerate(agent_run_result.tool_calls):
                logger.info(f"DEBUG: Tool call {i+1}: name={tool_call.name}, has_output={bool(tool_call.output)}")
                
                # Check if StructureJournalTool was called and returned updated data
                if tool_call.name == "StructureJournalTool" and tool_call.output and hasattr(tool_call.output, 'updated_draft_data'):
                    if tool_call.output.updated_draft_data:
                        logger.info(f"StructureJournalTool modified draft: {list(tool_call.output.updated_draft_data.keys())}")
                        # Instead of replacing data, merge with existing to preserve history
                        current_draft = current_session_state.current_journal_draft_data
                        for section, content in tool_call.output.updated_draft_data.items():
                            # If section already exists, append the new content
                            if section in current_draft and current_draft[section]:
                                # Only append if not already present (avoid duplication)
                                if content not in current_draft[section]:
                                    current_draft[section] = f"{current_draft[section]}\n\n{content}"
                            else:
                                # New section, just add it
                                current_draft[section] = content
                        
                        # Update session state with merged data
                        current_session_state.update_draft(current_draft)
                        logger.info(f"Updated draft with merged content: {list(current_draft.keys())}")
                
                # Check if SaveJournal was called
                if tool_call.name == "SaveJournal" and tool_call.output:
                    logger.info(f"DEBUG: SaveJournal tool called, output: {tool_call.output}")
                    
                    # Get the confirmation message from the tool output
                    confirmation_message = None
                    if isinstance(tool_call.output, dict) and "confirmation_message" in tool_call.output:
                        confirmation_message = tool_call.output["confirmation_message"]
                    elif hasattr(tool_call.output, 'confirmation_message'):
                        confirmation_message = tool_call.output.confirmation_message
                    
                    # Check for success
                    if confirmation_message and "success" in confirmation_message.lower():
                        logger.info(f"Journal entry for session {session_id} has been finalized.")
                        current_session_state.is_journal_entry_finalized = True
                    else:
                        # Log the issue, but don't auto-mark as finalized
                        logger.warning(f"SaveJournal may have failed: {confirmation_message}")
                
                # Also check for other possible name variations the tool might have
                possible_save_names = ["save_journal", "save_journal_tool", "finalize_journal", "FinalizeJournal", "SaveJournalTool", "FinalizeJournalToolInstance"]
                if any(name.lower() == tool_call.name.lower() for name in possible_save_names) and tool_call.output:
                    logger.info(f"DEBUG: Alternative save tool name detected: {tool_call.name}")
                    if hasattr(tool_call.output, 'finalized_session_id') and tool_call.output.finalized_session_id:
                        logger.info(f"Journal entry for session {session_id} has been finalized.")
                        current_session_state.is_journal_entry_finalized = True
                    elif hasattr(tool_call.output, 'confirmation_message'):
                        logger.info(f"Journal entry has confirmation but no ID: {tool_call.output.confirmation_message}")
                        current_session_state.is_journal_entry_finalized = True
        else:
            logger.info("DEBUG: No tool_calls found in agent_run_result")
            
            # No tool calls, update the draft directly from context if available
            # We're doing this to capture any direct updates the agent might have made
            if hasattr(agent_deps, 'current_journal_draft') and agent_deps.current_journal_draft.data:
                if agent_deps.current_journal_draft.data != current_session_state.current_journal_draft_data:
                    logger.info("Detected changes to journal draft in context, updating session state")
                    current_session_state.update_draft(agent_deps.current_journal_draft.data)
                    
        # Save the updated session state back to storage
        _session_states[session_state_key] = current_session_state
        logger.debug(f"Updated session state for {session_state_key}: {current_session_state.model_dump_json(indent=2)}")
    except Exception as e:
        logger.error(f"Error processing agent tool results: {e}", exc_info=True)
        # We'll still return the agent's text response even if processing tools failed

    return AgentResponseOutput(
        text=agent_response_text,
        updated_structured_data=current_session_state.current_journal_draft_data
    )

# TODO: Add this router to the main FastAPI app in backend/app/main.py 