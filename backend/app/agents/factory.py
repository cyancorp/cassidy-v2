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
            print(f"[DEBUG] API key set, length: {len(api_key)}")
        else:
            print("[ERROR] No Anthropic API key found!")
        
        # Initialize Anthropic model
        print(f"[DEBUG] Initializing AnthropicModel with {settings.ANTHROPIC_DEFAULT_MODEL}")
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
                print(f"[DEBUG] AgentFactory: Built tasks context with {len(context.current_tasks)} tasks")
            else:
                tasks_context = "\n\nCURRENT TASKS: None\n"
                print(f"[DEBUG] AgentFactory: No tasks in context - context: {context}, has current_tasks: {hasattr(context, 'current_tasks') if context else False}")
            
            return f"""You are Cassidy, a journaling and task assistant. You MUST call tools for all user input.

{tasks_context}
MANDATORY TOOL USAGE - ALWAYS call the appropriate tool first:

1. TASK MANAGEMENT:
   - "I need to [do something]" / "add task" → create_task_agent_tool(title="[task]", description="...", due_date="YYYY-MM-DD")
   - "I bought milk" / "I completed [task]" → complete_task_by_title_agent_tool(task_title="milk")
   - "I got a cat" → complete_task_by_title_agent_tool(task_title="cat")
   - "delete task" / "remove task" → delete_task_agent_tool(task_id="[exact ID from CURRENT TASKS list]")
   - "show my tasks" / "list tasks" → list_tasks_agent_tool(include_completed=False)
   - Recognize task mentions in journal entries and create tasks automatically
   
   IMPORTANT: Use complete_task_by_title_agent_tool when user says they completed something!

2. PREFERENCES: Goals, aspirations, or preferences → update_preferences_tool
   - "I want..." (aspirational) → update_preferences_tool(preference_updates={{"user_text": "[full user text]"{user_id_example}}})
   - "My goal..." → update_preferences_tool(preference_updates={{"user_text": "[full user text]"{user_id_example}}})

3. JOURNALING: Experiences, activities, thoughts, feelings → structure_journal_tool  
   - "I went to..." → structure_journal_tool(user_text="I went to...")
   - "I did..." → structure_journal_tool(user_text="I did...")
   - "I feel..." → structure_journal_tool(user_text="I feel...")
   - If user mentions tasks while journaling, ALSO call create_task_agent_tool

4. SAVING: When user wants to save → save_journal_tool(confirmation=True)

CRITICAL RULES:
- ALWAYS call appropriate tool first, never ask for more information
- For task completion, match user intent to EXACT task ID from the list above
- When journaling mentions tasks ("need to", "should", "must"), create tasks AND journal
- Be context-aware: if user says "I bought milk" and milk task exists, complete it
- TASK MATCHING: When user says they completed something, find the matching task from the current list and use its exact ID

TASK COMPLETION MATCHING:
- When user says they completed something, use complete_task_by_title_agent_tool
- Extract what they completed and pass it as the task_title parameter

Examples:
- "I bought a cat" → complete_task_by_title_agent_tool(task_title="cat")
- "I got milk" → complete_task_by_title_agent_tool(task_title="milk")
- "finished the report" → complete_task_by_title_agent_tool(task_title="report")
- "I bought cigars" → complete_task_by_title_agent_tool(task_title="cigars")

More Examples:
- "I need to buy milk" → create_task_agent_tool(title="Buy milk", description=None, due_date=None)
- "I bought milk" → complete_task_by_title_agent_tool(task_title="milk")
- "I went to the store and need to call mom later" → structure_journal_tool + create_task_agent_tool
- "My goal is to exercise daily" → update_preferences_tool(preference_updates={{"user_text": "My goal is to exercise daily"{user_id_example}}})"""

        elif conversation_type == "general":
            return """You are Cassidy, a helpful AI assistant. Provide clear, helpful responses to user questions and requests."""
        
        else:
            return """You are Cassidy, a helpful AI assistant."""