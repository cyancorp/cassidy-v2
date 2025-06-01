from typing import Optional, Dict
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
import os

from app.agents.models import CassidyAgentDependencies
from app.agents.tools import get_tools_for_conversation_type
from app.core.config import settings


class AgentFactory:
    """Factory for creating and managing AI agents"""
    
    _agents: Dict[str, Agent] = {}
    
    @classmethod
    async def get_agent(cls, conversation_type: str = "journaling", user_id: str = None) -> Agent:
        """Get or create agent for conversation type"""
        # Temporarily disable caching to debug the issue
        return await cls._create_agent(conversation_type, user_id)
    
    @classmethod
    async def _create_agent(cls, conversation_type: str, user_id: str = None) -> Agent:
        """Create new agent instance"""
        # Set environment variable for Anthropic API key
        if settings.ANTHROPIC_API_KEY:
            os.environ["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY
        
        # Initialize Anthropic model
        model = AnthropicModel(settings.ANTHROPIC_DEFAULT_MODEL)
        
        # Get tools for this conversation type
        tools = get_tools_for_conversation_type(conversation_type)
        print(f"Created agent with {len(tools)} tools for conversation type: {conversation_type}")
        print(f"Tools: {[tool.function.__name__ if hasattr(tool, 'function') else str(tool) for tool in tools]}")
        
        # Validate tools before passing to agent
        for i, tool in enumerate(tools):
            print(f"Tool {i}: {type(tool)}, function: {getattr(tool, 'function', None)}")
            if hasattr(tool, 'function'):
                print(f"  Function name: {tool.function.__name__}")
            if hasattr(tool, 'description'):
                print(f"  Description: {tool.description}")
        
        # Get system prompt with user_id
        system_prompt = cls._get_system_prompt(conversation_type, user_id)
        
        # Create agent
        print(f"Creating agent with system prompt: {system_prompt[:100]}...")
        print(f"Tools being registered: {[getattr(tool, 'function', tool).__name__ if hasattr(tool, 'function') else str(tool) for tool in tools]}")
        
        try:
            agent = Agent(
                model=model,
                tools=tools,
                system_prompt=system_prompt,
                deps_type=CassidyAgentDependencies
            )
            print(f"Agent created successfully!")
            
            # Check agent attributes after creation
            agent_attrs = [attr for attr in dir(agent) if not attr.startswith('__')]
            print(f"Agent attributes: {agent_attrs[:10]}...")  # Show first 10 attrs
            
        except Exception as e:
            print(f"Error creating agent: {e}")
            print(f"Error type: {type(e)}")
            raise
        
        return agent
    
    @classmethod
    def _get_system_prompt(cls, conversation_type: str, user_id: str = None) -> str:
        """Get system prompt for conversation type"""
        if conversation_type == "journaling":
            user_id_param = f'"user_id": "{user_id}"' if user_id else ''
            user_id_example = f', "user_id": "{user_id}"' if user_id else ''
            
            return f"""You are Cassidy, a journaling assistant. You MUST call tools for all user input.

CRITICAL: For ANY input that mentions goals, aspirations, or desires, immediately call update_preferences_tool first.

TOOL USAGE RULES:
1. "I want..." → ALWAYS call update_preferences_tool(preference_updates={{"user_text": "[full user text]"{user_id_example}}})
2. "My goal..." → ALWAYS call update_preferences_tool(preference_updates={{"user_text": "[full user text]"{user_id_example}}})  
3. "I hope..." → ALWAYS call update_preferences_tool(preference_updates={{"user_text": "[full user text]"{user_id_example}}})
4. Any aspirational statement → ALWAYS call update_preferences_tool FIRST

NEVER ask for more information. ALWAYS extract and save the preference immediately.

Examples of CORRECT behavior:
- User: "i want to go to the moon" 
- You: Call update_preferences_tool(preference_updates={{"user_text": "i want to go to the moon"{user_id_example}}}) FIRST
- Then respond: "Great! I've saved your goal to go to the moon."

- User: "I want to be a better trader"
- You: Call update_preferences_tool(preference_updates={{"user_text": "I want to be a better trader"{user_id_example}}}) FIRST  
- Then respond: "Excellent! I've saved your goal to be a better trader."

NEVER say "I need more information" - just save the goal and respond positively."""

        elif conversation_type == "general":
            return """You are Cassidy, a helpful AI assistant. Provide clear, helpful responses to user questions and requests."""
        
        else:
            return """You are Cassidy, a helpful AI assistant."""