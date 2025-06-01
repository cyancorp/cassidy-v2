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
    request: StructureJournalRequest
) -> StructureJournalResponse:
    """
    Tool to structure user input into journal template sections using LLM analysis.
    
    This tool uses an LLM to intelligently analyze the user's text and map it to 
    appropriate sections in their personal journal template.
    """
    print(f"StructureJournalTool called with text: {request.user_text}")
    user_text = request.user_text.strip()
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
        from app.core.config import settings
        
        # Set API key from settings
        os.environ["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY
        model = AnthropicModel("claude-sonnet-4-20250514")  # Use latest Sonnet 4 model for best content analysis
        
        # Create a simple agent for content structuring
        analysis_agent = Agent(model=model)
        
        # Run the analysis
        result = await analysis_agent.run(analysis_prompt)
        analysis_output = result.output.strip()
        
        print(f"LLM analysis output: {analysis_output}")
        
        # Extract JSON from the response
        if analysis_output.startswith("```json"):
            analysis_output = analysis_output[7:]
        if analysis_output.endswith("```"):
            analysis_output = analysis_output[:-3]
        analysis_output = analysis_output.strip()
        
        # Parse the structured content
        try:
            structured_content = json.loads(analysis_output)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}, falling back to general reflection")
            # Fallback to general reflection if JSON parsing fails
            structured_content = {"General Reflection": user_text}
        
    except Exception as e:
        print(f"LLM analysis failed: {e}, falling back to general reflection")
        # Fallback to general reflection if LLM call fails
        structured_content = {"General Reflection": user_text}
    
    # Get current draft data and merge with new content
    current_draft = ctx.current_journal_draft.copy()
    sections_updated = []
    
    # Merge structured content with existing draft
    for section_name, new_content in structured_content.items():
        if section_name in template_sections:  # Validate section exists in template
            if section_name in current_draft:
                # Merge with existing content
                existing_content = current_draft[section_name]
                
                if isinstance(new_content, list) and isinstance(existing_content, list):
                    # Both are lists - extend
                    current_draft[section_name] = existing_content + new_content
                elif isinstance(new_content, list) and isinstance(existing_content, str):
                    # New is list, existing is string - convert existing to list and extend
                    current_draft[section_name] = [existing_content] + new_content
                elif isinstance(new_content, str) and isinstance(existing_content, list):
                    # New is string, existing is list - append string
                    current_draft[section_name] = existing_content + [new_content]
                else:
                    # Both are strings - concatenate
                    current_draft[section_name] = existing_content + "\n\n" + new_content
            else:
                # New section
                current_draft[section_name] = new_content
            
            sections_updated.append(section_name)
    
    # Update the context (this will be handled by the agent service)
    ctx.current_journal_draft = current_draft
    
    return StructureJournalResponse(
        sections_updated=sections_updated,
        updated_draft_data=current_draft,
        status="success"
    )


async def save_journal_tool(
    ctx: CassidyAgentDependencies,
    request: SaveJournalRequest
) -> SaveJournalResponse:
    """
    Tool to save/finalize the current journal draft into a permanent journal entry.
    
    This tool should only be called when the user explicitly requests to save their journal.
    """
    print(f"SaveJournalTool called with confirmation: {request.confirmation}")
    print(f"Current draft data from context: {ctx.current_journal_draft}")
    
    if not request.confirmation:
        return SaveJournalResponse(journal_entry_id="", status="cancelled")
    
    # Note: We'll check the actual draft content in the agent service
    # since the context might not have the latest data from the database
    # For now, we'll assume there is content to save and let the service handle validation
    
    # Generate a journal entry ID
    import uuid
    journal_entry_id = str(uuid.uuid4())
    
    # The actual saving will be handled by the agent service
    # Return success - the agent service will check if there's actually content to save
    return SaveJournalResponse(
        journal_entry_id=journal_entry_id,
        status="success"
    )


async def update_preferences_tool(
    ctx: CassidyAgentDependencies,
    request: UpdatePreferencesRequest
) -> UpdatePreferencesResponse:
    """
    Tool to update user preferences and template settings.
    
    This tool allows users to modify their preferences and journal template sections.
    Supports both preference updates and template modifications.
    """
    updated_fields = []
    current_prefs = ctx.user_preferences.copy()
    
    for field, value in request.preference_updates.items():
        # Handle preference updates
        if field in ["purpose_statement", "preferred_feedback_style", "personal_glossary"]:
            current_prefs[field] = value
            updated_fields.append(field)
        elif field in ["long_term_goals", "known_challenges"]:
            if isinstance(value, list):
                current_prefs[field] = value
                updated_fields.append(field)
            elif isinstance(value, str):
                # Add to existing list
                if field not in current_prefs:
                    current_prefs[field] = []
                if value not in current_prefs[field]:
                    current_prefs[field].append(value)
                    updated_fields.append(field)
        
        # Handle template modifications
        elif field == "template_reload":
            # Reload template from file
            template_loader.reload_template()
            updated_fields.append("template_reloaded")
        
        elif field.startswith("template_"):
            # Template modification requests
            if field == "template_sections":
                # Request to view available sections
                sections = template_loader.get_template_sections()
                print(f"Available template sections: {list(sections.keys())}")
                updated_fields.append("template_sections_listed")
            
            elif field == "template_info":
                # Request for template information
                template = template_loader.get_user_template()
                print(f"Current template: {template['name']}")
                print(f"Sections: {len(template['sections'])}")
                updated_fields.append("template_info_provided")
            
            elif field == "template_request":
                # User requesting template changes - log for manual implementation
                print(f"TEMPLATE CHANGE REQUEST: {value}")
                print(f"To implement: Edit /app/templates/user_template.py and restart server")
                updated_fields.append("template_change_requested")
    
    # Update context (this will be handled by the agent service)
    ctx.user_preferences = current_prefs
    
    return UpdatePreferencesResponse(
        updated_fields=updated_fields,
        status="success"
    )


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
    description="Update user preferences, settings, and template configuration. Can reload template, view template info, or request template changes."
)


def get_tools_for_conversation_type(conversation_type: str) -> List[Tool]:
    """Return appropriate tools for the given conversation type"""
    if conversation_type == "journaling":
        return [StructureJournalTool, SaveJournalTool, UpdatePreferencesTool]
    elif conversation_type == "general":
        return []
    else:
        return []