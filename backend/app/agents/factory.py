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
    async def get_agent(cls, conversation_type: str = "journaling", user_id: str = None) -> Agent:
        """Get or create agent for conversation type"""
        return await cls._create_agent(conversation_type, user_id)
    
    @classmethod
    async def _create_agent(cls, conversation_type: str, user_id: str = None) -> Agent:
        """Create new agent instance"""
        # Set environment variable for Anthropic API key
        api_key = get_anthropic_api_key()
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        
        # Initialize Anthropic model
        print(f"[DEBUG] Initializing AnthropicModel with {settings.ANTHROPIC_DEFAULT_MODEL}")
        model = AnthropicModel(settings.ANTHROPIC_DEFAULT_MODEL)
        print("[DEBUG] AnthropicModel initialized successfully")
        
        # Get tools for this conversation type
        tools = get_tools_for_conversation_type(conversation_type)
        print(f"Created agent with {len(tools)} tools for conversation type: {conversation_type}")
        print(f"Tools: {[tool.function.__name__ if hasattr(tool, 'function') else str(tool) for tool in tools]}")
        
        # Get system prompt with user_id
        system_prompt = cls._get_system_prompt(conversation_type, user_id)
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
    def _get_system_prompt(cls, conversation_type: str, user_id: str = None) -> str:
        """Get system prompt for conversation type"""
        if conversation_type == "journaling":
            user_id_param = f'"user_id": "{user_id}"' if user_id else ''
            user_id_example = f', "user_id": "{user_id}"' if user_id else ''
            
            return f"""You are Cassidy, a journaling assistant. You MUST call tools for all user input.

MANDATORY TOOL USAGE - ALWAYS call the appropriate tool first:

1. PREFERENCES: When user mentions goals, aspirations, or preferences → Call update_preferences_tool
   - "I want..." (aspirational) → update_preferences_tool(preference_updates={{"user_text": "[full user text]"{user_id_example}}})
   - "My goal..." → update_preferences_tool(preference_updates={{"user_text": "[full user text]"{user_id_example}}})
   - "I hope..." → update_preferences_tool(preference_updates={{"user_text": "[full user text]"{user_id_example}}})

2. JOURNALING: When user shares experiences, activities, thoughts, or feelings → Call structure_journal_tool  
   - "I went to..." → structure_journal_tool(user_text="I went to...")
   - "I did..." → structure_journal_tool(user_text="I did...")
   - "I feel..." → structure_journal_tool(user_text="I feel...")
   - Daily activities, experiences, emotions → structure_journal_tool

3. SAVING: When user wants to save → Call save_journal_tool
   - "save it" / "save" / "finalize" → save_journal_tool(confirmation=True)

CRITICAL RULES:
- ALWAYS call a tool first, never ask for more information
- For aspirational statements ("I want to..."), use update_preferences_tool
- For activity/experience statements ("I went to..."), use structure_journal_tool

Examples:
- "I want to go to the moon" → update_preferences_tool(preference_updates={{"user_text": "I want to go to the moon"{user_id_example}}})
- "I went to the park" → structure_journal_tool(user_text="I went to the park")
- "add a journal entry to say that i went to the park" → structure_journal_tool(user_text="I went to the park")
- "save it" → save_journal_tool(confirmation=True)"""

        elif conversation_type == "general":
            return """You are Cassidy, a helpful AI assistant. Provide clear, helpful responses to user questions and requests."""
        
        else:
            return """You are Cassidy, a helpful AI assistant."""