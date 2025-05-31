# backend/app/services/anthropic_service.py
import logging
import json
from pathlib import Path
from anthropic import Anthropic, AnthropicError
from typing import List, Dict, Any

from ..core.config import settings
from ..models.user import UserTemplate, UserPreferences
from ..models.session import SessionRawInput, SessionStructuredContent
from ..repositories import load_user_template, save_user_template

logger = logging.getLogger(__name__)

# --- Prompt Loading --- 
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def load_prompt(filename: str) -> str:
    """Loads prompt text from a file in the prompts directory."""
    filepath = PROMPTS_DIR / filename
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().strip() # Read and strip leading/trailing whitespace
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {filepath}")
        return "" # Return empty string or raise error?
    except Exception as e:
        logger.error(f"Error loading prompt file {filepath}: {e}")
        return ""

# Load prompts on startup
CONVERSATION_SYSTEM_PROMPT_TEMPLATE = load_prompt("conversation_system_prompt.txt")
STRUCTURING_PROMPT_TEMPLATE = load_prompt("structuring_prompt_template.txt")
PREFERENCE_EXTRACTION_PROMPT_TEMPLATE = load_prompt("preference_extraction_prompt.txt")
# --- End Prompt Loading ---

try:
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    logger.info("Anthropic client initialized.")
except Exception as e:
    logger.error(f"Failed to initialize Anthropic client: {e}")
    client = None

# --- Structuring Prompt --- 
def construct_structuring_prompt(raw_text: str, template: UserTemplate) -> str:
    """Constructs the prompt focused *only* on structuring raw text into JSON."""
    template_sections = ", ".join([f'"{s}"' for s in template.sections])
    # Use loaded template and format it
    prompt = STRUCTURING_PROMPT_TEMPLATE.format(
        template_sections=template_sections,
        raw_text=raw_text
    )
    return prompt

# --- Conversation Prompt --- 
def construct_conversation_prompt(
    last_user_message: str, 
    conversation_history: List[Dict[str, str]],
    prefs: UserPreferences,
    latest_structured_content: SessionStructuredContent | None
) -> tuple[List[Dict[str, str]], str]: # Return tuple
    """Constructs the message list and system prompt for conversational response."""
    
    # Prepare context strings for formatting
    purpose_statement = prefs.purpose_statement or 'Not specified'
    long_term_goals_str = ", ".join(prefs.long_term_goals) if prefs.long_term_goals else 'None specified'
    known_challenges_str = ", ".join(prefs.known_challenges) if prefs.known_challenges else 'None specified'
    preferred_feedback_style = prefs.preferred_feedback_style or 'supportive' # Default to supportive
    # Provide a limited summary of the glossary to avoid making the prompt too long
    glossary_items = list(prefs.personal_glossary.items())[:5] # Limit to first 5 items
    personal_glossary_summary = ", ".join([f'{k}: {v}' for k,v in glossary_items]) if glossary_items else 'Empty'
    if len(prefs.personal_glossary) > 5:
        personal_glossary_summary += "... (truncated)"

    # Format the loaded system prompt template
    try:
        system_prompt = CONVERSATION_SYSTEM_PROMPT_TEMPLATE.format(
            purpose_statement=purpose_statement,
            long_term_goals=long_term_goals_str,
            known_challenges=known_challenges_str,
            preferred_feedback_style=preferred_feedback_style,
            personal_glossary_summary=personal_glossary_summary
        )
    except KeyError as e:
        logger.error(f"Missing key in conversation system prompt template: {e}")
        # Fallback to a very basic system prompt if formatting fails
        system_prompt = "You are a helpful assistant." 
    
    messages = []
    history_limit = 4 
    messages.extend(conversation_history[-history_limit:])
    messages.append({"role": "user", "content": last_user_message})
    
    logger.debug(f"Conversation system prompt: {system_prompt}")
    logger.debug(f"Conversation messages: {messages}")
    return messages, system_prompt

# --- Preference Extraction --- 
def construct_preference_extraction_prompt(raw_text: str) -> str:
    """Formats the preference extraction prompt."""
    try:
        return PREFERENCE_EXTRACTION_PROMPT_TEMPLATE.format(raw_text=raw_text)
    except KeyError as e:
        logger.error(f"Missing key in preference extraction prompt template: {e}")
        return "" # Return empty or raise?

def extract_preference_updates(session_id: str, raw_text: str) -> Dict[str, Any] | None:
    """Uses Claude API to extract potential preference updates from raw text."""
    if not client:
        logger.error(f"[{session_id}] Anthropic client not initialized. Cannot extract preferences.")
        return None
    if not PREFERENCE_EXTRACTION_PROMPT_TEMPLATE: # Check if prompt loaded
        logger.error(f"[{session_id}] Preference extraction prompt template not loaded.")
        return None
        
    logger.info(f"[{session_id}] Extracting preference updates from raw text.")
    prompt = construct_preference_extraction_prompt(raw_text)
    if not prompt:
        return None # Error formatting prompt
        
    logger.debug(f"[{session_id}] Preference extraction prompt: {prompt[:500]}...")

    try:
        # Use the specified model for this focused task
        message = client.messages.create(
            # model="claude-3-7-sonnet-latest", # User-specified model
            model=settings.ANTHROPIC_DEFAULT_MODEL,
            max_tokens=4096, # Updated max_tokens to max for Sonnet 3.5
            messages=[{"role": "user", "content": prompt}],
            # No system prompt needed here
            # Temperature 0 for more deterministic JSON output
            temperature=0.0
        )
        
        logger.debug(f"[{session_id}] Preference extraction API response content: {message.content}")
        if not message.content or not isinstance(message.content, list) or len(message.content) == 0:
             raise ValueError("Received unexpected content format from Claude API for preference extraction")
        
        json_string = message.content[0].text
        # Clean potential markdown fences
        if json_string.startswith("```json"):
            json_string = json_string.strip("```json\n")
        if json_string.endswith("```"):
            json_string = json_string.strip("\n```")
            
        # Parse the JSON string (expecting a dictionary)
        updates = json.loads(json_string)
        if not isinstance(updates, dict):
            raise ValueError(f"Expected JSON object (dict), got {type(updates)}")

        logger.info(f"[{session_id}] Successfully parsed preference updates: {updates}")
        return updates # Return the dictionary of updates

    except AnthropicError as e:
        logger.error(f"[{session_id}] Anthropic API error during preference extraction: {e}")
        return None
    except json.JSONDecodeError as e:
        # Log error and response separately to avoid complex f-string parsing issues
        logger.error(f"[{session_id}] Failed to decode JSON from preference extraction response: {e}")
        logger.debug(f"[{session_id}] Raw response causing JSON error: {json_string}") # Log raw string separately
        return None
    except Exception as e:
        logger.error(f"[{session_id}] Error processing preference extraction response: {e}")
        return None

def extract_template_sections_llm(text: str) -> list[str]:
    """Helper to extract template sections using LLM (similar to CLI)."""
    prompt = (
        "Analyze the following journal text and return a JSON object with two keys: "
        "'fields' (an array of field names/sections to extract from each entry) and 'example' (an example JSON object with those fields filled from the text).\n\n"
        "Journal Text:\n---\n"
        f"{text}\n---\n\nJSON Output: "
    )
    if not client:
        logger.error("Anthropic client not initialized. Cannot extract template sections.")
        return []
    try:
        message = client.messages.create(
            # model="claude-3-7-sonnet-latest",
            model=settings.ANTHROPIC_DEFAULT_MODEL,
            max_tokens=4096, # Ensure sufficient tokens
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        json_string = message.content[0].text.strip()
        if json_string.startswith("```json"):
            json_string = json_string.strip("```json\n")
        if json_string.endswith("```"):
            json_string = json_string.strip("\n```")
        result = json.loads(json_string)
        if isinstance(result, dict) and 'fields' in result and isinstance(result['fields'], list):
            return [str(s) for s in result['fields']]
    except Exception as e:
        logger.error(f"Error extracting template sections with LLM: {e}")
    return []

def get_user_template(user_id: str = "default_user", raw_text: str = "") -> UserTemplate:
    """Loads template from file, or infers using LLM if needed."""
    try:
        if user_id:
            from app.repositories import load_user_template
            user_template = load_user_template(user_id)
            # Check if template is valid (e.g., has sections)
            if user_template and user_template.sections:
                logger.info(f"Loaded user template from file for user_id: {user_id}")
                return user_template
            else:
                logger.warning(f"User template file empty or invalid for user_id: {user_id}. Attempting LLM inference.")
        else:
            logger.warning("No user_id provided to get_user_template. Will use LLM inference.")
    except Exception as e:
        logger.error(f"Error loading user template file: {e}. Attempting LLM inference.")

    # Infer template using LLM
    inferred_sections = extract_template_sections_llm(raw_text)
    if inferred_sections:
        # Create sections dictionary with SectionDetailDef objects
        from app.models.user import SectionDetailDef
        sections_dict = {
            section: SectionDetailDef(description=f"Content for {section}") 
            for section in inferred_sections
        }
        
        user_template = UserTemplate(sections=sections_dict)
        logger.info(f"Inferred template sections via LLM: {list(sections_dict.keys())}")
        
        # Save the inferred template for next time if user_id is provided
        if user_id:
            from app.repositories import save_user_template
            save_success = save_user_template(user_id, user_template)
            if save_success:
                logger.info(f"Saved inferred template to file for user_id: {user_id}")
            else:
                logger.error(f"Failed to save inferred template to file for user_id: {user_id}")
                
        return user_template
    else:
        logger.error("Failed to infer template using LLM. Using default template.")
        # Fallback to a default template if LLM fails
        from app.models.user import SectionDetailDef
        return UserTemplate(sections={
            "Events": SectionDetailDef(description="Key events from your day"),
            "Thoughts": SectionDetailDef(description="Reflections and ideas"),
            "Feelings": SectionDetailDef(description="Emotional state")
        }) # Return default with proper dictionary format

# --- Service Functions (structure_raw_input and generate_conversational_response) ---

def structure_raw_input(session_id: str, raw_text: str, user_id: str = None) -> SessionStructuredContent | None:
    """Uses Claude API to structure raw text based on user template."""
    if not client:
        logger.error("Anthropic client is not initialized. Cannot structure input.")
        return None

    # Use provided user_id or fall back to default if not provided
    user_id = user_id or "default_user"
    
    logger.info(f"Structuring raw input for session {session_id}, user_id: {user_id}")
    # Get template, inferring if necessary
    user_template = get_user_template(user_id, raw_text)
    if not user_template.sections:
        logger.error(f"Cannot structure input for {session_id}: No template sections available.")
        return None

    prompt = construct_structuring_prompt(raw_text, user_template)
    logger.debug(f"Structuring prompt for session {session_id}:\n{prompt[:500]}...")

    try:
        message = client.messages.create(
            # model="claude-3-7-sonnet-latest",
            model=settings.ANTHROPIC_DEFAULT_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
            # No system prompt used for structuring
        )
        
        # Log the raw response before any processing
        logger.debug(f"[{session_id}] Raw Anthropic API response content for structuring: {message.content}")

        if not message.content or not isinstance(message.content, list) or len(message.content) == 0:
            logger.error(f"[{session_id}] Received unexpected empty or invalid content array from Anthropic API for structuring")
            return None 
        
        json_string = message.content[0].text.strip()
        
        logger.debug(f"[{session_id}] JSON string to parse for structuring: '{json_string}'")

        # Handle empty string from LLM before attempting to parse
        if not json_string:
            logger.warning(f"[{session_id}] Anthropic API returned an empty string for structuring. Returning empty structured content.")
            return SessionStructuredContent(session_id=session_id, data={}) # Return empty data

        # Clean potential markdown fences (important!)
        if json_string.startswith("```json"):
            json_string = json_string.strip("```json\n")
        if json_string.endswith("```"):
            json_string = json_string.strip("\n```")
        
        logger.debug(f"[{session_id}] Cleaned JSON string for structuring: '{json_string}'")
            
        data = json.loads(json_string) 
        
        if not isinstance(data, dict):
            logger.error(f"[{session_id}] Expected JSON object (dict) for structured data, got {type(data)}")
            return None

        logger.info(f"[{session_id}] Successfully parsed structured data: {list(data.keys())}")
        
        return SessionStructuredContent(session_id=session_id, data=data)

    except AnthropicError as e:
        logger.error(f"[{session_id}] Anthropic API error during structuring: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"[{session_id}] Failed to decode JSON from structuring response: {e}")
        # Log the problematic string that caused the error - THIS IS THE KEY ADDITION
        logger.debug(f"[{session_id}] Raw JSON string causing structuring decode error: '{json_string}'") 
        return None
    except Exception as e:
        logger.error(f"Error processing structuring response or validating data for session {session_id}: {e}")
        return None

def generate_conversational_response(
    session_id: str, 
    last_user_message: str, 
    conversation_history: List[Dict[str, str]], 
    prefs: UserPreferences,
    latest_structured_content: SessionStructuredContent | None
) -> str | None:
    """Uses Claude API to generate a conversational response."""
    if not client:
        logger.error("Anthropic client is not initialized. Cannot generate response.")
        return None

    logger.info(f"Generating conversational response for session {session_id}")
    messages, system_prompt = construct_conversation_prompt(
        last_user_message, conversation_history, prefs, latest_structured_content
    )
    
    try:
        message = client.messages.create(
            # model="claude-3-7-sonnet-latest", # User-specified model
            model=settings.ANTHROPIC_DEFAULT_MODEL,
            max_tokens=4096, # Updated max_tokens to max for Sonnet 3.5
            system=system_prompt, 
            messages=messages,
            temperature=0.7
        )
        
        logger.debug(f"Conversation API response content for session {session_id}: {message.content}")
        if not message.content or not isinstance(message.content, list) or len(message.content) == 0:
             raise ValueError("Received unexpected content format from Claude API for conversation")
        
        chat_response = message.content[0].text
        logger.info(f"Successfully generated chat response for session {session_id}")
        return chat_response

    except AnthropicError as e:
        logger.error(f"Anthropic API error during conversation generation for session {session_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing conversation response for session {session_id}: {e}")
        return None 