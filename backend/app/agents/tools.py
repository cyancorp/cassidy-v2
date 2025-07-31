from pydantic_ai import Tool, RunContext
from typing import Dict, Any, List
import re

from app.agents.models import (
    CassidyAgentDependencies,
    StructureJournalRequest, StructureJournalResponse,
    SaveJournalRequest, SaveJournalResponse,
    UpdatePreferencesRequest, UpdatePreferencesResponse
)
from app.templates.loader import template_loader
from app.agents.task_tools import (
    create_task_tool, list_tasks_tool, complete_task_tool, 
    delete_task_tool, update_task_tool
)


async def structure_journal_tool(
    ctx: RunContext[CassidyAgentDependencies],
    user_text: str
) -> StructureJournalResponse:
    """Structure user experiences, thoughts, and feelings into organized journal sections. Use for personal reflections, daily events, emotions, or activities."""
    
    user_text = user_text.strip()
    if not user_text:
        return StructureJournalResponse(sections_updated=[], status="no_content")
    
    # Get template sections from context (should come from file-based template now)
    template_sections = ctx.deps.user_template.get("sections", {})
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
6. ALWAYS include a "Summary" field - this is mandatory for all entries

MANDATORY SUMMARY FIELD:
- "Summary": A pithy, engaging 1-sentence summary (max 120 characters) that captures the essence of the entry for UI listing. Make it compelling and informative.

DYNAMIC SECTION MAPPING (based on user's template):
{chr(10).join(section_guidelines)}

Template Sections Available:
{chr(10).join(sections_list)}


Raw User Input:
---
{user_text}
---

IMPORTANT: Your JSON response MUST include a "Summary" field with a concise, engaging 1-sentence description (max 120 chars)."""

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
    current_draft = ctx.deps.current_journal_draft.copy()
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
                
        # Check aliases - fixed dict access
        for template_name, section_def in template_sections.items():
            aliases = section_def.get("aliases", []) if isinstance(section_def, dict) else []
            if name.lower() in [alias.lower() for alias in aliases]:
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
    ctx.deps.current_journal_draft = current_draft
    
    return StructureJournalResponse(
        sections_updated=sections_updated,
        updated_draft_data=current_draft,
        status="success"
    )


async def save_journal_tool(
    ctx: RunContext[CassidyAgentDependencies],
    confirmation: bool = True
) -> SaveJournalResponse:
    """Save and finalize the current journal draft as a permanent entry. Only call when user explicitly asks to save."""
    
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
    ctx: RunContext[CassidyAgentDependencies],
    preference_updates: Dict[str, Any]
) -> UpdatePreferencesResponse:
    """Update user goals, challenges, feedback preferences, or personal settings from natural conversation about aspirations and preferences."""
    # WORKAROUND: Get user_id from request if context is wrong
    request_user_id = preference_updates.get("user_id", "")
    actual_user_id = request_user_id if request_user_id and request_user_id != "{{user_id}}" else ctx.deps.user_id
    
    # Extract the user text that might contain preference updates  
    # The agent should pass the user's conversational text in preference_updates["user_text"]
    user_text = preference_updates.get("user_text", "")
    
    # If no user_text provided, try to extract from other string values
    if not user_text.strip():
        text_values = [str(v) for v in preference_updates.values() if isinstance(v, str) and v.strip()]
        user_text = " ".join(text_values)
    
    if not user_text.strip():
        # Fallback to old behavior for direct API calls
        return await _legacy_update_preferences(ctx.deps, preference_updates)
    
    # Get current preferences for context
    current_prefs = ctx.deps.user_preferences.copy()
    
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
    ctx.deps.user_preferences = current_prefs
    
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


# Tool definitions for Pydantic-AI (descriptions come from docstrings)
StructureJournalTool = Tool(structure_journal_tool)
SaveJournalTool = Tool(save_journal_tool)
UpdatePreferencesTool = Tool(update_preferences_tool)


# Task management tools
async def create_task_agent_tool(ctx: RunContext[CassidyAgentDependencies], title: str, description: str = None, priority: int = None, due_date: str = None) -> Dict[str, Any]:
    """Create a new task when user mentions something they need to do, buy, remember, or accomplish. Supports optional due dates (YYYY-MM-DD format)."""
    return await create_task_tool(ctx.deps.user_id, title, description, priority=priority, due_date=due_date, source_session_id=ctx.deps.session_id)

async def list_tasks_agent_tool(ctx: RunContext[CassidyAgentDependencies], include_completed: bool = False) -> Dict[str, Any]:
    """Show user's current tasks. Set include_completed=True to also show finished tasks."""
    return await list_tasks_tool(ctx.deps.user_id, include_completed)

async def complete_task_agent_tool(ctx: RunContext[CassidyAgentDependencies], task_id: str) -> Dict[str, Any]:
    """Mark a task as completed using its exact task ID from the current tasks list."""
    return await complete_task_tool(ctx.deps.user_id, task_id)

async def complete_task_by_title_agent_tool(ctx: RunContext[CassidyAgentDependencies], task_title: str) -> Dict[str, Any]:
    """Mark a task as completed by fuzzy matching its title. Use when user says 'I bought milk', 'finished the report', etc."""
    
    # Find the task in the current context by title
    for task in ctx.deps.current_tasks:
        if task_title.lower() in task['title'].lower() or task['title'].lower() in task_title.lower():
            return await complete_task_tool(ctx.deps.user_id, task['id'])
    
    return {
        "success": False,
        "message": f"No task found matching '{task_title}'. Current tasks: {[t['title'] for t in ctx.deps.current_tasks]}"
    }

async def delete_task_agent_tool(ctx: RunContext[CassidyAgentDependencies], task_id: str) -> Dict[str, Any]:
    """Delete a task permanently using its exact task ID from the current tasks list."""
    return await delete_task_tool(ctx.deps.user_id, task_id)

async def update_task_agent_tool(ctx: RunContext[CassidyAgentDependencies], task_id: str, title: str = None, description: str = None) -> Dict[str, Any]:
    """Update a task's title or description using its exact task ID from the current tasks list."""
    return await update_task_tool(ctx.deps.user_id, task_id, title, description)

# Task tool definitions for Pydantic-AI (descriptions come from docstrings)
CreateTaskTool = Tool(create_task_agent_tool)
ListTasksTool = Tool(list_tasks_agent_tool)
CompleteTaskTool = Tool(complete_task_agent_tool)
CompleteTaskByTitleTool = Tool(complete_task_by_title_agent_tool)
DeleteTaskTool = Tool(delete_task_agent_tool)
UpdateTaskTool = Tool(update_task_agent_tool)

# Journal search and insights tools
async def search_journal_entries_agent_tool(
    ctx: RunContext[CassidyAgentDependencies], 
    query: str = None,
    date_from: str = None,
    date_to: str = None,
    limit: int = 10
) -> str:
    """Search historical journal entries by text content, date range, or keywords. Use when user asks about past entries, goals, or specific topics they've written about."""
    from sqlalchemy import select, and_, or_, cast, String
    from datetime import datetime
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        user_id = ctx.deps.user_id
        logger.info(f"Searching journal entries for user_id: {user_id}, query: {query}, date_from: {date_from}, date_to: {date_to}")
        
        if not user_id:
            return "❌ Unable to search journal entries: User not found"
        
        # Get database session
        from ..database import get_db
        from ..models.session import JournalEntryDB
        
        async for db in get_db():
            try:
                # Build search conditions
                conditions = [JournalEntryDB.user_id == user_id]
                
                # Add text search across multiple fields
                if query and query.strip():
                    query_term = f"%{query.strip()}%"
                    text_conditions = [
                        JournalEntryDB.raw_text.ilike(query_term),
                        JournalEntryDB.title.ilike(query_term)
                    ]
                    
                    # For SQLite, use LIKE on the JSON string representation
                    # For PostgreSQL, we'd use .astext but SQLite doesn't support it
                    try:
                        # Try PostgreSQL syntax first
                        text_conditions.append(JournalEntryDB.structured_data.astext.ilike(query_term))
                    except AttributeError:
                        # Fall back to SQLite - cast to string
                        text_conditions.append(cast(JournalEntryDB.structured_data, String).ilike(query_term))
                    
                    conditions.append(or_(*text_conditions))
                
                # Add date filtering
                if date_from:
                    try:
                        from_date = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                        conditions.append(JournalEntryDB.created_at >= from_date)
                    except ValueError:
                        return f"❌ Invalid date format for date_from: {date_from}. Use YYYY-MM-DD or ISO format."
                
                if date_to:
                    try:
                        to_date = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                        conditions.append(JournalEntryDB.created_at <= to_date)
                    except ValueError:
                        return f"❌ Invalid date format for date_to: {date_to}. Use YYYY-MM-DD or ISO format."
                
                # Execute search query
                search_query = select(JournalEntryDB).where(
                    and_(*conditions)
                ).order_by(JournalEntryDB.created_at.desc()).limit(limit)
                
                result = await db.execute(search_query)
                entries = result.scalars().all()
                
                logger.info(f"Found {len(entries)} matching journal entries")
                
                if not entries:
                    search_info = []
                    if query:
                        search_info.append(f"text matching '{query}'")
                    if date_from:
                        search_info.append(f"from {date_from}")
                    if date_to:
                        search_info.append(f"to {date_to}")
                    
                    search_criteria = " ".join(search_info) if search_info else "your criteria"
                    return f"📝 No journal entries found matching {search_criteria}. Try different search terms or date ranges."
                
                # Format results for the agent to work with
                formatted_entries = []
                for entry in entries:
                    entry_info = {
                        "date": entry.created_at.strftime('%Y-%m-%d %H:%M'),
                        "days_ago": (datetime.utcnow() - entry.created_at).days,
                        "title": entry.title or "Untitled Entry",
                        "raw_text": entry.raw_text or "",
                    }
                    
                    # Include structured data if available - this should be the primary content
                    if entry.structured_data:
                        try:
                            structured = json.loads(entry.structured_data) if isinstance(entry.structured_data, str) else entry.structured_data
                            entry_info["structured_data"] = structured
                            entry_info["structured_sections"] = list(structured.keys()) if structured else []
                            
                            # For backward compatibility, create a summary from structured data
                            if structured and not entry.raw_text:
                                # Build content from structured data
                                content_parts = []
                                for section, content in structured.items():
                                    if content:
                                        if isinstance(content, list):
                                            content_parts.append(f"{section}: {', '.join(str(item) for item in content)}")
                                        else:
                                            content_parts.append(f"{section}: {content}")
                                entry_info["content"] = " | ".join(content_parts)
                            else:
                                entry_info["content"] = entry.raw_text or ""
                        except Exception as e:
                            logger.warning(f"Error parsing structured data: {e}")
                            entry_info["content"] = entry.raw_text or ""
                    else:
                        entry_info["content"] = entry.raw_text or ""
                    
                    formatted_entries.append(entry_info)
                
                # Create a comprehensive response for the agent
                search_summary = []
                if query:
                    search_summary.append(f"containing '{query}'")
                if date_from or date_to:
                    date_range = []
                    if date_from:
                        date_range.append(f"from {date_from}")
                    if date_to:
                        date_range.append(f"to {date_to}")
                    search_summary.append(" ".join(date_range))
                
                search_criteria = " ".join(search_summary) if search_summary else "all entries"
                
                # Format entries for agent context
                entries_text = []
                for entry in formatted_entries:
                    entry_text = f"📅 **{entry['date']}** ({entry['days_ago']} days ago)\n"
                    entry_text += f"**Title:** {entry['title']}\n"
                    
                    # Show structured data if available
                    if entry.get('structured_data'):
                        entry_text += "**Structured Content:**\n"
                        for section, content in entry['structured_data'].items():
                            if content:
                                if isinstance(content, list):
                                    content_str = ', '.join(str(item) for item in content[:3])
                                    if len(content) > 3:
                                        content_str += f" (and {len(content) - 3} more)"
                                else:
                                    content_str = str(content)[:200]
                                    if len(str(content)) > 200:
                                        content_str += "..."
                                entry_text += f"  - {section}: {content_str}\n"
                    elif entry.get('raw_text'):
                        # Fall back to raw text if no structured data
                        entry_text += f"**Content:** {entry['raw_text'][:300]}{'...' if len(entry['raw_text']) > 300 else ''}\n"
                    
                    entries_text.append(entry_text)
                
                result_text = "\n---\n".join(entries_text)
                
                return f"""📝 **Journal Search Results**
Found {len(entries)} entries {search_criteria}:

{result_text}

💡 **What would you like to know about these entries?** I can help you analyze patterns, extract specific information, or answer questions about your past thoughts and experiences."""
                
            except Exception as e:
                logger.error(f"Error searching journal entries: {e}", exc_info=True)
                return f"❌ Error searching journal entries: {str(e)}"
    
    except Exception as e:
        logger.error(f"Error searching journal entries: {e}", exc_info=True)
        return f"❌ Error searching journal entries: {str(e)}"

async def generate_insights_agent_tool(ctx: RunContext[CassidyAgentDependencies], limit: int = 50) -> str:
    """Generate insights from your recent journal entries. Analyzes patterns, moods, activities, and provides personalized recommendations. Default: last 50 entries."""
    from sqlalchemy import select, and_
    from datetime import datetime, timedelta
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get user_id from context
        user_id = ctx.deps.user_id
        
        logger.info(f"Generating insights for user_id: {user_id}")
        
        if not user_id:
            return "❌ Unable to generate insights: User not found"
        
        # Get database session
        from ..database import get_db
        from ..models.user import UserDB
        
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        try:
            # Get user object
            user_result = await db.execute(select(UserDB).where(UserDB.id == user_id))
            user = user_result.scalar_one_or_none()
            
            if not user:
                return "❌ Unable to generate insights: User not found"
            
            # Get most recent journal entries
            today = datetime.utcnow()
            
            from ..models.session import JournalEntryDB
            
            query = select(JournalEntryDB).where(
                JournalEntryDB.user_id == user.id
            ).order_by(JournalEntryDB.created_at.desc()).limit(limit)
            
            result = await db.execute(query)
            entries = result.scalars().all()
            
            logger.info(f"Found {len(entries)} journal entries for analysis")
            
            if not entries:
                return f"📊 No journal entries found. Keep journaling to discover insights!"
            
            # Prepare entries for analysis (leveraging Claude's context window)
            entries_text = []
            for entry in entries:
                entry_info = f"Date: {entry.created_at.strftime('%Y-%m-%d %H:%M')} ({(today - entry.created_at).days} days ago)\n"
                if entry.title:
                    entry_info += f"Title: {entry.title}\n"
                if entry.raw_text:
                    entry_info += f"Entry: {entry.raw_text}\n"
                
                # Include structured data for richer analysis
                if entry.structured_data:
                    try:
                        structured = json.loads(entry.structured_data)
                        if "mood" in structured:
                            entry_info += f"Mood: {structured['mood'].get('current_mood', 'unknown')}, Energy: {structured['mood'].get('energy_level', 'N/A')}\n"
                        if "activities" in structured:
                            entry_info += f"Activities: {', '.join(structured['activities'])}\n"
                        if "tags" in structured:
                            entry_info += f"Tags: {', '.join(structured['tags'])}\n"
                    except:
                        pass
                
                entries_text.append(entry_info)
            
            # Create analysis prompt
            journal_content = "\n---\n".join(entries_text)
            
            # Calculate date range for context
            oldest_entry_date = entries[-1].created_at if entries else today
            date_range_days = (today - oldest_entry_date).days
            
            analysis_prompt = f"""
Today's date: {today.strftime('%Y-%m-%d')}

Based on these {len(entries)} most recent journal entries (spanning {date_range_days} days), provide a comprehensive analysis:

{journal_content}

Please analyze and provide:

# 📊 Journal Insights Report

## 📈 Summary
- Total entries analyzed and frequency
- Overall emotional state and energy levels

## 🔍 Key Patterns
- Mood patterns and trends (with specific examples)
- Common activities and their correlation with moods
- Recurring themes or concerns
- Time-based patterns (morning vs evening, weekdays vs weekends)

## 💪 Strengths & Achievements
- Positive patterns to celebrate
- Growth areas identified
- Successful coping strategies observed

## 🎯 Areas for Attention
- Potential stress triggers or patterns
- Imbalances in activities or moods
- Suggestions for improvement

## 💡 Personalized Recommendations
- 3-5 specific, actionable recommendations based on the patterns
- Suggestions should be practical and tailored to what you observed

## 📊 Mood Trend
- Overall trajectory of emotional wellbeing
- Notable shifts or changes

Keep the analysis empathetic, constructive, and focused on actionable insights.
"""
            
            # Return the formatted journal data for the agent to analyze
            insights_data = {
                "instruction": "Please analyze these journal entries and provide insights following the format below.",
                "entries_count": len(entries),
                "date_range_days": date_range_days,
                "journal_entries": journal_content,
                "analysis_format": """
# 📊 Journal Insights Report

## 📈 Summary
- Total entries analyzed and frequency
- Overall emotional state and energy levels

## 🔍 Key Patterns
- Mood patterns and trends (with specific examples)
- Common activities and their correlation with moods
- Recurring themes or concerns
- Time-based patterns

## 💪 Strengths & Achievements
- Positive patterns to celebrate
- Growth areas identified
- Successful coping strategies observed

## 🎯 Areas for Attention
- Potential stress triggers or patterns
- Imbalances in activities or moods
- Suggestions for improvement

## 💡 Personalized Recommendations
- 3-5 specific, actionable recommendations based on the patterns
- Suggestions should be practical and tailored to what you observed

## 📊 Mood Trend
- Overall trajectory of emotional wellbeing
- Notable shifts or changes
"""
            }
            
            # Format as a clear request for analysis
            return f"""Today is {today.strftime('%A, %B %d, %Y')}.

I've collected your {len(entries)} most recent journal entries (spanning {date_range_days} days from {oldest_entry_date.strftime('%B %d')} to {entries[0].created_at.strftime('%B %d')}). Here they are:

{journal_content}

Please analyze these entries and provide comprehensive insights following this format:

{insights_data['analysis_format']}

Keep the analysis empathetic, constructive, and focused on actionable insights."""
            
        finally:
            # Clean up database session
            await db_gen.aclose()
        
    except Exception as e:
        logger.error(f"Error generating insights: {e}", exc_info=True)
        return f"❌ Error generating insights: {str(e)}"

SearchJournalTool = Tool(search_journal_entries_agent_tool)
GenerateInsightsTool = Tool(generate_insights_agent_tool)


def get_tools_for_conversation_type(conversation_type: str) -> List[Tool]:
    """Return appropriate tools for the given conversation type"""
    if conversation_type == "journaling":
        return [StructureJournalTool, SaveJournalTool, UpdatePreferencesTool, CreateTaskTool, ListTasksTool, CompleteTaskByTitleTool, CompleteTaskTool, DeleteTaskTool, UpdateTaskTool, SearchJournalTool, GenerateInsightsTool]
    elif conversation_type == "general":
        return [CreateTaskTool, ListTasksTool, CompleteTaskByTitleTool, CompleteTaskTool, DeleteTaskTool, UpdateTaskTool, SearchJournalTool, GenerateInsightsTool]
    else:
        return []