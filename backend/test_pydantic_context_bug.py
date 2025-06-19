#!/usr/bin/env python3
"""
Minimal test to demonstrate pydantic-ai context passing bug.

Expected behavior: Tool should receive the exact context we pass to agent.run()
Actual behavior: Tool receives corrupted/different context values

This is a reproducible bug in pydantic-ai where the deps parameter
passed to agent.run() is not correctly forwarded to tools.
"""

import asyncio
import os
from dataclasses import dataclass
from pydantic_ai import Agent, Tool
from pydantic_ai.models.anthropic import AnthropicModel
import pydantic_ai

@dataclass
class TestContext:
    user_id: str
    secret_number: int
    is_admin: bool

async def test_tool(ctx: TestContext, input_text: str) -> str:
    """Simple tool that shows what context it receives"""
    print(f"🔍 TOOL RECEIVED:")
    print(f"   ctx.user_id = '{ctx.user_id}' (type: {type(ctx.user_id)})")
    print(f"   ctx.secret_number = {ctx.secret_number} (type: {type(ctx.secret_number)})")
    print(f"   ctx.is_admin = {ctx.is_admin} (type: {type(ctx.is_admin)})")
    print(f"   input_text = '{input_text}'")
    
    return f"Tool got user_id='{ctx.user_id}', secret={ctx.secret_number}, admin={ctx.is_admin}"

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
    print("🔍 EXPECTED: Tool should receive user_id='real-user-123', secret_number=42, is_admin=True")
    print("❓ QUESTION: Did the tool receive the correct context values?")

if __name__ == "__main__":
    asyncio.run(main())