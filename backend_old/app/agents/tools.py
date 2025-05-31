# Tool definitions for the Pydantic AI agent. 
from datetime import datetime
from pydantic_ai.tools import Tool
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.agents.models import CassidyAgentDependencies # Changed import
from app.models.user import UserPreferences # Changed import
from app.models.session import SessionStructuredContent
from app.services import anthropic_service
from app.repositories import json_repository

class StructureJournalInput(BaseModel):
    user_text: str = Field(..., description="The raw text input from the user that needs to be structured for the journal.")

class StructureJournalOutput(BaseModel):
    updated_draft_data: Optional[Dict[str, Any]] = Field(None, description="The journal draft data after attempting to structure the user_text into it.")
    status: str = Field(..., description="A message indicating the outcome of the structuring attempt.")

class UpdatePreferencesInput(BaseModel):
    user_text: str = Field(..., description="The raw text input from the user that might contain updates to their preferences.")

class UpdatePreferencesOutput(BaseModel):
    updated_preferences_data: Optional[UserPreferences] = Field(None, description="The user's preferences after attempting to extract and apply updates from the user_text.")
    status: str = Field(..., description="A message indicating the outcome of the preference update attempt.")

# Keep the SaveJournalInput class for reference but don't use it in the Tool constructor
class SaveJournalInput(BaseModel):
    """Empty input model for the SaveJournal tool"""
    pass

class FinalizeJournalOutput(BaseModel):
    confirmation_message: str = Field(..., description="A message confirming the journal entry has been finalized and saved.")
    finalized_session_id: Optional[str] = Field(None, description="The session ID of the finalized journal entry.")

# Standalone functions for tool logic

def _structure_journal_entry_run(ctx: CassidyAgentDependencies, args: StructureJournalInput) -> StructureJournalOutput:
    """Logic for StructureJournalEntryTool."""
    # Check if a context has been provided
    if not ctx or not isinstance(ctx, CassidyAgentDependencies):
        print("WARNING: ctx is not a CassidyAgentDependencies object, creating fallback")
        # Handle missing context by creating a fallback context
        try:
            # Try to load preferences and template
            from app.repositories import json_repository
            from app.api.v1.endpoints.agent import TEMP_USER_ID

            # Default IDs
            user_id = TEMP_USER_ID
            session_id = "unknown_session" 

            # Try to load preferences from file
            try:
                preferences = json_repository.load_user_preferences(user_id)
            except Exception as e:
                print(f"Error loading preferences: {e}")
                from app.models.user import UserPreferences
                from datetime import datetime
                preferences = UserPreferences(
                    purpose_statement="General journaling assistance",
                    long_term_goals=["Personal growth"],
                    known_challenges=[],
                    last_updated=datetime.utcnow()
                )

            # Try to load template from file
            try:
                template = json_repository.load_user_template(user_id)
            except Exception as e:
                print(f"Error loading template: {e}")
                from app.models.user import UserTemplate
                from datetime import datetime
                template = UserTemplate(sections={}, last_updated=datetime.utcnow())

            # Create an empty draft
            from app.agents.models import JournalDraft
            draft = JournalDraft()
        
            # Create a new context object
            try:
                ctx = CassidyAgentDependencies(
                    user_id=user_id,
                    current_chat_id=session_id,
                    chat_type="journaling",
                    user_template=template,
                    user_preferences=preferences,
                    current_journal_draft=draft
                )
                print("Created default context object")
            except Exception as e:
                print(f"Error creating default context: {e}")
                # Return a fallback response
                return StructureJournalOutput(
                    status=f"An internal error occurred: {str(e)}. Please try again.",
                    updated_draft_data={"Thoughts": args.user_text}
                )
        except Exception as e:
            print(f"Failed to create fallback context: {e}")
            return StructureJournalOutput(
                status="Internal error occurred. Please try again.",
                updated_draft_data={"Thoughts": args.user_text}
            )
    
    # Get session ID and user ID, with fallbacks / recovery
    session_id = getattr(ctx, "current_chat_id", None)
    user_id = getattr(ctx, "user_id", None)

    if not session_id or not user_id or session_id == "unknown_session":
        # Attempt to recover a valid session_id from in-memory session state
        print("Missing or placeholder session_id/user_id detected. Attempting recovery …")
        try:
            from app.api.v1.endpoints.agent import _session_states, TEMP_USER_ID

            if not user_id:
                user_id = TEMP_USER_ID

            # Look for an existing session for this user
            candidate_keys = [k for k in _session_states.keys() if k[0] == user_id]
            if candidate_keys:
                # Naively pick the most recently updated (last in list)
                session_id = candidate_keys[-1][1]
                print(f"Recovered session_id '{session_id}' for user '{user_id}' from _session_states")
            else:
                # Still nothing – use placeholder values
                session_id = session_id or "unknown_session"
        except Exception as rec_exc:
            print(f"Recovery attempt failed: {rec_exc}")
            from app.api.v1.endpoints.agent import TEMP_USER_ID
            session_id = session_id or "unknown_session"
            user_id = user_id or TEMP_USER_ID
    
    # First try to get existing journal content from session state
    print(f"StructureJournalTool called with session: {session_id}, user: {user_id}")
    print(f"Processing text: {args.user_text[:100]}...")
    
    # Try to get existing content from session state
    existing_draft_data = {}
    
    # First check if we have a session state with draft data
    from app.api.v1.endpoints.agent import _session_states
    session_state_key = (user_id, session_id)
    
    if session_state_key in _session_states:
        existing_draft_data = _session_states[session_state_key].current_journal_draft_data
        print(f"Found existing draft in session state with keys: {list(existing_draft_data.keys() if existing_draft_data else [])}")
    
    # If no session state or empty, fallback to context
    if not existing_draft_data and hasattr(ctx, "current_journal_draft") and ctx.current_journal_draft and ctx.current_journal_draft.data:
        existing_draft_data = ctx.current_journal_draft.data
        print(f"Using existing draft from context with keys: {list(existing_draft_data.keys() if existing_draft_data else [])}")
    
    # Get template sections - with defensive checks
    template_sections = []
    
    if hasattr(ctx, "user_template") and ctx.user_template and hasattr(ctx.user_template, "sections") and ctx.user_template.sections:
        template_sections = list(ctx.user_template.sections.keys())
        print(f"Template sections: {template_sections}")
    else:
        # Try to load the user's template from storage before giving up
        try:
            template_from_disk = json_repository.load_user_template(user_id)
            if template_from_disk and template_from_disk.sections:
                ctx.user_template = template_from_disk  # Update context for rest of the run
                template_sections = list(template_from_disk.sections.keys())
                print(f"Loaded template from disk with sections: {template_sections}")
            else:
                raise ValueError("No sections in loaded template")
        except Exception as tmpl_exc:
            print(f"Unable to load template from disk: {tmpl_exc}. Using fallback template.")
            template_sections = ["Thoughts", "Emotions", "Tasks"]
            print(f"Created fallback template with sections: {template_sections}")
    
    # Process the user's text to structure it
    raw_text = args.user_text
    
    try:
        # Use Anthropic service to structure the content
        from app.services import anthropic_service
        
        # FIXED: Pass the correct user_id from context, not a hardcoded value
        print(f"TOOL DEBUG: Using user_id '{user_id}' for structuring content")
        structured_content = anthropic_service.structure_raw_input(session_id, raw_text, user_id=user_id)
        
        # In case of JSON parsing error, fall back to simple structuring
        if not structured_content or not structured_content.data:
            print("Failed to structure content with AI, using fallback approach.")
            
            # Simple fallback: put all content in first section
            if template_sections:
                fallback_data = {}
                fallback_data[template_sections[0]] = raw_text
                structured_data = fallback_data
            else:
                structured_data = {"Content": raw_text}
        else:
            structured_data = structured_content.data
            print(f"Successfully structured content with keys: {list(structured_data.keys() if structured_data else [])}")
        
        # Update the draft with the structured data
        updated_draft_data = {}
        
        # If we have existing data, merge the new structured data with it
        if existing_draft_data:
            updated_draft_data = existing_draft_data.copy()
            # Update or add new sections
            for key, value in structured_data.items():
                if key in updated_draft_data:
                    # If key exists, append new content with separator
                    updated_draft_data[key] = f"{updated_draft_data[key]}\n\n{value}"
                else:
                    # If key doesn't exist, add it
                    updated_draft_data[key] = value
        else:
            # No existing data, just use the structured data
            updated_draft_data = structured_data
        
        print(f"Updated draft now has keys: {list(updated_draft_data.keys() if updated_draft_data else [])}")
        
        # Update the session state if it exists
        if session_state_key in _session_states:
            _session_states[session_state_key].update_draft(updated_draft_data)
            print(f"Updated session state with new draft data")
        
        # Also update the context for good measure
        if hasattr(ctx, "current_journal_draft"):
            ctx.current_journal_draft.data = updated_draft_data
            print("Updated context current_journal_draft")
        
        # Return the successful result
        return StructureJournalOutput(
            status="Successfully processed your journal entry.",
            updated_draft_data=updated_draft_data
        )
    except Exception as e:
        print(f"Error processing journal entry: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback response in case of error
        return StructureJournalOutput(
            status=f"An error occurred while processing your journal entry: {str(e)}. Please try again.",
            updated_draft_data=existing_draft_data  # Return existing data unmodified
        )

def _update_preferences_run(ctx: CassidyAgentDependencies, args: UpdatePreferencesInput) -> UpdatePreferencesOutput:
    """Logic for UpdatePreferencesTool."""
    print(f"UpdatePreferencesTool called with text: {args.user_text[:100]}...")
    print(f"Current preferences before update: {ctx.user_preferences.model_dump_json(indent=2)}")
    
    # Ensure that datetime fields are properly set
    if not ctx.user_template.last_updated or isinstance(ctx.user_template.last_updated, str) and not ctx.user_template.last_updated:
        print("Setting missing last_updated for user_template")
        ctx.user_template.last_updated = datetime.utcnow()
    if not ctx.user_preferences.last_updated or isinstance(ctx.user_preferences.last_updated, str) and not ctx.user_preferences.last_updated:
        print("Setting missing last_updated for user_preferences")
        ctx.user_preferences.last_updated = datetime.utcnow()
    
    try:
        # Extract preference updates from text
        session_id = ctx.current_chat_id
        user_id = ctx.user_id
        
        # Get preference updates from the text
        updates = anthropic_service.extract_preference_updates(session_id, args.user_text)
        
        if not updates:
            print(f"No preference updates extracted from text for session {session_id}")
            return UpdatePreferencesOutput(
                updated_preferences_data=ctx.user_preferences,
                status="No new preference information was found in your message."
            )
        
        # Create a copy of the current preferences
        updated_prefs = ctx.user_preferences.model_copy(deep=True)
        
        # Update purpose statement if present
        if 'purpose_statement' in updates and updates['purpose_statement']:
            updated_prefs.purpose_statement = updates['purpose_statement']
            print(f"Updated purpose statement: {updated_prefs.purpose_statement}")
        
        # Update long-term goals if present
        if 'long_term_goals' in updates and updates['long_term_goals']:
            # For array fields, merge new items with existing ones, avoiding duplicates
            existing_goals = set(updated_prefs.long_term_goals)
            for goal in updates['long_term_goals']:
                existing_goals.add(goal)
            updated_prefs.long_term_goals = list(existing_goals)
            print(f"Updated long_term_goals: {updated_prefs.long_term_goals}")
        
        # Update known challenges if present
        if 'known_challenges' in updates and updates['known_challenges']:
            existing_challenges = set(updated_prefs.known_challenges)
            for challenge in updates['known_challenges']:
                existing_challenges.add(challenge)
            updated_prefs.known_challenges = list(existing_challenges)
            print(f"Updated known_challenges: {updated_prefs.known_challenges}")
        
        # Update feedback style if present
        if 'preferred_feedback_style' in updates and updates['preferred_feedback_style']:
            updated_prefs.preferred_feedback_style = updates['preferred_feedback_style']
            print(f"Updated preferred_feedback_style: {updated_prefs.preferred_feedback_style}")
        
        # Update personal glossary if present
        if 'personal_glossary' in updates and updates['personal_glossary']:
            updated_prefs.personal_glossary.update(updates['personal_glossary'])
            print(f"Updated personal_glossary with {len(updates['personal_glossary'])} terms")
        
        # Update last_updated timestamp
        updated_prefs.last_updated = datetime.utcnow()
        
        # Save the updated preferences to storage
        save_success = json_repository.save_user_preferences(user_id, updated_prefs)
        
        if save_success:
            print(f"Successfully saved updated preferences for user {user_id}")
            return UpdatePreferencesOutput(
                updated_preferences_data=updated_prefs,
                status="Your preferences have been updated based on new information in your message."
            )
        else:
            print(f"Failed to save updated preferences for user {user_id}")
            return UpdatePreferencesOutput(
                updated_preferences_data=updated_prefs,  # Still return updated prefs even if saving failed
                status="Your preferences were updated in memory but couldn't be saved to storage."
            )
            
    except Exception as e:
        print(f"Error in UpdatePreferencesTool: {e}")
        return UpdatePreferencesOutput(
            updated_preferences_data=ctx.user_preferences,  # Return original unchanged
            status=f"An error occurred while updating your preferences: {str(e)}"
        )

def _finalize_journal_run(ctx: CassidyAgentDependencies) -> FinalizeJournalOutput:
    """Logic for FinalizeJournalEntryTool."""
    print("\n----- FINALIZE JOURNAL TOOL CALLED -----")
    print(f"TOOL DEBUG: Tool function: _finalize_journal_run")
    print(f"TOOL DEBUG: Context type: {type(ctx)}")
    
    # Ensure we have valid session_id and user_id
    if not isinstance(ctx, CassidyAgentDependencies):
        print("WARNING: ctx is not a CassidyAgentDependencies object")
        return FinalizeJournalOutput(
            confirmation_message="Unable to finalize journal entry due to a technical issue. Please try again.",
            finalized_session_id=None
        )
        
    session_id = getattr(ctx, "current_chat_id", None)
    user_id = getattr(ctx, "user_id", None)
    
    print(f"TOOL DEBUG: Session ID: {session_id}, User ID: {user_id}")
    
    if not session_id or not user_id or session_id == "unknown_session":
        print("Missing or placeholder session_id/user_id in FinalizeJournal tool. Attempting recovery …")
        try:
            from app.api.v1.endpoints.agent import _session_states, TEMP_USER_ID

            if not user_id:
                user_id = TEMP_USER_ID

            candidate_keys = [k for k in _session_states.keys() if k[0] == user_id]
            if candidate_keys:
                session_id = candidate_keys[-1][1]
                print(f"Recovered session_id '{session_id}' for user '{user_id}' from _session_states")
            else:
                session_id = session_id or "unknown_session"
        except Exception as rec_exc:
            print(f"Recovery attempt failed: {rec_exc}")
            from app.api.v1.endpoints.agent import TEMP_USER_ID
            session_id = session_id or "unknown_session"
            user_id = user_id or TEMP_USER_ID
    
    print(f"FinalizeJournalEntryTool called for chat_id: {session_id}, user_id: {user_id}")
    
    # Get the full journal content from session state
    from app.api.v1.endpoints.agent import _session_states
    session_state_key = (user_id, session_id)
    
    # Initialize journal_content as an empty dict in case we don't find any content
    journal_content = {}
    
    # Try to get content from session state first
    if session_state_key in _session_states:
        session_state = _session_states[session_state_key]
        journal_content = session_state.current_journal_draft_data
        print(f"Retrieved journal content from session state: {list(journal_content.keys() if journal_content else [])}")
    # Fall back to context if session state not available or empty
    if (not journal_content or len(journal_content) == 0) and hasattr(ctx, 'current_journal_draft') and ctx.current_journal_draft and ctx.current_journal_draft.data:
        journal_content = ctx.current_journal_draft.data
        print(f"Using journal content from context: {list(journal_content.keys() if journal_content else [])}")
    
    # Last resort: return error if no content available
    if not journal_content or len(journal_content) == 0:
        print("No journal content found in either session state or context")
        return FinalizeJournalOutput(
            confirmation_message="There's no journal content to finalize. Please add some content first.",
            finalized_session_id=None
        )
    
    print(f"Finalizing draft with keys: {list(journal_content.keys() if journal_content else [])}")
    
    # Ensure that datetime fields are properly set
    if hasattr(ctx, 'user_template') and ctx.user_template and hasattr(ctx.user_template, 'last_updated'):
        if not ctx.user_template.last_updated or isinstance(ctx.user_template.last_updated, str) and not ctx.user_template.last_updated:
            print("Setting missing last_updated for user_template")
            from datetime import datetime
            ctx.user_template.last_updated = datetime.utcnow()
            
    if hasattr(ctx, 'user_preferences') and ctx.user_preferences and hasattr(ctx.user_preferences, 'last_updated'):
        if not ctx.user_preferences.last_updated or isinstance(ctx.user_preferences.last_updated, str) and not ctx.user_preferences.last_updated:
            print("Setting missing last_updated for user_preferences")
            from datetime import datetime
            ctx.user_preferences.last_updated = datetime.utcnow()
    
    try:
        # Check if there's actual content to save
        if not journal_content:
            return FinalizeJournalOutput(
                confirmation_message="There's no journal content to finalize. Please add some content first.",
                finalized_session_id=None
            )
        
        # If data is not yet structured according to template, attempt to structure it now
        default_sections = ["Thoughts", "Emotions", "Tasks"]
        template_sections = []
        
        if hasattr(ctx, 'user_template') and ctx.user_template and hasattr(ctx.user_template, 'sections') and ctx.user_template.sections:
            template_sections = list(ctx.user_template.sections.keys())
        else:
            template_sections = default_sections
        
        if len(journal_content) == 1 and ('content' in journal_content or 'raw' in journal_content):
            # Get the raw content
            raw_content = journal_content.get('content', '') or journal_content.get('raw', '')
            print(f"Content needs structuring before finalizing. Raw content: {raw_content[:100]}...")
            
            # Try to structure the content
            from app.services import anthropic_service
            # FIXED: Pass the correct user_id to structure_raw_input
            print(f"TOOL DEBUG: Using user_id '{user_id}' for final structuring")
            structured_content = anthropic_service.structure_raw_input(session_id, raw_content, user_id=user_id)
            
            if structured_content and structured_content.data:
                # Use the structured data
                final_data = structured_content.data
                print(f"Successfully structured content before finalizing with sections: {list(final_data.keys())}")
            else:
                # If structuring fails, use a simple approach to distribute content to template sections
                final_data = {}
                
                if template_sections:
                    # If we have template sections, put the content in the first section
                    first_section = template_sections[0]
                    final_data[first_section] = raw_content
                    
                    # Add empty strings for other sections to match template
                    for section in template_sections[1:]:
                        final_data[section] = ""
                        
                    print(f"Fallback structuring applied, using sections: {list(final_data.keys())}")
                else:
                    # No template sections, just use the raw content
                    final_data = {"Content": raw_content}
                    print("No template sections available, using generic Content section")
        else:
            # Data already appears to be structured, use as is
            final_data = journal_content.copy()
            print(f"Using existing structured data with sections: {list(final_data.keys())}")
        
        # Create a SessionStructuredContent object
        from app.models.session import SessionStructuredContent
        structured_content = SessionStructuredContent(
            session_id=session_id,
            data=final_data,
            user_edited=True  # Mark as explicitly finalized by user
        )
        
        # Save the structured content to permanent storage with the user_id
        from app.repositories import json_repository
        print(f"TOOL DEBUG: About to save session data with user_id={user_id}, session_id={session_id}")
        save_success = json_repository.save_session_data(
            session_id=session_id, 
            data=structured_content,
            user_id=user_id
        )
        
        if save_success:
            print(f"Successfully saved finalized journal for session {session_id}")
            
            # Update session state to mark as finalized if available
            if session_state_key in _session_states:
                _session_states[session_state_key].is_journal_entry_finalized = True
                print(f"Updated session state to mark journal as finalized for {session_state_key}")
            
            # Return success message
            print("TOOL DEBUG: Returning success message from SaveJournal tool")
            return FinalizeJournalOutput(
                confirmation_message="Your journal entry has been finalized and saved successfully. You can start a new journal entry or continue chatting.",
                finalized_session_id=session_id
            )
        else:
            print(f"Failed to save finalized journal for session {session_id}")
            return FinalizeJournalOutput(
                confirmation_message="There was an error saving your journal entry. Please try again or contact support if the issue persists.",
                finalized_session_id=None
            )
            
    except Exception as e:
        print(f"Error in FinalizeJournalEntryTool: {e}")
        import traceback
        traceback.print_exc()
        return FinalizeJournalOutput(
            confirmation_message=f"An error occurred while finalizing your journal entry: {str(e)}",
            finalized_session_id=None
        )
    finally:
        print("----- FINALIZE JOURNAL TOOL COMPLETED -----\n")

# First, define a simple direct function for saving journal
def save_journal(ctx: CassidyAgentDependencies, args: SaveJournalInput = None) -> Dict[str, Any]:
    """
    Direct function to save a journal entry without any arguments.
    """
    print("\n===== DIRECT SAVE JOURNAL FUNCTION CALLED =====")
    print(f"TOOL DEBUG: save_journal called with ctx type: {type(ctx)}")
    print(f"TOOL DEBUG: Context user_id: {getattr(ctx, 'user_id', 'unknown')}")
    print(f"TOOL DEBUG: Context current_chat_id: {getattr(ctx, 'current_chat_id', 'unknown')}")
    
    # Try to get session ID from endpoint context if missing
    try:
        if not getattr(ctx, 'user_id', None):
            from app.api.v1.endpoints.agent import TEMP_USER_ID
            ctx.user_id = TEMP_USER_ID
            print(f"Set missing user_id to {ctx.user_id}")
    except Exception as e:
        print(f"Error setting user_id: {e}")
    
    # Now call the finalize function
    result = _finalize_journal_run(ctx)
    print(f"Result: {result}")
    
    # Return a dictionary to match expected output format
    return {
        "confirmation_message": result.confirmation_message,
        "finalized_session_id": result.finalized_session_id or ""
    }

# Define tools using the standard format that worked before
StructureJournalTool = Tool(
    _structure_journal_entry_run,
    name="StructureJournalTool",
    description="Use this tool to process the user's text and structure it into the current journal entry draft based on the user's template. IMPORTANT: You must include the user's text in the 'user_text' parameter.",
    max_retries=3
)

UpdatePreferencesToolInstance = Tool(
    _update_preferences_run,
    name="UpdatePreferencesTool",
    description="Use this tool if the user's input seems to indicate a desire to update their preferences, such as their goals, known challenges, personal glossary, or overall journaling style/purpose. IMPORTANT: You must include the user's text in the 'user_text' parameter.",
    max_retries=3
)

# This tool should use the SaveJournalInput model to be more consistent
FinalizeJournalToolInstance = Tool(
    save_journal,
    name="SaveJournal",
    description="Call this tool to save and finalize the current journal entry. Use when the user says 'yes', 'save', or confirms they want to save their journal.",
    max_retries=5
)

# List of tools to be used by the agent
tools = [
    StructureJournalTool,
    UpdatePreferencesToolInstance,
    FinalizeJournalToolInstance
]
print(f"DEBUG: Final tools list: {[getattr(t, 'name', str(t)) for t in tools]}")

# For reference, expose the structured names directly
StructureJournalTool = StructureJournalTool
UpdatePreferencesToolInstance = UpdatePreferencesToolInstance
FinalizeJournalToolInstance = FinalizeJournalToolInstance 