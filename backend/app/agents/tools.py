from pydantic_ai import Tool
from typing import Dict, Any, List
import re

from app.agents.models import (
    CassidyAgentDependencies,
    StructureJournalRequest, StructureJournalResponse,
    SaveJournalRequest, SaveJournalResponse,
    UpdatePreferencesRequest, UpdatePreferencesResponse
)


async def structure_journal_tool(
    ctx: CassidyAgentDependencies,
    request: StructureJournalRequest
) -> StructureJournalResponse:
    """
    Tool to structure user input into journal template sections.
    
    This tool analyzes the user's text and maps it to appropriate sections
    in their personal journal template based on content and section descriptions.
    """
    print(f"StructureJournalTool called with text: {request.user_text}")
    user_text = request.user_text.strip()
    if not user_text:
        return StructureJournalResponse(sections_updated=[], status="no_content")
    
    # Get template sections from context
    template_sections = ctx.user_template.get("sections", {})
    if not template_sections:
        # Default sections if no template
        template_sections = {
            "General Reflection": {
                "description": "General thoughts, daily reflections, or free-form journaling content",
                "aliases": ["Daily Notes", "Journal", "Reflection", "General"]
            }
        }
    
    # Get current draft data
    current_draft = ctx.current_journal_draft.copy()
    sections_updated = []
    
    # Simple content classification based on keywords and patterns
    text_lower = user_text.lower()
    
    # Check for each section based on keywords and content
    for section_name, section_def in template_sections.items():
        section_desc = section_def.get("description", "").lower()
        aliases = [alias.lower() for alias in section_def.get("aliases", [])]
        
        # Check if content matches this section
        should_add_to_section = False
        
        # Trading journal specific patterns
        if any(keyword in section_desc for keyword in ["trading", "trade", "position"]):
            if any(word in text_lower for word in ["trade", "bought", "sold", "position", "profit", "loss", "entry", "exit", "$", "shares"]):
                should_add_to_section = True
        
        # Market thoughts patterns
        elif any(keyword in section_desc for keyword in ["market", "analysis", "trend"]):
            if any(word in text_lower for word in ["market", "bullish", "bearish", "trend", "analysis", "outlook", "economic", "fed", "inflation"]):
                should_add_to_section = True
        
        # Emotional state patterns
        elif any(keyword in section_desc for keyword in ["mood", "emotion", "feeling", "well-being"]):
            if any(word in text_lower for word in ["feel", "mood", "happy", "sad", "anxious", "excited", "stressed", "confident", "worried"]):
                should_add_to_section = True
        
        # Strategy patterns
        elif any(keyword in section_desc for keyword in ["strategy", "planning", "approach"]):
            if any(word in text_lower for word in ["strategy", "plan", "approach", "thinking", "consider", "next step", "goal"]):
                should_add_to_section = True
        
        # Goals patterns
        elif any(keyword in section_desc for keyword in ["goal", "objective", "next week"]):
            if any(word in text_lower for word in ["goal", "objective", "next week", "plan to", "want to", "will do", "tomorrow"]):
                should_add_to_section = True
        
        # Gratitude patterns
        elif any(keyword in section_desc for keyword in ["grateful", "gratitude"]):
            if any(word in text_lower for word in ["grateful", "thankful", "appreciate", "blessed", "grateful for"]):
                should_add_to_section = True
        
        # Weekly review patterns
        elif any(keyword in section_desc for keyword in ["review", "accomplish", "progress"]):
            if any(word in text_lower for word in ["accomplished", "completed", "finished", "did", "this week", "progress"]):
                should_add_to_section = True
        
        # General reflection (fallback)
        elif any(keyword in section_desc for keyword in ["general", "reflection", "daily"]):
            # If no other section matched strongly, add to general
            if not any(sections_updated):  # Only if no specific section was found
                should_add_to_section = True
        
        # Add content to section if it matches
        if should_add_to_section:
            if section_name in current_draft:
                # Append to existing content
                existing_content = current_draft[section_name]
                if isinstance(existing_content, str):
                    current_draft[section_name] = existing_content + "\n\n" + user_text
                elif isinstance(existing_content, list):
                    current_draft[section_name].append(user_text)
                else:
                    current_draft[section_name] = user_text
            else:
                # Create new content
                current_draft[section_name] = user_text
            
            sections_updated.append(section_name)
    
    # If no specific section matched, add to general reflection
    if not sections_updated:
        general_section = None
        for section_name, section_def in template_sections.items():
            if any(keyword in section_def.get("description", "").lower() for keyword in ["general", "reflection", "open"]):
                general_section = section_name
                break
        
        if not general_section:
            general_section = "General Reflection"
        
        if general_section in current_draft:
            existing_content = current_draft[general_section]
            if isinstance(existing_content, str):
                current_draft[general_section] = existing_content + "\n\n" + user_text
            else:
                current_draft[general_section] = user_text
        else:
            current_draft[general_section] = user_text
        
        sections_updated.append(general_section)
    
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
    Tool to update user preferences based on conversation insights.
    
    This tool allows the agent to learn about user preferences and update them accordingly.
    """
    updated_fields = []
    current_prefs = ctx.user_preferences.copy()
    
    for field, value in request.preference_updates.items():
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
    description="Update user preferences based on insights from the conversation"
)


def get_tools_for_conversation_type(conversation_type: str) -> List[Tool]:
    """Return appropriate tools for the given conversation type"""
    if conversation_type == "journaling":
        return [StructureJournalTool, SaveJournalTool, UpdatePreferencesTool]
    elif conversation_type == "general":
        return []
    else:
        return []