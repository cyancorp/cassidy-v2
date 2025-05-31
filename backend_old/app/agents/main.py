# Main agent logic will reside here.

import logging
import os
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pathlib import Path
from typing import Optional

from app.agents.models import CassidyAgentDependencies, JournalDraft
from app.agents.tools import tools as actual_app_tools
from app.models.user import UserPreferences, UserTemplate, SectionDetailDef


# Re-introduce settings import
from app.core.config import settings

# .env loading
dotenv_path = os.path.join(os.path.dirname(__file__), '../../.env')
load_dotenv(dotenv_path=dotenv_path)

logger = logging.getLogger(__name__)

# Load system prompt
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def load_prompt(filename: str) -> str:
    """Loads prompt text from a file in the prompts directory."""
    filepath = PROMPTS_DIR / filename
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().strip()  # Read and strip leading/trailing whitespace
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {filepath}")
        return ""  # Return empty string or raise error?
    except Exception as e:
        logger.error(f"Error loading prompt file {filepath}: {e}")
        return ""

# Load the system prompt at module level
SYSTEM_PROMPT_TEMPLATE = load_prompt("conversation_system_prompt.txt")

# Global agent instance
cassidy_agent = None

def get_dynamic_instructions(ctx: CassidyAgentDependencies) -> str:
    """
    Generate dynamic instructions for the agent based on the current state.
    This will be called via the @agent.instruction decorator.
    """
    # Get the current chat type and user's template
    chat_type = ctx.chat_type
    user_template = ctx.user_template
    current_draft = ctx.current_journal_draft
    
    # Build different instructions based on chat type
    if chat_type == "journaling":
        # For journaling, instructions help guide the user to fill their template
        sections = list(user_template.sections.keys()) if user_template and user_template.sections else []
        
        # Check which sections in the template are filled/unfilled
        filled_sections = []
        unfilled_sections = []
        
        if current_draft and current_draft.data:
            # Check for proper structuring - if data contains only 'content' or 'raw', it's not properly structured
            if len(current_draft.data) == 1 and ('content' in current_draft.data or 'raw' in current_draft.data):
                # Data is not properly structured - consider all sections unfilled
                unfilled_sections = sections.copy()
                structured_note = (
                    "The current journal entry is not properly structured according to the template. "
                    "You should use the StructureJournalTool with the user's text to organize it into template sections."
                )
            else:
                # Check each template section
                for section in sections:
                    if section in current_draft.data and current_draft.data[section]:
                        filled_sections.append(section)
                    else:
                        unfilled_sections.append(section)
                structured_note = ""
        else:
            # No draft data yet
            unfilled_sections = sections.copy()
            structured_note = ""
                
        # Build template status message
        if not sections:
            template_status = (
                "The user doesn't have a journal template defined yet. "
                "Encourage them to share what kind of content they'd like to track in their journal entries."
            )
        elif not unfilled_sections:
            template_status = (
                f"The user has filled all sections of their journal template: {', '.join(sections)}. "
                "Ask if they're ready to finalize their journal entry, or if they want to add more to any section."
            )
        else:
            template_status = (
                f"The user has filled sections: {', '.join(filled_sections) if filled_sections else 'None yet'}. "
                f"Still needs to fill: {', '.join(unfilled_sections)}. "
                "Actively prompt the user to provide content for each unfilled section. Ask specifically about each unfilled section."
            )
            
        # Additional guidance for the agent
        if ctx.current_journal_draft.data:
            finalization_guidance = (
                "When the user indicates they're done with their journal entry, "
                "call the FinalizeJournalEntryTool to save it. Before finalizing, ensure all template sections "
                "have been addressed with the user, even if some remain empty."
            )
        else:
            finalization_guidance = (
                "The user hasn't provided any journal content yet. "
                "When they share thoughts, use the StructureJournalTool to organize their input according to the template sections."
            )
            
        # Tool usage guidance
        tool_guidance = """
IMPORTANT TOOL USAGE INSTRUCTIONS:
- When using the StructureJournalTool, you MUST provide the 'user_text' parameter with the user's message
  Example: StructureJournalTool(user_text="User's message here")
- When using the UpdatePreferencesTool, you MUST provide the 'user_text' parameter with the user's message
  Example: UpdatePreferencesTool(user_text="User's message here")
- The FinalizeJournalEntryTool does not require parameters
  Example: FinalizeJournalToolInstance()
- When the user responds with "yes", "save", "finalize", or any clear confirmation to save their journal, 
  you MUST IMMEDIATELY call: FinalizeJournalToolInstance()
- Do not ask follow-up questions or make further clarifications if the user has confirmed they want to finalize
"""
            
        # Journal-specific instructions
        return f"""
You are assisting with journaling. Help the user record and reflect on their experiences.

{template_status}

{structured_note}

If the user shares new information that seems relevant to their preferences (like goals, challenges, 
or terms for their personal glossary), use the UpdatePreferencesTool to update their profile.

When the user provides journal content, use the StructureJournalTool to organize it into the appropriate template sections.

For each section in the template, actively encourage the user to add content if it's missing.

{finalization_guidance}

{tool_guidance}

IMPORTANT: Do not finalize a journal entry without first trying to organize it according to the template sections.
        """
    else:
        # Default conversation mode
        return """
You are engaged in a general conversation. 

If the user wants to start journaling, suggest they begin sharing their thoughts for the day.
        """

async def create_cassidy_agent(user_preferences: Optional[UserPreferences] = None):
    """Create a Cassidy agent instance with proper configuration."""
    logger.info("[PER-REQUEST] Starting agent creation.")
    
    # For troubleshooting, print out user preferences
    if user_preferences:
        logger.info(f"[PER-REQUEST] User preferences provided: purpose={user_preferences.purpose_statement}, goals={user_preferences.long_term_goals}")
    else:
        logger.warning("[PER-REQUEST] No user preferences provided to create_cassidy_agent")

    # 1. Get API Key and Model Name from Pydantic settings (no change)
    try:
        api_key = str(settings.ANTHROPIC_API_KEY)
        model_name = str(settings.ANTHROPIC_DEFAULT_MODEL)
        if not api_key:
            logger.error("[PER-REQUEST] ERROR: ANTHROPIC_API_KEY from settings is empty.")
            return None
        if not model_name:
            logger.error("[PER-REQUEST] ERROR: ANTHROPIC_DEFAULT_MODEL from settings is empty.")
            return None
        logger.info(f"[PER-REQUEST] Model: {model_name}, Key (first 5): {api_key[:5]}...")
    except Exception as e_settings:
        logger.error(f"[PER-REQUEST] ERROR: Failed to access API key/model from settings: {e_settings}", exc_info=True)
        return None

    # 2. Initialize AnthropicProvider and AnthropicModel (no change)
    local_llm_instance = None
    try:
        provider = AnthropicProvider(api_key=api_key)
        local_llm_instance = AnthropicModel(model_name, provider=provider)
        logger.info(f"[PER-REQUEST] AnthropicModel initialized: {local_llm_instance}")
    except Exception as e:
        logger.error(f"[PER-REQUEST] ERROR: AnthropicModel init failed: {e}", exc_info=True)
        return None

    # 3. Initialize Agent with llm, debug flag, and logger
    local_agent_instance = None
    try:
        agent_debug_flag = getattr(settings, 'DEBUG', False)
        logger.info(f"[PER-REQUEST] Agent debug flag: {agent_debug_flag}")
        
        # Log tool information
        logger.info(f"[PER-REQUEST] Tools provided: {len(actual_app_tools)} tools")
        for i, tool in enumerate(actual_app_tools):
            logger.info(f"[PER-REQUEST] Tool {i+1}: {getattr(tool, 'name', tool.__name__ if hasattr(tool, '__name__') else 'unnamed')} - {getattr(tool, 'description', 'no description')[:50]}...")
        
        # Format the system prompt with user preferences if available
        if user_preferences:
            # Use actual user preferences
            purpose_statement = user_preferences.purpose_statement or 'General journaling assistance'
            long_term_goals_str = ", ".join(user_preferences.long_term_goals) if user_preferences.long_term_goals else 'None specified'
            known_challenges_str = ", ".join(user_preferences.known_challenges) if user_preferences.known_challenges else 'None specified'
            preferred_feedback_style = user_preferences.preferred_feedback_style or 'supportive'
            
            # Provide a limited summary of the glossary to avoid making the prompt too long
            glossary_items = list(user_preferences.personal_glossary.items())[:5]  # Limit to first 5 items
            personal_glossary_summary = ", ".join([f'{k}: {v}' for k, v in glossary_items]) if glossary_items else 'Empty'
            if len(user_preferences.personal_glossary) > 5:
                personal_glossary_summary += "... (truncated)"
                
            logger.info(f"[PER-REQUEST] Formatting system prompt with user preferences for: {purpose_statement}")
        else:
            # Use default values as fallback
            purpose_statement = "General journaling assistance"
            long_term_goals_str = "Not specified yet"
            known_challenges_str = "Not specified yet"
            preferred_feedback_style = "supportive"
            personal_glossary_summary = "Not specified yet"
            logger.info("[PER-REQUEST] Using default values for system prompt (no user preferences provided)")
        
        # Format the prompt template
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            purpose_statement=purpose_statement,
            long_term_goals=long_term_goals_str,
            known_challenges=known_challenges_str,
            preferred_feedback_style=preferred_feedback_style,
            personal_glossary_summary=personal_glossary_summary
        )
        
        # Add explicit tool instructions to the system prompt
        tool_instructions = """
CRITICAL TOOL INSTRUCTIONS:
1. When a user says "yes", "save", "finalize", or any word confirming they want to save, you MUST use the SaveJournal tool with JSON format like this:
   <tool_use>
   {"name": "SaveJournal", "input": {}}
   </tool_use>

2. DO NOT RESPOND WITH TEXT ONLY - YOU MUST USE THE TOOL!

3. When the user is adding journal content, use:
   <tool_use>
   {"name": "StructureJournalTool", "input": {"user_text": "User's message here"}}
   </tool_use>

4. For preference updates, use:
   <tool_use>
   {"name": "UpdatePreferencesTool", "input": {"user_text": "User's message here"}}
   </tool_use>

EXACT EXAMPLES TO FOLLOW:
User: "Yes"
YOU MUST RESPOND WITH:
<tool_use>
{"name": "SaveJournal", "input": {}}
</tool_use>

User: "save it"
YOU MUST RESPOND WITH:
<tool_use>
{"name": "SaveJournal", "input": {}}
</tool_use>

User: "ok save"
YOU MUST RESPOND WITH:
<tool_use>
{"name": "SaveJournal", "input": {}}
</tool_use>
"""
        
        system_prompt += "\n\n" + tool_instructions
        
        logger.info(f"[PER-REQUEST] Using system_prompt (first 50 chars): {system_prompt[:50]}...")
        
        # Create the agent instance - needs to be 'tools' plural per pydantic-ai docs
        local_agent_instance = Agent(
            local_llm_instance, 
            debug=agent_debug_flag, 
            logger=logger, 
            tools=actual_app_tools,  # IMPORTANT: Use tools= (plural)
            system_prompt=system_prompt,
            instruction_max_retries=5
        )
        
        # Simple debug check
        logger.info(f"DEBUG: Agent created with {len(actual_app_tools)} tools")
        
        # Add dynamic instructions directly as a string rather than as a function
        # The Agent class doesn't have an 'instruction' method, but we can add to instructions attribute
        # local_agent_instance.instruction(get_dynamic_instructions)
        # Create fake template if needed
        default_template = UserTemplate(
            sections={
                "Events": SectionDetailDef(description="Key events from your day"),
                "Thoughts": SectionDetailDef(description="Reflections and ideas")
            }
        )
        
        # Create deps with default values
        template_to_use = None
        if 'user_template' in locals() and user_template:
            template_to_use = user_template
        else:
            template_to_use = default_template
            
        dynamic_instructions = get_dynamic_instructions(CassidyAgentDependencies(
            user_id="example_user",
            current_chat_id="example_chat",
            chat_type="journaling",
            user_template=template_to_use,
            user_preferences=user_preferences or UserPreferences(),
            current_journal_draft=JournalDraft()
        ))
        if hasattr(local_agent_instance, 'instructions'):
            local_agent_instance.instructions = dynamic_instructions
        
        logger.info("[PER-REQUEST] Agent initialized with dynamic instructions.")
        
        if local_agent_instance.model:
            logger.info("[PER-REQUEST] Agent.model IS SET.")
            logger.info(f"  Type: {type(local_agent_instance.model).__name__}, Value: {local_agent_instance.model}")
            return local_agent_instance
        else:
            logger.error("[PER-REQUEST] ERROR: Agent.model is NOT SET after initialization.")
            return None
    except Exception as e:
        logger.error(f"[PER-REQUEST] ERROR: Agent initialization failed: {e}", exc_info=True)
        return None

# Ensure other application-specific imports/functions are commented out:
# from app.agents.models import CassidyAgentDependencies, JournalDraft
# from app.agents.tools import tools as actual_app_tools
# from pathlib import Path
# from jinja2 import Environment, FileSystemLoader, select_autoescape
# import sys