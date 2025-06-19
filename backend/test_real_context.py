#!/usr/bin/env python3
"""Test script that exactly replicates our main app agent setup"""

import asyncio
import os
from dataclasses import dataclass
from typing import Dict, Any, List
from pydantic_ai import Agent, Tool
from pydantic_ai.models.anthropic import AnthropicModel

# Import our actual models and tools
from app.agents.models import CassidyAgentDependencies
from app.agents.tools import (
    complete_task_agent_tool, 
    list_tasks_agent_tool,
    create_task_agent_tool,
    complete_task_by_title_agent_tool
)

async def main():
    print("=== Testing Real App Context ===\n")
    
    # Create context that matches our app exactly
    context = CassidyAgentDependencies(
        user_id="291c429e-7da5-4fc7-8460-b933f3ec582a",
        session_id="test-session-123",
        conversation_type="journaling",
        user_template={},
        user_preferences={},
        current_journal_draft={},
        current_tasks=[
            {
                "id": "5e7b9123-c352-42f2-b83c-24e384472da1",
                "title": "Buy milk",
                "description": None,
                "priority": 3,
                "due_date": None,
                "created_at": "2025-06-19T15:13:27.551714"
            },
            {
                "id": "c254f1ab-05db-4b28-b0de-465b8cefcaf6", 
                "title": "Buy a cat",
                "description": None,
                "priority": 1,
                "due_date": None,
                "created_at": "2025-06-19T14:23:16.718942"
            }
        ]
    )
    
    # Build system prompt exactly like our app
    tasks_context = "\n\nCURRENT TASKS (Priority Order):\n"
    for i, task in enumerate(context.current_tasks, 1):
        due_info = f" (due {task['due_date']})" if task.get('due_date') else ""
        tasks_context += f"{i}. {task['title']}{due_info} [ID: {task['id']}]\n"
    tasks_context += "\nUSE THESE TASK IDs when completing/updating tasks!\n"
    
    system_prompt = f"""You are Cassidy, a journaling and task assistant. You MUST call tools for all user input.

{tasks_context}

MANDATORY TOOL USAGE - ALWAYS call the appropriate tool first:

1. TASK MANAGEMENT:
   - "I need to [do something]" / "add task" → create_task_agent_tool(title="[task]", description="...", due_date="YYYY-MM-DD")
   - "I bought milk" / "I completed [task]" → complete_task_by_title_agent_tool(task_title="milk")
   - "I got a cat" → complete_task_by_title_agent_tool(task_title="cat")
   - "show my tasks" / "list tasks" → list_tasks_agent_tool(include_completed=False)

TASK COMPLETION MATCHING:
- When user says they completed something, use complete_task_by_title_agent_tool
- Extract what they completed and pass it as the task_title parameter

Examples:
- "I bought a cat" → complete_task_by_title_agent_tool(task_title="cat")
- "I got milk" → complete_task_by_title_agent_tool(task_title="milk")
- "finished the report" → complete_task_by_title_agent_tool(task_title="report")
- "I bought cigars" → complete_task_by_title_agent_tool(task_title="cigars")"""

    print(f"System Prompt:\n{system_prompt}\n")
    print("=" * 80)
    
    # Create agent exactly like our app
    api_key = os.getenv("ANTHROPIC_API_KEY") 
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return
        
    print(f"[DEBUG] Using model: claude-sonnet-4-20250514")
    print(f"[DEBUG] Context user_id: {context.user_id}")
    print(f"[DEBUG] Context current_tasks: {len(context.current_tasks)} tasks")
    for task in context.current_tasks:
        print(f"  - {task['title']} [ID: {task['id']}]")
    
    agent = Agent(
        model=AnthropicModel("claude-sonnet-4-20250514"),
        tools=[
            Tool(list_tasks_agent_tool, description="List the user's current tasks"),
            Tool(complete_task_by_title_agent_tool, description="Complete a task by matching the task title"),
            Tool(complete_task_agent_tool, description="Complete a task by exact ID"),
            Tool(create_task_agent_tool, description="Create a new task")
        ],
        system_prompt=system_prompt,
        deps_type=CassidyAgentDependencies
    )
    
    # Test the same messages that are failing
    test_messages = [
        "show my tasks",
        "i bought milk"
    ]
    
    for msg in test_messages:
        print(f"\n{'='*20} User: {msg} {'='*20}")
        try:
            result = await agent.run(msg, deps=context)
            print(f"Agent Response: {result.output}")
            
            # Show tool calls if any
            if hasattr(result, 'new_messages'):
                for message in result.new_messages():
                    if hasattr(message, 'parts'):
                        for part in message.parts:
                            if hasattr(part, 'tool_name'):
                                print(f"\nTool Called: {part.tool_name}")
                                if hasattr(part, 'args'):
                                    print(f"Tool Args: {part.args}")
                                    
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())