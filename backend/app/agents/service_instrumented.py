import time
import functools
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from app.agents.models import CassidyAgentDependencies
from app.repositories.user import UserPreferencesRepository
from app.repositories.session import JournalDraftRepository, ChatMessageRepository
from app.repositories.task import TaskRepository
from app.templates.loader import template_loader
from app.agents.factory import AgentFactory


def timing_decorator(func_name):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            elapsed = (time.time() - start_time) * 1000  # Convert to milliseconds
            print(f"⏱️  {func_name}: {elapsed:.2f}ms")
            return result
        return wrapper
    return decorator


class InstrumentedAgentService:
    """Instrumented version of AgentService for performance analysis"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_prefs_repo = UserPreferencesRepository()
        self.journal_draft_repo = JournalDraftRepository()
        self.message_repo = ChatMessageRepository()
        self.task_repo = TaskRepository()
        self.timing_results = {}
    
    @timing_decorator("create_agent_context")
    async def create_agent_context(
        self, 
        user_id: str, 
        session_id: str,
        conversation_type: str = "journaling"
    ) -> CassidyAgentDependencies:
        """Create agent context with user data"""
        
        # Time individual database queries
        start = time.time()
        user_prefs = await self.user_prefs_repo.get_by_user_id(self.db, user_id)
        print(f"  📊 get_user_preferences: {(time.time() - start) * 1000:.2f}ms")
        
        start = time.time()
        journal_draft = await self.journal_draft_repo.get_by_session_id(self.db, session_id)
        print(f"  📊 get_journal_draft: {(time.time() - start) * 1000:.2f}ms")
        
        start = time.time()
        current_tasks = await self.task_repo.get_pending_by_user_id(self.db, user_id)
        print(f"  📊 get_pending_tasks: {(time.time() - start) * 1000:.2f}ms - Found {len(current_tasks)} tasks")
        
        # Load template from file (instead of database)
        start = time.time()
        user_template_dict = template_loader.get_user_template(user_id)
        print(f"  📊 load_template: {(time.time() - start) * 1000:.2f}ms")
        
        # Create defaults if needed
        if not user_prefs:
            start = time.time()
            user_prefs = await self._create_default_preferences(user_id)
            print(f"  📊 create_default_preferences: {(time.time() - start) * 1000:.2f}ms")
        if not journal_draft:
            start = time.time()
            journal_draft = await self.journal_draft_repo.create_draft(
                self.db, session_id=session_id, user_id=user_id
            )
            print(f"  📊 create_draft: {(time.time() - start) * 1000:.2f}ms")
        
        # Convert to dictionaries for the agent context
        prefs_dict = {
            "purpose_statement": user_prefs.purpose_statement,
            "long_term_goals": user_prefs.long_term_goals or [],
            "known_challenges": user_prefs.known_challenges or [],
            "preferred_feedback_style": user_prefs.preferred_feedback_style or "supportive",
            "personal_glossary": user_prefs.personal_glossary or {}
        }
        
        # Convert tasks to dict format
        tasks_list = []
        for task in current_tasks:
            tasks_list.append({
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "is_completed": task.is_completed,
                "due_date": task.due_date,
                "created_at": task.created_at.isoformat(),
                "source_session_id": str(task.source_session_id) if task.source_session_id else None
            })
        
        return CassidyAgentDependencies(
            user_id=user_id,
            session_id=session_id,
            conversation_type=conversation_type,
            user_template=user_template_dict,
            user_preferences=prefs_dict,
            current_journal_draft=journal_draft.draft_data if journal_draft else {},
            current_tasks=tasks_list
        )
    
    @timing_decorator("process_message")
    async def process_message(
        self, 
        user_id: str, 
        session_id: str, 
        message: str,
        conversation_type: str = "journaling"
    ) -> Dict[str, Any]:
        """Process a user message with the AI agent"""
        print(f"\n🚀 Starting message processing for: '{message[:50]}...'")
        overall_start = time.time()
        
        # Create context
        context = await self.create_agent_context(user_id, session_id, conversation_type)
        
        # Initialize agent
        start = time.time()
        agent = await AgentFactory.get_agent(conversation_type, context.user_id, context)
        print(f"⏱️  create_agent: {(time.time() - start) * 1000:.2f}ms")
        
        # Get message history
        message_history = await self.get_message_history(session_id)
        
        # Call agent
        start = time.time()
        agent_result = await agent.run(message, deps=context, message_history=message_history)
        llm_time = (time.time() - start) * 1000
        print(f"🤖 LLM call (agent.run): {llm_time:.2f}ms")
        
        # Process response
        response = await self.process_agent_response(agent_result, context)
        
        # Save messages to database
        start = time.time()
        await self.message_repo.create(
            self.db,
            session_id=session_id,
            role="user",
            content=message
        )
        await self.message_repo.create(
            self.db,
            session_id=session_id,
            role="assistant",
            content=response["message"]
        )
        print(f"⏱️  save_messages: {(time.time() - start) * 1000:.2f}ms")
        
        total_time = (time.time() - overall_start) * 1000
        print(f"\n✅ Total processing time: {total_time:.2f}ms")
        print(f"   - LLM call: {llm_time:.2f}ms ({(llm_time/total_time)*100:.1f}%)")
        print(f"   - Other operations: {total_time - llm_time:.2f}ms ({((total_time - llm_time)/total_time)*100:.1f}%)")
        
        response["performance_metrics"] = {
            "total_time_ms": total_time,
            "llm_time_ms": llm_time,
            "llm_percentage": (llm_time/total_time)*100
        }
        
        return response
    
    @timing_decorator("process_agent_response")
    async def process_agent_response(self, agent_result, context: CassidyAgentDependencies) -> Dict[str, Any]:
        """Process the agent's response and update database as needed"""
        response_data = {
            "message": agent_result.data,
            "tool_calls": [],
            "metadata": {},
            "success": True
        }
        
        # Process tool calls if any
        if hasattr(agent_result, 'all_tool_calls') and agent_result.all_tool_calls:
            start = time.time()
            for call in agent_result.all_tool_calls:
                tool_call_data = {
                    "name": call["name"],
                    "input": call.get("input", {}),
                    "output": call.get("output", {})
                }
                response_data["tool_calls"].append(tool_call_data)
                
                # Handle specific tool calls
                if call["name"] == "structure_journal_tool":
                    output = call["output"]
                    if hasattr(output, 'updated_draft_data'):
                        updated_draft = output.updated_draft_data
                        await self.journal_draft_repo.update_draft_data(
                            self.db, context.session_id, updated_draft
                        )
                        response_data["updated_draft_data"] = updated_draft
                
                elif call["name"] == "save_journal_tool":
                    output = call["output"]
                    if hasattr(output, 'status') and output.status == "success":
                        latest_draft = await self.journal_draft_repo.get_by_session_id(
                            self.db, context.session_id
                        )
                        if latest_draft and latest_draft.draft_data and any(latest_draft.draft_data.values()):
                            journal_entry = await self.journal_draft_repo.finalize_draft(
                                self.db, context.session_id
                            )
                            if journal_entry:
                                response_data["metadata"]["journal_entry_id"] = journal_entry.id
                                context.current_journal_draft = {}
            
            print(f"⏱️  process_tool_calls: {(time.time() - start) * 1000:.2f}ms")
        
        # Add usage metadata if available
        if hasattr(agent_result, 'usage') and agent_result.usage:
            try:
                response_data["metadata"]["usage"] = {
                    "total_tokens": getattr(agent_result.usage, 'total_tokens', 0),
                    "prompt_tokens": getattr(agent_result.usage, 'prompt_tokens', 0),
                    "completion_tokens": getattr(agent_result.usage, 'completion_tokens', 0)
                }
            except AttributeError:
                response_data["metadata"]["usage"] = {"error": "Usage data format unknown"}
        
        return response_data
    
    @timing_decorator("get_message_history")
    async def get_message_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get formatted message history for the agent"""
        messages = await self.message_repo.get_by_session_id(self.db, session_id)
        formatted_messages = []
        for msg in messages:
            formatted_msg = self.message_repo.to_pydantic_message(msg)
            formatted_messages.append(formatted_msg)
        
        print(f"  📊 Retrieved and formatted {len(formatted_messages)} messages")
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