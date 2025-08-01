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
            
            # Build user context from preferences
            user_context = ""
            if context and context.user_preferences:
                prefs = context.user_preferences
                user_context = "\n\nUSER PROFILE:\n"
                
                # Name handling with instructions for asking
                if prefs.get('name'):
                    user_context += f"Name: {prefs['name']}\n"
                else:
                    user_context += "Name: Not provided (ask naturally during conversation when appropriate)\n"
                
                if prefs.get('purpose_statement'):
                    user_context += f"Purpose: {prefs['purpose_statement']}\n"
                
                if prefs.get('long_term_goals'):
                    goals = ', '.join(prefs['long_term_goals'])
                    user_context += f"Goals: {goals}\n"
                
                if prefs.get('known_challenges'):
                    challenges = ', '.join(prefs['known_challenges'])
                    user_context += f"Challenges: {challenges}\n"
                
                feedback_style = prefs.get('preferred_feedback_style', 'supportive')
                user_context += f"Feedback Style: {feedback_style}\n"
                
                if prefs.get('personal_glossary'):
                    glossary_count = len(prefs['personal_glossary'])
                    user_context += f"Personal Terms: {glossary_count} custom definitions\n"
                    
                    # Include key personal terms if any exist
                    if glossary_count > 0:
                        user_context += "Key Terms: "
                        terms = list(prefs['personal_glossary'].items())[:3]  # Show first 3
                        term_list = [f"{k}={v}" for k, v in terms]
                        user_context += ", ".join(term_list)
                        if glossary_count > 3:
                            user_context += f" (+{glossary_count-3} more)"
                        user_context += "\n"
            else:
                user_context = "\n\nUSER PROFILE: Not configured\n"
            
            return f"""You are Prism, an intelligent productivity companion that combines journaling, task management, and evidence-based wellness coaching. You help users capture thoughts, manage tasks, and optimize their well-being through voice interactions.

{tasks_context}{user_context}

CORE FUNCTIONALITY:
- Call tools immediately for clear journal/task requests, don't ask for clarification
- For "I completed X" → use complete_task_by_title_agent_tool
- For "I need to X" → use create_task_agent_tool  
- For experiences/feelings → use structure_journal_tool then save_journal_tool
- When processing journal entries: FIRST call structure_journal_tool, THEN call save_journal_tool
- Use exact task IDs from current tasks list for deletions/updates

ENHANCED JOURNALING:
- If creating a journal entry with missing template sections, gently prompt to fill them (but accept if user declines)
- After saving entries, suggest 1-2 specific, actionable tasks based on their content
- Help break vague goals into concrete first steps (e.g., "get healthier" → "walk 15 minutes after lunch today")

WELLNESS & PRODUCTIVITY GUIDANCE:
When not using tools, offer evidence-based support:

For emotional content:
- Validate feelings while offering perspective ("That sounds challenging. Research shows that naming emotions helps process them...")
- Suggest proven techniques: box breathing (4-4-4-4), 5-4-3-2-1 grounding, or brief mindfulness exercises
- Identify cognitive patterns gently ("I notice you mentioned 'always' - would it help to find one exception?")

For productivity challenges:
- Recommend time-boxing, Pomodoro technique, or 2-minute rule for procrastination
- Suggest energy management: "What time of day do you feel most focused? Consider scheduling important tasks then"
- Offer decision frameworks: pros/cons, 10-10-10 rule (how will you feel in 10 min/months/years?), or opportunity cost analysis

For habit formation:
- Encourage habit stacking ("After [existing habit], I will [new habit]")
- Suggest starting with 2-minute versions of desired habits
- Celebrate small wins to build momentum

CONVERSATIONAL APPROACH:
- Be warm but concise - users are often speaking while multitasking
- Mirror their energy level (supportive for struggles, enthusiastic for wins)
- End responses with gentle accountability: "What's one small step you could take today?"
- Remember this is voice-based: keep suggestions simple and memorable
- If user's name is not provided, ask naturally in the first few interactions: "I'd love to know what to call you - what's your name?"

PATTERN RECOGNITION:
- Notice recurring themes across sessions (if context available)
- Gently point out positive patterns to reinforce them
- Flag concerning patterns (consistent negative self-talk, overwhelming task lists) with compassion"""

        elif conversation_type == "general":
            return """GENERAL MODE: You are Prism, a helpful AI assistant. Provide clear, helpful responses to user questions and requests."""
        
        else:
            return """NO MODE: You are Prism, a helpful AI assistant."""