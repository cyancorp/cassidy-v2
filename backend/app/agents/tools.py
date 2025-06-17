from pydantic_ai import Tool
from typing import Dict, Any, List
import re

from app.agents.models import (
    CassidyAgentDependencies,
    StructureJournalRequest, StructureJournalResponse,
    SaveJournalRequest, SaveJournalResponse,
    UpdatePreferencesRequest, UpdatePreferencesResponse
)
from app.templates.loader import template_loader


async def structure_journal_tool(
    ctx: CassidyAgentDependencies,
    user_text: str
) -> StructureJournalResponse:
    """
    Tool to structure user input into journal template sections using LLM analysis.
    
    This tool uses an LLM to intelligently analyze the user's text and map it to 
    appropriate sections in their personal journal template.
    """
    print(f"StructureJournalTool called with text: {user_text}")
    print(f"Context user_id: {ctx.user_id}")
    print(f"Context session_id: {ctx.session_id}")
    print(f"Context template keys: {list(ctx.user_template.keys())}")
    print(f"Context draft keys: {list(ctx.current_journal_draft.keys())}")
    
    user_text = user_text.strip()
    if not user_text:
        return StructureJournalResponse(sections_updated=[], status="no_content")
    
    # Get template sections from context (should come from file-based template now)
    template_sections = ctx.user_template.get("sections", {})
    if not template_sections:
        # Fallback to file-based template if context doesn't have sections
        fallback_template = template_loader.get_user_template()
        template_sections = fallback_template.get("sections", {})
    
    # Format template sections for LLM prompt with dynamic guidelines
    sections_list = []
    section_guidelines = []
    
    for section_name, section_def in template_sections.items():
        description = section_def.get("description", "")
        aliases = section_def.get("aliases", [])
        aliases_str = f" (also known as: {', '.join(aliases)})" if aliases else ""
        sections_list.append(f"- {section_name}: {description}{aliases_str}")
        
        # Create dynamic guideline based on section name and description
        if aliases:
            alias_examples = f" (keywords: {', '.join(aliases[:3])})"  # Show first 3 aliases as keywords
        else:
            alias_examples = ""
        section_guidelines.append(f'- "{section_name}": {description}{alias_examples}')
    
    # Create LLM prompt for content analysis
    analysis_prompt = f"""Analyze the following raw user input and structure it into a JSON object that maps content to the most appropriate template sections.

CRITICAL INSTRUCTIONS:
1. Read each template section description carefully
2. Map content to the MOST SPECIFIC section that fits
3. Use arrays for multiple items, strings for single content
4. Only include sections that have relevant content
5. Be selective with general categories - prefer specific sections when applicable

DYNAMIC SECTION MAPPING (based on user's template):
{chr(10).join(section_guidelines)}

Template Sections Available:
{chr(10).join(sections_list)}

EXAMPLES (adapt to your template sections):
Input: "I finished the report and need to buy groceries. Meeting tomorrow at 2pm. Feeling accomplished."
Output: Use the most specific sections available for: completed work, future tasks, scheduled events, and emotions.

Input: "Made some trades today and feeling optimistic about the market direction."
Output: Use sections that best match: trading actions, market sentiment, and personal feelings.

Input: "My goal is to go to the moon"
Output: {{"long_term_goals": ["go to the moon"]}}

Input: "I want to travel to space"
Output: {{"long_term_goals": ["travel to space"]}}

Raw User Input:
---
{user_text}
---

JSON Output (focus on capturing emotions, distinguishing completed vs future tasks):"""

    # Use LLM to analyze and structure content
    import json
    import os
    
    try:
        # Set up LLM for content analysis using existing imports
        from pydantic_ai import Agent
        from pydantic_ai.models.anthropic import AnthropicModel
        from app.core.config import settings, get_anthropic_api_key
        
        # Set API key from settings
        api_key = get_anthropic_api_key()
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        model = AnthropicModel(settings.ANTHROPIC_STRUCTURING_MODEL)
        
        # Create a simple agent for content structuring
        analysis_agent = Agent(model=model)
        
        # Run the analysis
        result = await analysis_agent.run(analysis_prompt)
        analysis_output = result.output.strip()
        
        
        # Extract JSON from the response
        if analysis_output.startswith("```json"):
            analysis_output = analysis_output[7:]
        if analysis_output.endswith("```"):
            analysis_output = analysis_output[:-3]
        analysis_output = analysis_output.strip()
        
        # Parse the structured content
        try:
            structured_content = json.loads(analysis_output)
        except json.JSONDecodeError:
            # Fallback to general reflection if JSON parsing fails
            structured_content = {"General Reflection": user_text}
        
    except Exception:
        # Fallback to general reflection if LLM call fails
        structured_content = {"General Reflection": user_text}
    
    # Get current draft data and merge with new content
    current_draft = ctx.current_journal_draft.copy()
    sections_updated = []
    
    # Normalize section names to match template (handle case variations)
    def normalize_section_name(name: str, template_sections: dict) -> str:
        """Normalize section name to match template format"""
        # Direct match
        if name in template_sections:
            return name
            
        # Case-insensitive match
        for template_name in template_sections:
            if name.lower() == template_name.lower():
                return template_name
                
        # Check aliases
        for template_name, section_def in template_sections.items():
            if name.lower() in [alias.lower() for alias in section_def.aliases]:
                return template_name
                
        # Convert snake_case to proper case
        if "_" in name:
            words = name.split("_")
            proper_case = " ".join(word.capitalize() for word in words)
            for template_name in template_sections:
                if proper_case == template_name:
                    return template_name
        
        return name  # Return original if no match found
    
    # Merge structured content with existing draft
    for section_name, new_content in structured_content.items():
        # Normalize section name to match template
        normalized_name = normalize_section_name(section_name, template_sections)
        
        # Validate section exists in template, or allow "General Reflection" as default fallback
        if normalized_name in template_sections or (not template_sections and normalized_name == "General Reflection"):
            if normalized_name in current_draft:
                # Merge with existing content
                existing_content = current_draft[normalized_name]
                
                if isinstance(new_content, list) and isinstance(existing_content, list):
                    # Both are lists - extend
                    current_draft[normalized_name] = existing_content + new_content
                elif isinstance(new_content, list) and isinstance(existing_content, str):
                    # New is list, existing is string - convert existing to list and extend
                    current_draft[normalized_name] = [existing_content] + new_content
                elif isinstance(new_content, str) and isinstance(existing_content, list):
                    # New is string, existing is list - append string
                    current_draft[normalized_name] = existing_content + [new_content]
                else:
                    # Both are strings - concatenate
                    current_draft[normalized_name] = existing_content + "\n\n" + new_content
            else:
                # New section
                current_draft[normalized_name] = new_content
            
            sections_updated.append(normalized_name)
    
    # Update the context (this will be handled by the agent service)
    ctx.current_journal_draft = current_draft
    
    return StructureJournalResponse(
        sections_updated=sections_updated,
        updated_draft_data=current_draft,
        status="success"
    )


async def save_journal_tool(
    ctx: CassidyAgentDependencies,
    confirmation: bool = True
) -> SaveJournalResponse:
    """
    Tool to save/finalize the current journal draft into a permanent journal entry.
    
    This tool should only be called when the user explicitly requests to save their journal.
    """
    
    if not confirmation:
        return SaveJournalResponse(journal_entry_id="", status="cancelled")
    
    # Note: We'll check the actual draft content in the agent service
    # since the context might not have the latest data from the database
    # For now, we'll assume there is content to save and let the service handle validation
    
    # The actual saving will be handled by the agent service
    # Don't generate ID here - let the database handle it
    # Return success - the agent service will check if there's actually content to save
    return SaveJournalResponse(
        journal_entry_id="pending",  # Will be set after database save
        status="success"
    )


async def update_preferences_tool(
    ctx: CassidyAgentDependencies,
    preference_updates: Dict[str, Any]
) -> UpdatePreferencesResponse:
    """
    Tool to intelligently update user preferences and template settings from natural language.
    
    Uses LLM analysis to extract preference changes from conversational context,
    making preference updates feel natural and fluid.
    """
    # WORKAROUND: Get user_id from request if context is wrong
    request_user_id = preference_updates.get("user_id", "")
    actual_user_id = request_user_id if request_user_id and request_user_id != "{{user_id}}" else ctx.user_id
    
    # Extract the user text that might contain preference updates  
    # The agent should pass the user's conversational text in preference_updates["user_text"]
    user_text = preference_updates.get("user_text", "")
    
    # If no user_text provided, try to extract from other string values
    if not user_text.strip():
        text_values = [str(v) for v in preference_updates.values() if isinstance(v, str) and v.strip()]
        user_text = " ".join(text_values)
    
    if not user_text.strip():
        # Fallback to old behavior for direct API calls
        return await _legacy_update_preferences(ctx, preference_updates)
    
    # Get current preferences for context
    current_prefs = ctx.user_preferences.copy()
    
    # Create LLM prompt for preference analysis
    preferences_prompt = f"""Analyze the following user input to identify any preference updates or changes they want to make to their journaling system.

USER PREFERENCES THAT CAN BE UPDATED:
- purpose_statement: Why they use this journaling tool (string or null)
- long_term_goals: List of goals they're working toward (array of strings)
- known_challenges: Areas they struggle with or want to improve (array of strings)  
- preferred_feedback_style: How they want feedback ("supportive", "detailed", "brief", "challenging")
- personal_glossary: Custom terms/definitions they use (object with key-value pairs)

TEMPLATE ACTIONS:
- template_info: User wants to see template information
- template_sections: User wants to see available sections
- template_reload: User wants to reload template from file
- template_request: User wants to request template changes

CURRENT USER PREFERENCES:
- Purpose: {current_prefs.get('purpose_statement', 'None set')}
- Goals: {current_prefs.get('long_term_goals', [])}
- Challenges: {current_prefs.get('known_challenges', [])}
- Feedback Style: {current_prefs.get('preferred_feedback_style', 'supportive')}
- Glossary: {len(current_prefs.get('personal_glossary', {}))} terms defined

INSTRUCTIONS:
1. Identify if the user is expressing any preference changes or updates
2. Extract the specific changes they want to make
3. For lists (goals, challenges), determine if they want to ADD, REPLACE, or REMOVE items
4. Return JSON with only the fields that should be updated
5. If no preference updates are detected, return an empty object

EXAMPLES:
Input: "My goal is to become a better trader and improve my risk management"
Output: {{"long_term_goals": ["become a better trader", "improve risk management"]}}

Input: "I want to go to the moon"
Output: {{"long_term_goals": ["go to the moon"]}}

Input: "I want to travel to space"
Output: {{"long_term_goals": ["travel to space"]}}

Input: "I prefer detailed feedback when you respond to me"
Output: {{"preferred_feedback_style": "detailed"}}

Input: "I struggle with emotional trading decisions"
Output: {{"known_challenges": ["emotional trading decisions"]}}

Input: "Can you show me my template sections?"
Output: {{"template_sections": true}}

Input: "The purpose of my journaling is to track my trading psychology and personal growth"
Output: {{"purpose_statement": "to track my trading psychology and personal growth"}}

User Input:
---
{user_text}
---

JSON Output (only include fields that should be updated):"""

    try:
        # Set up LLM for preference analysis
        import json
        import os
        from pydantic_ai import Agent
        from pydantic_ai.models.anthropic import AnthropicModel
        from app.core.config import settings, get_anthropic_api_key
        
        # Set API key from settings
        api_key = get_anthropic_api_key()
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        model = AnthropicModel(settings.ANTHROPIC_STRUCTURING_MODEL)
        
        # Create agent for preference analysis
        preferences_agent = Agent(model=model)
        
        # Run the analysis
        result = await preferences_agent.run(preferences_prompt)
        analysis_output = result.output.strip()
        
        # Extract JSON from the response
        if analysis_output.startswith("```json"):
            analysis_output = analysis_output[7:]
        if analysis_output.endswith("```"):
            analysis_output = analysis_output[:-3]
        analysis_output = analysis_output.strip()
        
        # Parse the preference updates
        try:
            preference_updates = json.loads(analysis_output)
        except json.JSONDecodeError:
            preference_updates = {}
        
    except Exception:
        preference_updates = {}
    
    # Apply the extracted preference updates
    updated_fields = []
    
    for field, value in preference_updates.items():
        if field == "purpose_statement":
            current_prefs[field] = value
            updated_fields.append(field)
            
        elif field == "preferred_feedback_style" and value in ["supportive", "detailed", "brief", "challenging"]:
            current_prefs[field] = value
            updated_fields.append(field)
            
        elif field in ["long_term_goals", "known_challenges"]:
            if isinstance(value, list):
                # For now, replace the entire list (could be enhanced to support add/remove)
                current_prefs[field] = value
                updated_fields.append(field)
            elif isinstance(value, str):
                # Add single item to list
                if field not in current_prefs:
                    current_prefs[field] = []
                if value not in current_prefs[field]:
                    current_prefs[field].append(value)
                    updated_fields.append(field)
                    
        elif field == "personal_glossary" and isinstance(value, dict):
            if "personal_glossary" not in current_prefs:
                current_prefs["personal_glossary"] = {}
            current_prefs["personal_glossary"].update(value)
            updated_fields.append(field)
            
        # Handle template requests
        elif field == "template_info":
            template = template_loader.get_user_template()
            updated_fields.append("template_info_provided")
            
        elif field == "template_sections":
            sections = template_loader.get_template_sections()
            updated_fields.append("template_sections_listed")
            
        elif field == "template_reload":
            template_loader.reload_template()
            updated_fields.append("template_reloaded")
            
        elif field == "template_request":
            updated_fields.append("template_change_requested")
    
    # Update context
    ctx.user_preferences = current_prefs
    
    # Save preferences to database immediately to ensure persistence
    if updated_fields:
        try:
            # Import here to avoid circular imports
            from app.repositories.user import UserPreferencesRepository
            from app.database import async_session_maker
            
            # Save preferences immediately using direct session
            async with async_session_maker() as db:
                prefs_repo = UserPreferencesRepository()
                await prefs_repo.update_by_user_id(db, actual_user_id, **current_prefs)
        except Exception as e:
            print(f"Failed to save preferences to database: {e}")
    
    return UpdatePreferencesResponse(
        updated_fields=updated_fields,
        status="success"
    )


async def _legacy_update_preferences(ctx: CassidyAgentDependencies, preference_updates: Dict[str, Any]) -> UpdatePreferencesResponse:
    """Legacy direct preference updates for API calls"""
    updated_fields = []
    current_prefs = ctx.user_preferences.copy()
    
    for field, value in preference_updates.items():
        if field in ["purpose_statement", "preferred_feedback_style", "personal_glossary"]:
            current_prefs[field] = value
            updated_fields.append(field)
        elif field in ["long_term_goals", "known_challenges"]:
            if isinstance(value, list):
                current_prefs[field] = value
                updated_fields.append(field)
            elif isinstance(value, str):
                if field not in current_prefs:
                    current_prefs[field] = []
                if value not in current_prefs[field]:
                    current_prefs[field].append(value)
                    updated_fields.append(field)
    
    ctx.user_preferences = current_prefs
    
    # Save to database immediately (same fix as main function)
    if updated_fields:
        try:
            from app.repositories.user import UserPreferencesRepository
            from app.database import async_session_maker
            
            async with async_session_maker() as db:
                prefs_repo = UserPreferencesRepository()
                await prefs_repo.update_by_user_id(db, ctx.user_id, **current_prefs)
        except Exception as e:
            print(f"Failed to save legacy preferences to database: {e}")
    
    return UpdatePreferencesResponse(updated_fields=updated_fields, status="success")


# Tool definitions for Pydantic-AI
StructureJournalTool = Tool(
    structure_journal_tool,
    description="Structure user input into appropriate journal template sections based on content analysis"
)

SaveJournalTool = Tool(
    save_journal_tool,
    description="Save and finalize the current journal draft when user asks to save, finalize, or complete their journal entry"
)

UpdatePreferencesTool = Tool(
    update_preferences_tool,
    description="Intelligently update user preferences from natural conversation. Call this when user mentions goals, challenges, feedback preferences, or purpose. Extracts preference changes from user text automatically using LLM analysis."
)


def get_tools_for_conversation_type(conversation_type: str) -> List[Tool]:
    """Return appropriate tools for the given conversation type"""
    if conversation_type == "journaling":
        return [StructureJournalTool, SaveJournalTool, UpdatePreferencesTool]
    elif conversation_type == "general":
        return []
    else:
        return []