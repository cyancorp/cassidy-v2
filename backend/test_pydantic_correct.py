#!/usr/bin/env python3
"""
Correct way to use pydantic-ai context based on documentation.
Tools should receive RunContext[DepsType], not deps directly.
"""

import asyncio
import os
from dataclasses import dataclass
from pydantic_ai import Agent, Tool, RunContext
from pydantic_ai.models.anthropic import AnthropicModel
import pydantic_ai

@dataclass
class TestContext:
    user_id: str
    secret_number: int
    is_admin: bool

# CORRECT: Tool receives RunContext[TestContext], not TestContext directly
async def test_tool(ctx: RunContext[TestContext], input_text: str) -> str:
    """Tool that correctly accesses context via ctx.deps"""
    print(f"🔍 TOOL RECEIVED:")
    print(f"   ctx.deps.user_id = '{ctx.deps.user_id}' (type: {type(ctx.deps.user_id)})")
    print(f"   ctx.deps.secret_number = {ctx.deps.secret_number} (type: {type(ctx.deps.secret_number)})")
    print(f"   ctx.deps.is_admin = {ctx.deps.is_admin} (type: {type(ctx.deps.is_admin)})")
    print(f"   input_text = '{input_text}'")
    
    return f"Tool got user_id='{ctx.deps.user_id}', secret={ctx.deps.secret_number}, admin={ctx.deps.is_admin}"

async def main():
    print(f"🔍 pydantic-ai version: {pydantic_ai.__version__}")
    print()
    
    # Set up API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not set")
        return

    # Create the context we want to pass
    original_context = TestContext(
        user_id="real-user-123",
        secret_number=42,
        is_admin=True
    )
    
    print("📤 SENDING TO AGENT:")
    print(f"   user_id = '{original_context.user_id}'")
    print(f"   secret_number = {original_context.secret_number}")
    print(f"   is_admin = {original_context.is_admin}")
    print()

    # Create agent with our tool
    agent = Agent(
        model=AnthropicModel("claude-3-5-sonnet-20241022"),
        tools=[
            Tool(test_tool, description="A test tool that shows context")
        ],
        system_prompt="You are a test assistant. When user sends any message, call test_tool with their message.",
        deps_type=TestContext
    )

    # Run the agent with our context
    print("🤖 CALLING AGENT...")
    result = await agent.run(
        "test message", 
        deps=original_context
    )
    
    print()
    print("📤 AGENT RESPONSE:")
    print(f"   {result.output}")
    
    print()
    print("✅ SUCCESS: Tool should receive the exact context values!")

if __name__ == "__main__":
    asyncio.run(main())