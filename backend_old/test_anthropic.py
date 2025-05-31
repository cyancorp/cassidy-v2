import asyncio
import os
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from dotenv import load_dotenv
import sys # Import sys

print(f"[test_anthropic.py] id(Agent): {id(Agent)}") # Log ID of Agent class
print(f"[test_anthropic.py] Agent.__module__: {Agent.__module__}")
if Agent.__module__ in sys.modules:
    print(f"[test_anthropic.py] Agent module file: {sys.modules[Agent.__module__].__file__}")

# It's good practice to load .env variables for a standalone script
# Assuming your .env is in the project root (one level above backend)
dotenv_path = os.path.join(os.path.dirname(__file__), '../.env')
load_dotenv(dotenv_path=dotenv_path)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# Use the same model name as in our main app settings
ANTHROPIC_MODEL_NAME = os.getenv("ANTHROPIC_DEFAULT_MODEL", "claude-3-7-sonnet-latest") 

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not found in environment variables or .env file.")
    exit(1)

print(f"Using Anthropic Model: {ANTHROPIC_MODEL_NAME}")
print(f"Anthropic API Key (first 5 chars): {ANTHROPIC_API_KEY[:5]}...")

# 1. Initialize the AnthropicModel
try:
    # First, create and inspect the provider
    print("\n--- AnthropicProvider Inspection (test_anthropic.py) ---")
    anthropic_provider_instance = AnthropicProvider(api_key=ANTHROPIC_API_KEY)
    print(f"Provider instance: {anthropic_provider_instance}")
    print(f"Provider __dict__: {anthropic_provider_instance.__dict__}")
    try:
        api_key_on_provider = anthropic_provider_instance.api_key
        print(f"Accessed provider.api_key: {api_key_on_provider}") # Should fail
    except AttributeError:
        print("AttributeError when accessing provider.api_key (as expected based on source).")
    print("--- End AnthropicProvider Inspection (test_anthropic.py) ---")

    model = AnthropicModel(
        ANTHROPIC_MODEL_NAME,
        provider=anthropic_provider_instance # Use the inspected instance
    )
    print("AnthropicModel initialized successfully.")
except Exception as e:
    print(f"ERROR: Failed to initialize AnthropicModel: {e}")
    exit(1)

# 2. Initialize a minimal Agent with this model
try:
    agent = Agent(model)
    print("Agent initialized successfully with AnthropicModel.")
    
    # Check if the agent has the model correctly
    if agent.model:
        print(f"Agent.model is set. Type: {type(agent.model).__name__}")
        # Accessing agent.model_name was causing an error here if agent.model was set but agent itself wasn't fully formed for that property yet.
        # The key is that agent.model IS set.
        # print(f"Agent.model_name (from agent property): {agent.model_name}") # Removed this line
    else:
        print("ERROR: Agent.model is NOT set after initialization.")
        exit(1)

except Exception as e:
    print(f"ERROR: Failed to initialize Agent: {e}")
    exit(1)

# 3. Try a simple run
async def main():
    print("\nAttempting agent.run('Why is the sky blue?')...")
    try:
        response = await agent.run("Why is the sky blue?")
        print("\nAgent run successful!")
        print("Response data:")
        # Depending on pydantic-ai version, response might be a Pydantic model or a string
        if hasattr(response, '__str__'):
             print(str(response)) # Print the whole response object for inspection
        else:
             print(response)

        # If response is a structured object, let's try to access common fields
        if hasattr(response, 'data'):
            print(f"Response.data: {response.data}")
        if hasattr(response, 'all_messages'):
            messages = response.all_messages()
            print("Messages from response.all_messages():")
            for msg in messages:
                print(f"  - {msg}")

    except Exception as e:
        print(f"ERROR: agent.run failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 