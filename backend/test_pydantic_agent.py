#!/usr/bin/env python3
"""Test script to debug pydantic-ai agent tool parameter passing"""

import asyncio
from typing import Dict, Any
from dataclasses import dataclass
from pydantic_ai import Agent, Tool
from pydantic_ai.models.anthropic import AnthropicModel
import os

# Set up Anthropic model
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY not set")
    exit(1)

@dataclass
class TestContext:
    """Test context with user data"""
    user_id: str
    current_tasks: list[Dict[str, Any]]

# Define test tools
async def complete_task_tool(ctx: TestContext, task_id: str) -> Dict[str, Any]:
    """Complete a task by ID"""
    print(f"[TOOL CALLED] complete_task_tool")
    print(f"  - ctx.user_id: {ctx.user_id}")
    print(f"  - task_id: {task_id}")
    print(f"  - current_tasks: {ctx.current_tasks}")
    
    # Find the task
    for task in ctx.current_tasks:
        if task['id'] == task_id:
            task_name = task.get('title', task.get('description', 'Unknown Task'))
            return {
                "success": True,
                "message": f"Completed task: {task_name}"
            }
    
    return {
        "success": False,
        "message": f"Task {task_id} not found"
    }

async def list_tasks_tool(ctx: TestContext) -> Dict[str, Any]:
    """List all tasks"""
    print(f"[TOOL CALLED] list_tasks_tool")
    print(f"  - ctx.user_id: {ctx.user_id}")
    print(f"  - tasks count: {len(ctx.current_tasks)}")
    
    return {
        "success": True,
        "tasks": ctx.current_tasks,
        "count": len(ctx.current_tasks)
    }

async def main():
    print("=== Testing Pydantic-AI Agent Tool Parameter Passing ===\n")
    
    # Create context with test data
    context = TestContext(
        user_id="test-user-123",
        current_tasks=[
            {"id": "task-001", "title": "Buy milk"},
            {"id": "task-002", "title": "Buy a cat"},
            {"id": "task-003", "title": "Buy cigars"}
        ]
    )
    
    # Build system prompt with task list
    tasks_prompt = "\n".join([
        f"{i+1}. {task['title']} [ID: {task['id']}]"
        for i, task in enumerate(context.current_tasks)
    ])
    
    system_prompt = f"""You are a task assistant. You help users manage their tasks.

CURRENT TASKS:
{tasks_prompt}

When a user says they completed something:
1. Find the matching task from the list above
2. Extract the exact task ID
3. Call complete_task_tool with that task_id

Examples:
- "I bought milk" → complete_task_tool(task_id="task-001")
- "I got the cat" → complete_task_tool(task_id="task-002")
"""

    print(f"System Prompt:\n{system_prompt}\n")
    print("=" * 50)
    
    # Create agent with tools
    agent = Agent(
        model=AnthropicModel("claude-3-5-sonnet-20241022"),
        tools=[
            Tool(complete_task_tool, description="Complete a task by providing its ID"),
            Tool(list_tasks_tool, description="List all tasks")
        ],
        system_prompt=system_prompt,
        deps_type=TestContext
    )
    
    # Test cases
    test_messages = [
        "show me my tasks",
        "I bought milk",
        "I got the cat",
        "complete task task-003"
    ]
    
    for msg in test_messages:
        print(f"\n--- User: {msg} ---")
        try:
            # Run agent with context
            result = await agent.run(msg, deps=context)
            print(f"Agent Response: {result.output}")
            
            # Check if tools were called
            if hasattr(result, 'new_messages'):
                for message in result.new_messages():
                    if hasattr(message, 'parts'):
                        for part in message.parts:
                            if hasattr(part, 'tool_name'):
                                print(f"Tool Called: {part.tool_name}")
                                if hasattr(part, 'args'):
                                    print(f"Tool Args: {part.args}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())