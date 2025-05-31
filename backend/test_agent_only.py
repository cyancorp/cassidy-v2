#!/usr/bin/env python3
"""Test agent creation and tool registration"""
import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_agent_creation():
    """Test agent creation directly"""
    
    print("🚀 Testing agent creation...")
    
    try:
        from app.agents.factory import AgentFactory
        from app.agents.models import CassidyAgentDependencies
        print("✅ Imports successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    try:
        # Create agent
        print("Creating journaling agent...")
        agent = await AgentFactory.get_agent("journaling")
        print(f"✅ Agent created: {type(agent)}")
        
        # Check if agent has tools
        print(f"Agent has tools attribute: {hasattr(agent, 'tools')}")
        if hasattr(agent, 'tools'):
            print(f"Number of tools: {len(agent.tools) if agent.tools else 0}")
            if agent.tools:
                for i, tool in enumerate(agent.tools):
                    print(f"  Tool {i}: {type(tool)} - {getattr(tool, 'function', tool).__name__ if hasattr(tool, 'function') else tool}")
        
        # Create context
        context = CassidyAgentDependencies(
            user_id="test-user",
            session_id="test-session", 
            conversation_type="journaling",
            user_template={
                "name": "Test Template",
                "sections": {
                    "Thoughts & Feelings": {
                        "description": "Emotional state, mood, thoughts, and internal experiences",
                        "aliases": ["Emotions", "Mood", "Feelings", "Thoughts"]
                    }
                }
            },
            user_preferences={"preferred_feedback_style": "supportive"},
            current_journal_draft={}
        )
        
        print("✅ Context created")
        
        # Try a simple run
        print("Testing agent run...")
        result = await agent.run("i am sad because the market is down", deps=context)
        print(f"✅ Agent run successful")
        print(f"Result type: {type(result)}")
        print(f"Result data: {getattr(result, 'data', 'No data attr')[:100] if hasattr(result, 'data') else 'No data attr'}")
        
        # Check for tool calls
        print(f"Result attributes: {[attr for attr in dir(result) if not attr.startswith('_')]}")
        
        if hasattr(result, 'all_tool_calls'):
            tool_calls = result.all_tool_calls()
            print(f"Tool calls via all_tool_calls: {len(tool_calls)}")
            for call in tool_calls:
                print(f"  - {call}")
        else:
            print("No all_tool_calls method")
            
        if hasattr(result, 'tool_calls'):
            print(f"Tool calls via tool_calls: {result.tool_calls}")
            
        if hasattr(result, 'usage'):
            print(f"Usage: {result.usage}")
            
        if hasattr(result, 'output'):
            print(f"Output: {result.output[:100]}...")
            
        if hasattr(result, 'all_messages'):
            print(f"All messages: {len(result.all_messages())}")
            for i, msg in enumerate(result.all_messages()):
                print(f"  Message {i}: {type(msg)} - {str(msg)[:100]}...")
                
        if hasattr(result, 'new_messages'):
            print(f"New messages: {len(result.new_messages())}")
            for i, msg in enumerate(result.new_messages()):
                print(f"  New message {i}: {type(msg)} - {str(msg)[:100]}...")
                if hasattr(msg, 'tool_call'):
                    print(f"    Tool call: {msg.tool_call}")
                if hasattr(msg, 'content'):
                    print(f"    Content: {msg.content}")
            
    except Exception as e:
        print(f"❌ Agent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    print("🎉 Agent creation test completed!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_agent_creation())
    if not success:
        sys.exit(1)