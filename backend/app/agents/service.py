from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from app.agents.models import CassidyAgentDependencies
from app.repositories.user import UserRepository
from app.repositories.session import JournalDraftRepository, ChatMessageRepository
from app.repositories.task import TaskRepository
from app.templates.loader import template_loader


class AgentService:
    """Service for managing AI agent interactions"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository()
        self.journal_draft_repo = JournalDraftRepository()
        self.message_repo = ChatMessageRepository()
        self.task_repo = TaskRepository()
    
    async def create_agent_context(
        self, 
        user_id: str, 
        session_id: str,
        conversation_type: str = "journaling"
    ) -> CassidyAgentDependencies:
        """Create agent context with user data"""
        
        # Load user data
        user_prefs = await self.user_repo.get_user_preferences(self.db, user_id)
        journal_draft = await self.journal_draft_repo.get_by_session_id(self.db, session_id)
        current_tasks = await self.task_repo.get_pending_by_user_id(self.db, user_id)
        
        # Load template from file (instead of database)
        user_template_dict = template_loader.get_user_template(user_id)
        
        # Create defaults if needed
        if not user_prefs:
            user_prefs = await self._create_default_preferences(user_id)
        if not journal_draft:
            journal_draft = await self.journal_draft_repo.create_draft(
                self.db, session_id=session_id, user_id=user_id
            )
        
        # User preferences are already a dictionary
        prefs_dict = user_prefs
        
        # Use file-based template instead of database template
        template_dict = user_template_dict
        
        # Get the latest draft data from the database
        latest_draft = await self.journal_draft_repo.get_by_session_id(self.db, session_id)
        draft_dict = latest_draft.draft_data if latest_draft else {}
        
        # Convert tasks to dictionaries for context
        tasks_dict = []
        for task in current_tasks:
            task_dict = {
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "due_date": task.due_date,
                "created_at": task.created_at.isoformat()
            }
            tasks_dict.append(task_dict)
        
        print(f"Creating context with draft data: {draft_dict}")
        print(f"Current tasks: {len(tasks_dict)} pending")
        print(f"Task details: {[{'id': t['id'], 'title': t['title']} for t in tasks_dict]}")
        
        return CassidyAgentDependencies(
            user_id=user_id,
            session_id=session_id,
            conversation_type=conversation_type,
            user_template=template_dict,
            user_preferences=prefs_dict,
            current_journal_draft=draft_dict,
            current_tasks=tasks_dict
        )
    
    async def process_agent_response(
        self,
        context: CassidyAgentDependencies,
        agent_result: Any
    ) -> Dict[str, Any]:
        """Process agent response and update database accordingly"""
        
        response_data = {
            "updated_draft_data": None,
            "tool_calls": [],
            "metadata": {}
        }
        
        # Extract tool calls from messages
        tool_calls = []
        if hasattr(agent_result, 'new_messages'):
            for message in agent_result.new_messages():
                if hasattr(message, 'parts'):
                    for part in message.parts:
                        # Check if this is a tool return part
                        if hasattr(part, 'tool_name') and hasattr(part, 'content'):
                            # Serialize content if it's a Pydantic model
                            content = part.content
                            if hasattr(content, 'model_dump'):
                                # Pydantic v2 model
                                content = content.model_dump()
                            elif hasattr(content, 'dict'):
                                # Pydantic v1 model
                                content = content.dict()
                            
                            tool_calls.append({
                                "name": part.tool_name,
                                "input": getattr(part, 'input', {}),  # May not have input in return
                                "output": content
                            })
        
        response_data["tool_calls"] = tool_calls
        
        # Check for structure journal tool calls to update draft
        for call in tool_calls:
            if call["name"] == "structure_journal_tool":
                print(f"Processing structure_journal_tool call")
                print(f"Tool call output: {call['output']}")
                
                # Get the updated draft data from the tool response
                output = call["output"]
                if isinstance(output, dict) and 'updated_draft_data' in output:
                    updated_draft = output['updated_draft_data']
                    print(f"Updated draft from tool: {updated_draft}")
                    
                    # Update the draft in database
                    await self.journal_draft_repo.update_draft_data(
                        self.db, context.session_id, updated_draft
                    )
                    response_data["updated_draft_data"] = updated_draft
                else:
                    print(f"No updated_draft_data in tool output")
            
            elif call["name"] == "save_journal_tool":
                output = call["output"]
                print(f"Processing save_journal_tool call")
                print(f"Save tool output: {output}")
                
                if isinstance(output, dict) and output.get('status') == "success":
                    # Get the latest draft from database to check if there's content
                    latest_draft = await self.journal_draft_repo.get_by_session_id(
                        self.db, context.session_id
                    )
                    
                    print(f"Latest draft from DB: {latest_draft.draft_data if latest_draft else 'None'}")
                    
                    if latest_draft and latest_draft.draft_data and any(latest_draft.draft_data.values()):
                        # Finalize the draft
                        journal_entry = await self.journal_draft_repo.finalize_draft(
                            self.db, context.session_id
                        )
                        if journal_entry:
                            response_data["metadata"]["journal_entry_id"] = journal_entry.id
                            print(f"Journal entry created: {journal_entry.id}")
                            
                            # Analyze journal content for preference updates (non-blocking)
                            try:
                                await self._analyze_and_update_preferences(
                                    context, journal_entry.raw_text, journal_entry.structured_data
                                )
                            except Exception as e:
                                print(f"Warning: Preference analysis failed: {e}")
                            
                            # Clear the context to allow new journal entries
                            context.current_journal_draft = {}
                    else:
                        print(f"No content to save - draft is empty")
            
            elif call["name"] == "update_preferences_tool":
                # Skip processing - tool handles database updates directly to avoid overwriting
                print(f"Skipping update_preferences_tool processing - tool handles database updates directly")
        
        # Add usage metadata if available
        if hasattr(agent_result, 'usage') and agent_result.usage:
            response_data["metadata"]["usage"] = {
                "tokens": getattr(agent_result.usage, 'total_tokens', 0)
            }
        
        return response_data
    
    async def get_message_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get formatted message history for the agent"""
        messages = await self.message_repo.get_by_session_id(self.db, session_id)
        print(f"Retrieved {len(messages)} messages from database")
        
        formatted_messages = []
        for msg in messages:
            formatted_msg = self.message_repo.to_pydantic_message(msg)
            print(f"Formatted message: {formatted_msg}")
            formatted_messages.append(formatted_msg)
        
        print(f"Returning {len(formatted_messages)} formatted messages")
        return formatted_messages
    
    async def _create_default_preferences(self, user_id: str):
        """Create default preferences for new user"""
        default_prefs = {
            "name": None,
            "purpose_statement": None,
            "long_term_goals": [],
            "known_challenges": [],
            "preferred_feedback_style": "supportive",
            "personal_glossary": {}
        }
        await self.user_repo.update_user_preferences(self.db, user_id, default_prefs)
        return default_prefs
    
    async def _analyze_and_update_preferences(
        self, 
        context: CassidyAgentDependencies, 
        raw_text: str, 
        structured_data: Dict[str, Any]
    ) -> None:
        """Analyze journal content and update user preferences if insights are found"""
        
        if not raw_text and not structured_data:
            return
            
        # Combine all text content for analysis
        analysis_text = raw_text or ""
        if structured_data:
            # Add structured content for more comprehensive analysis
            for section, content in structured_data.items():
                if isinstance(content, str) and content.strip():
                    analysis_text += f"\n{section}: {content}"
                elif isinstance(content, list):
                    analysis_text += f"\n{section}: {', '.join(str(item) for item in content)}"
        
        if not analysis_text.strip():
            return
            
        # Skip analysis if content is too short to be meaningful
        if len(analysis_text.strip()) < 50:
            return
            
        current_prefs = context.user_preferences
        
        # Create analysis prompt
        analysis_prompt = f"""Analyze this journal entry for insights about the user's preferences. Only suggest updates if there are clear, meaningful insights that would improve the user experience.

CURRENT USER PREFERENCES:
- Name: {current_prefs.get('name', 'Not provided')}
- Purpose: {current_prefs.get('purpose_statement', 'None set')}
- Goals: {current_prefs.get('long_term_goals', [])}
- Challenges: {current_prefs.get('known_challenges', [])}
- Feedback Style: {current_prefs.get('preferred_feedback_style', 'supportive')}
- Personal Terms: {len(current_prefs.get('personal_glossary', {}))} defined

JOURNAL CONTENT:
{analysis_text}

INSTRUCTIONS:
1. Look for NEW insights not already captured in current preferences
2. Identify clear goals, challenges, or purpose statements the user expresses
3. Note any terms they use with specific personal meaning
4. Only suggest updates for significant insights, not minor mentions
5. Return JSON with only fields that should be updated, or empty object if no updates needed

VALID UPDATES:
- name: String with user's preferred name if they mention it (e.g., "I'm Alex", "call me Sarah")
- purpose_statement: String describing why they journal/their main focus
- long_term_goals: Array of strings for new goals to ADD (don't replace existing)
- known_challenges: Array of strings for new challenges to ADD (don't replace existing)  
- personal_glossary: Object with new terms/definitions to ADD
- preferred_feedback_style: "supportive", "detailed", "brief", or "challenging"

JSON Output:"""

        try:
            # Import here to avoid circular dependencies
            import json
            import os
            from pydantic_ai import Agent
            from pydantic_ai.models.anthropic import AnthropicModel
            from app.core.config import settings, get_anthropic_api_key
            
            # Set up LLM
            api_key = get_anthropic_api_key()
            if not api_key:
                return
                
            os.environ["ANTHROPIC_API_KEY"] = api_key
            model = AnthropicModel(settings.ANTHROPIC_STRUCTURING_MODEL)
            analysis_agent = Agent(model=model)
            
            # Run analysis
            result = await analysis_agent.run(analysis_prompt)
            analysis_output = result.output.strip()
            
            # Parse JSON response
            if analysis_output.startswith("```json"):
                analysis_output = analysis_output[7:]
            if analysis_output.endswith("```"):
                analysis_output = analysis_output[:-3]
            analysis_output = analysis_output.strip()
            
            try:
                updates = json.loads(analysis_output)
            except json.JSONDecodeError:
                print(f"Failed to parse preference analysis JSON: {analysis_output}")
                return
                
            if not updates or not isinstance(updates, dict):
                return
                
            # Apply updates (add to existing rather than replace)
            updated_prefs = current_prefs.copy()
            changes_made = []
            
            # Update name if provided and different
            if updates.get('name') and updates['name'] != current_prefs.get('name'):
                updated_prefs['name'] = updates['name']
                changes_made.append('name')
            
            # Update purpose if provided and different
            if updates.get('purpose_statement') and updates['purpose_statement'] != current_prefs.get('purpose_statement'):
                updated_prefs['purpose_statement'] = updates['purpose_statement']
                changes_made.append('purpose_statement')
            
            # Add new goals (don't replace existing)
            if updates.get('long_term_goals') and isinstance(updates['long_term_goals'], list):
                existing_goals = set(current_prefs.get('long_term_goals', []))
                new_goals = [goal for goal in updates['long_term_goals'] if goal not in existing_goals]
                if new_goals:
                    updated_prefs['long_term_goals'] = list(existing_goals) + new_goals
                    changes_made.append('long_term_goals')
            
            # Add new challenges (don't replace existing)
            if updates.get('known_challenges') and isinstance(updates['known_challenges'], list):
                existing_challenges = set(current_prefs.get('known_challenges', []))
                new_challenges = [challenge for challenge in updates['known_challenges'] if challenge not in existing_challenges]
                if new_challenges:
                    updated_prefs['known_challenges'] = list(existing_challenges) + new_challenges
                    changes_made.append('known_challenges')
            
            # Update feedback style if provided and valid
            valid_styles = ["supportive", "detailed", "brief", "challenging"]
            if updates.get('preferred_feedback_style') in valid_styles:
                if updates['preferred_feedback_style'] != current_prefs.get('preferred_feedback_style'):
                    updated_prefs['preferred_feedback_style'] = updates['preferred_feedback_style']
                    changes_made.append('preferred_feedback_style')
            
            # Add new glossary terms (don't replace existing)
            if updates.get('personal_glossary') and isinstance(updates['personal_glossary'], dict):
                existing_glossary = current_prefs.get('personal_glossary', {})
                new_terms = {k: v for k, v in updates['personal_glossary'].items() if k not in existing_glossary}
                if new_terms:
                    updated_prefs['personal_glossary'] = {**existing_glossary, **new_terms}
                    changes_made.append('personal_glossary')
            
            # Save to database if changes were made
            if changes_made:
                await self.user_repo.update_user_preferences(self.db, context.user_id, updated_prefs)
                # Update context for immediate use
                context.user_preferences = updated_prefs
                print(f"✅ Updated user preferences: {', '.join(changes_made)}")
            
        except Exception as e:
            print(f"Error in preference analysis: {e}")
            # Don't raise - this is non-critical functionality
    
