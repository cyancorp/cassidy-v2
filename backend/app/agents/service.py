from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from app.agents.models import CassidyAgentDependencies
from app.repositories.user import UserPreferencesRepository
from app.repositories.session import JournalDraftRepository, ChatMessageRepository
from app.templates.loader import template_loader


class AgentService:
    """Service for managing AI agent interactions"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_prefs_repo = UserPreferencesRepository()
        self.journal_draft_repo = JournalDraftRepository()
        self.message_repo = ChatMessageRepository()
    
    async def create_agent_context(
        self, 
        user_id: str, 
        session_id: str,
        conversation_type: str = "journaling"
    ) -> CassidyAgentDependencies:
        """Create agent context with user data"""
        
        # Load user data
        user_prefs = await self.user_prefs_repo.get_by_user_id(self.db, user_id)
        journal_draft = await self.journal_draft_repo.get_by_session_id(self.db, session_id)
        
        # Load template from file (instead of database)
        user_template_dict = template_loader.get_user_template(user_id)
        
        # Create defaults if needed
        if not user_prefs:
            user_prefs = await self._create_default_preferences(user_id)
        if not journal_draft:
            journal_draft = await self.journal_draft_repo.create_draft(
                self.db, session_id=session_id, user_id=user_id
            )
        
        # Convert to dictionaries for the agent context
        prefs_dict = {
            "purpose_statement": user_prefs.purpose_statement,
            "long_term_goals": user_prefs.long_term_goals or [],
            "known_challenges": user_prefs.known_challenges or [],
            "preferred_feedback_style": user_prefs.preferred_feedback_style,
            "personal_glossary": user_prefs.personal_glossary or {}
        }
        
        # Use file-based template instead of database template
        template_dict = user_template_dict
        
        # Get the latest draft data from the database
        latest_draft = await self.journal_draft_repo.get_by_session_id(self.db, session_id)
        draft_dict = latest_draft.draft_data if latest_draft else {}
        print(f"Creating context with draft data: {draft_dict}")
        
        return CassidyAgentDependencies(
            user_id=user_id,
            session_id=session_id,
            conversation_type=conversation_type,
            user_template=template_dict,
            user_preferences=prefs_dict,
            current_journal_draft=draft_dict
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
                            tool_calls.append({
                                "name": part.tool_name,
                                "input": getattr(part, 'input', {}),  # May not have input in return
                                "output": part.content
                            })
        
        response_data["tool_calls"] = tool_calls
        
        # Check for structure journal tool calls to update draft
        for call in tool_calls:
            if call["name"] == "structure_journal_tool":
                print(f"Processing structure_journal_tool call")
                print(f"Tool call output: {call['output']}")
                
                # Get the updated draft data from the tool response
                output = call["output"]
                if hasattr(output, 'updated_draft_data'):
                    updated_draft = output.updated_draft_data
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
                
                if hasattr(output, 'status') and output.status == "success":
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
        return await self.user_prefs_repo.create(
            self.db,
            user_id=user_id,
            purpose_statement=None,
            long_term_goals=[],
            known_challenges=[],
            preferred_feedback_style="supportive",
            personal_glossary={}
        )
    
