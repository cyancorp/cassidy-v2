from fastapi import APIRouter, HTTPException, Body, Depends
from datetime import datetime
import logging
from pydantic import BaseModel
from typing import List, Dict, Any

from app import repositories
from app.services import anthropic_service
from app.models.user import UserPreferences
from app.models.session import SessionStructuredContent
from app.models.common import SessionInfo

router = APIRouter()
logger = logging.getLogger(__name__)

# --- In-memory storage for conversation history (simple approach for now) ---
# Warning: This will be lost if the server restarts!
# A more robust solution would use files or a database.
session_histories: Dict[str, List[Dict[str, str]]] = {}
# --------------------------------------------------------------------------

# --- Request/Response Models --- 
class SubmitRawInputRequest(BaseModel):
    # Removed session_id, will be path parameter
    raw_text: str

# Removed SaveStructuredContentRequest for now, focus on submit_raw

class ProcessResponse(BaseModel):
    """Response model including structured data, chat response, and user preferences."""
    structured_content: SessionStructuredContent
    chat_response: str
    user_preferences: UserPreferences

# --- Session Endpoints --- 

@router.post("/start", response_model=SessionInfo) # Return session ID
async def start_new_session():
    session_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    logger.info(f"Starting new session with ID: {session_id}")
    
    # Initialize empty history for the new session
    session_histories[session_id] = [] 
    
    # Save initial (empty) preferences and default template if they don't exist
    # Ensures they are available for the first submit_raw call
    _ = repositories.load_user_preferences() # Loads default if not exists
    _ = repositories.load_user_template()   # Loads default if not exists

    # No need to save raw input here anymore, just return ID
    return SessionInfo(session_id=session_id)

# Changed endpoint to include session_id in path
@router.post("/{session_id}/submit_raw", response_model=ProcessResponse)
async def submit_raw_input_for_session(
    session_id: str, 
    payload: SubmitRawInputRequest = Body(...)
):
    logger.info(f"[{session_id}] Received raw input: '{payload.raw_text[:50]}...'")
    
    # --- 1. Structuring Task --- 
    structured_content = anthropic_service.structure_raw_input(
        session_id=session_id, 
        raw_text=payload.raw_text
    )
    if structured_content is None:
        logger.error(f"[{session_id}] Structuring service failed.")
        raise HTTPException(status_code=500, detail="Failed to structure input using AI service.")
    
    # --- 2. Preference Extraction Task --- 
    potential_updates = anthropic_service.extract_preference_updates(
        session_id=session_id,
        raw_text=payload.raw_text
    )
    if potential_updates is None:
        logger.warning(f"[{session_id}] Preference extraction failed. Proceeding without updates.")
        potential_updates = {} 
        
    # --- 3. Update & Save Preferences --- 
    user_prefs = repositories.load_user_preferences() 
    logger.debug(f"[{session_id}] Loaded initial prefs: {user_prefs.model_dump()}") # Log initial load
    updated_prefs_data = user_prefs.model_dump() 
    prefs_changed = False
    
    logger.debug(f"[{session_id}] Potential preference updates from extraction: {potential_updates}") # Log extraction output

    # Update Main Purpose Statement
    if "purpose_statement" in potential_updates and isinstance(potential_updates["purpose_statement"], str):
        new_purpose = potential_updates["purpose_statement"].strip()
        if new_purpose and updated_prefs_data["purpose_statement"] != new_purpose:
            logger.info(f"[{session_id}] Detected purpose change: '{updated_prefs_data['purpose_statement']}' -> '{new_purpose}'") # Log detected change
            updated_prefs_data["purpose_statement"] = new_purpose
            prefs_changed = True
        else:
            logger.debug(f"[{session_id}] Extracted purpose '{new_purpose}' matches existing or is empty. No change.")
    else:
        logger.debug(f"[{session_id}] No valid 'purpose_statement' key found in potential updates.")

    # Merge Goals (append new unique goals)
    if "new_long_term_goals" in potential_updates and isinstance(potential_updates["new_long_term_goals"], list):
        new_goals = [goal for goal in potential_updates["new_long_term_goals"] 
                     if isinstance(goal, str) and goal not in updated_prefs_data["long_term_goals"]]
        if new_goals:
            updated_prefs_data["long_term_goals"].extend(new_goals)
            prefs_changed = True
            logger.info(f"[{session_id}] Adding new goals: {new_goals}")
        else:
            logger.debug(f"[{session_id}] No new unique long-term goals extracted.")

    # Merge Challenges (append new unique challenges)
    if "new_known_challenges" in potential_updates and isinstance(potential_updates["new_known_challenges"], list):
        new_challenges = [challenge for challenge in potential_updates["new_known_challenges"] 
                          if isinstance(challenge, str) and challenge not in updated_prefs_data["known_challenges"]]
        if new_challenges:
            updated_prefs_data["known_challenges"].extend(new_challenges)
            prefs_changed = True
            logger.info(f"[{session_id}] Adding new challenges: {new_challenges}")

    # Merge Glossary (update/add new terms)
    if "new_personal_glossary" in potential_updates and isinstance(potential_updates["new_personal_glossary"], dict):
        for term, definition in potential_updates["new_personal_glossary"].items():
            if isinstance(term, str) and isinstance(definition, str):
                 if updated_prefs_data["personal_glossary"].get(term) != definition:
                     updated_prefs_data["personal_glossary"][term] = definition
                     prefs_changed = True
                     logger.info(f"[{session_id}] Updating glossary: '{term}': '{definition[:30]}...'")

    # Update Feedback Style
    if "preferred_feedback_style" in potential_updates and isinstance(potential_updates["preferred_feedback_style"], str):
        new_style = potential_updates["preferred_feedback_style"]
        # Basic validation, could be stricter with Enum
        if new_style in ["direct", "supportive"] and updated_prefs_data["preferred_feedback_style"] != new_style:
             updated_prefs_data["preferred_feedback_style"] = new_style
             prefs_changed = True
             logger.info(f"[{session_id}] Updating feedback style to: {new_style}")

    # Log final decision before saving
    logger.debug(f"[{session_id}] Prefs changed flag: {prefs_changed}")

    # Save if changes were made
    if prefs_changed:
        logger.info(f"[{session_id}] Attempting to save updated preferences...")
        try:
            updated_prefs_model = UserPreferences(**updated_prefs_data)
            logger.debug(f"[{session_id}] Validated updated prefs model: {updated_prefs_model.model_dump()}")
            save_success = repositories.save_user_preferences(updated_prefs_model)
            if save_success:
                logger.info(f"[{session_id}] Successfully saved updated preferences.")
                user_prefs = updated_prefs_model 
            else:
                logger.error(f"[{session_id}] Failed to save updated preferences (save_user_preferences returned False), continuing with old ones.")
        except Exception as e:
            logger.error(f"[{session_id}] Error validating/saving updated preferences: {e}. Continuing with old ones.")
    else:
         logger.info(f"[{session_id}] No preference updates identified or needed saving.")

    # Log the prefs object being used for the rest of the request
    logger.debug(f"[{session_id}] Final user_prefs object being used: {user_prefs.model_dump()}")

    # We now have the latest applicable user_prefs (either original or updated and saved)
    logger.debug(f"[{session_id}] Prefs used for conversation prompt: {user_prefs}")

    # --- 4. Save Structured Content --- 
    success_structured = repositories.save_session_data(session_id, structured_content)
    if not success_structured:
        logger.warning(f"[{session_id}] Failed to save structured content.")

    # --- 5. Retrieve Context for Conversation --- 
    current_history = session_histories.get(session_id, [])

    # --- 6. Conversation Task --- 
    chat_response = anthropic_service.generate_conversational_response(
        session_id=session_id,
        last_user_message=payload.raw_text,
        conversation_history=current_history, 
        prefs=user_prefs, 
        latest_structured_content=structured_content 
    )
    if chat_response is None:
        logger.error(f"[{session_id}] Conversational response generation failed.")
        chat_response = "(I encountered an issue generating a response. Please try again.)"

    # --- 7. Update Conversation History (In-memory) --- 
    current_history.append({"role": "user", "content": payload.raw_text})
    current_history.append({"role": "assistant", "content": chat_response})
    history_limit = 20 
    session_histories[session_id] = current_history[-history_limit:]

    # --- 8. Return Combined Response --- 
    logger.info(f"[{session_id}] Returning structured content, chat response, and preferences.")
    return ProcessResponse(
        structured_content=structured_content,
        chat_response=chat_response,
        user_preferences=user_prefs # Return the latest prefs used
    )

# Removed /save_structured endpoint for now to simplify

# TODO: Add endpoints later for:
# - Retrieving structured content (GET /session/{session_id}/structured)
# - Retrieving conversation history (GET /session/{session_id}/conversation) 
# - Need persistent storage for conversation history 