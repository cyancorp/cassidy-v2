from typing import Optional, Dict
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
import os

from app.agents.models import CassidyAgentDependencies
from app.agents.tools import get_tools_for_conversation_type
from app.core.config import settings, get_anthropic_api_key


class AgentFactory:
    """Factory for creating and managing AI agents"""
    
    _agents: Dict[str, Agent] = {}
    
    @classmethod
    async def get_agent(cls, conversation_type: str = "journaling", user_id: str = None, context: CassidyAgentDependencies = None) -> Agent:
        """Get or create agent for conversation type"""
        return await cls._create_agent(conversation_type, user_id, context)
    
    @classmethod
    async def _create_agent(cls, conversation_type: str, user_id: str = None, context: CassidyAgentDependencies = None) -> Agent:
        """Create new agent instance"""
        # Set environment variable for Anthropic API key
        api_key = get_anthropic_api_key()
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        else:
            print("[ERROR] No Anthropic API key found!")
        
        # Initialize Anthropic model
        try:
            model = AnthropicModel(settings.ANTHROPIC_DEFAULT_MODEL)
            print("[DEBUG] AnthropicModel initialized successfully")
        except Exception as e:
            print(f"[ERROR] Failed to initialize AnthropicModel: {e}")
            raise
        
        # Get tools for this conversation type
        tools = get_tools_for_conversation_type(conversation_type)
        print(f"Created agent with {len(tools)} tools for conversation type: {conversation_type}")
        print(f"Tools: {[tool.function.__name__ if hasattr(tool, 'function') else str(tool) for tool in tools]}")
        
        # Get system prompt with context
        system_prompt = cls._get_system_prompt(conversation_type, user_id, context)
        print(f"Creating agent with system prompt: {system_prompt[:200]}...")
        
        # Create agent
        agent = Agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            deps_type=CassidyAgentDependencies
        )
        
        return agent
    
    @classmethod
    def _get_system_prompt(cls, conversation_type: str, user_id: str = None, context: CassidyAgentDependencies = None) -> str:
        """Get system prompt for conversation type"""
        if conversation_type == "journaling":
            user_id_example = f', "user_id": "{user_id}"' if user_id else ''
            
            # Build current tasks context
            tasks_context = ""
            if context and context.current_tasks:
                tasks_context = "\n\nCURRENT TASKS (Priority Order):\n"
                for i, task in enumerate(context.current_tasks, 1):
                    due_info = f" (due {task['due_date']})" if task.get('due_date') else ""
                    tasks_context += f"{i}. {task['title']}{due_info} [ID: {task['id']}]\n"
                tasks_context += "\nUSE THESE TASK IDs when completing/updating tasks!\n"
            else:
                tasks_context = "\n\nCURRENT TASKS: None\n"
            
            return f"""You are Prism, a journaling and task assistant. Always call appropriate tools for user input.
{tasks_context}
RULES:
- Call tools immediately, don't ask for clarification
- For "I completed X" → use complete_task_by_title_agent_tool
- For "I need to X" → use create_task_agent_tool  
- For experiences/feelings → use structure_journal_tool then save_journal_tool
- When processing journal entries: FIRST call structure_journal_tool, THEN call save_journal_tool
- Focus on journal structuring first, task creation second
- Use exact task IDs from current tasks list for deletions/updates"""

        elif conversation_type == "general":
            return """You are Prism, a helpful AI assistant. Provide clear, helpful responses to user questions and requests."""
        
        else:
            return """You are Prism, a helpful AI assistant."""