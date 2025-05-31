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
    async def get_agent(cls, conversation_type: str = "journaling") -> Agent:
        """Get or create agent for conversation type"""
        # Temporarily disable caching to debug the issue
        return await cls._create_agent(conversation_type)
    
    @classmethod
    async def _create_agent(cls, conversation_type: str) -> Agent:
        """Create new agent instance"""
        # Set environment variable for Anthropic API key
        os.environ["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY
        
        # Initialize Anthropic model
        model = AnthropicModel(settings.ANTHROPIC_DEFAULT_MODEL)
        
        # Get tools for this conversation type
        tools = get_tools_for_conversation_type(conversation_type)
        print(f"Created agent with {len(tools)} tools for conversation type: {conversation_type}")
        print(f"Tools: {[tool.function.__name__ if hasattr(tool, 'function') else str(tool) for tool in tools]}")
        
        # Get system prompt
        system_prompt = cls._get_system_prompt(conversation_type)
        
        # Create agent
        print(f"Creating agent with system prompt: {system_prompt[:100]}...")
        print(f"Tools being registered: {[getattr(tool, 'function', tool).__name__ if hasattr(tool, 'function') else str(tool) for tool in tools]}")
        
        agent = Agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            deps_type=CassidyAgentDependencies
        )
        
        print(f"Agent created successfully. Agent tools attribute: {hasattr(agent, 'tools')}")
        if hasattr(agent, 'tools'):
            print(f"Agent tools count: {len(agent.tools) if agent.tools else 0}")
        
        return agent
    
    @classmethod
    def _get_system_prompt(cls, conversation_type: str) -> str:
        """Get system prompt for conversation type"""
        if conversation_type == "journaling":
            return """You are Cassidy, a journaling assistant. You MUST call tools for all journaling requests.

MANDATORY TOOL USAGE:
- When user wants to journal (any content about thoughts/feelings): Call structure_journal_tool
- When user wants to save: Call save_journal_tool

For ANY journaling content, ALWAYS call structure_journal_tool first with the user's text as user_text parameter.

Examples:
- "hi i want to create a journal entry" → No content yet, ask for content
- "i am sad because market is down" → Call structure_journal_tool(user_text="i am sad because market is down")
- "save it" / "save the journal" / "please save" / "finalize it" → Call save_journal_tool(confirmation=True)

You have these tools available:
1. structure_journal_tool - Use when user shares thoughts/feelings/experiences
2. save_journal_tool - Use when user wants to save
3. update_preferences_tool - Use when updating user preferences

Always call the appropriate tool first, then provide a supportive response."""

        elif conversation_type == "general":
            return """You are Cassidy, a helpful AI assistant. Provide clear, helpful responses to user questions and requests."""
        
        else:
            return """You are Cassidy, a helpful AI assistant."""