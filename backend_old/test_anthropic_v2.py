import asyncio
import os
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from dotenv import load_dotenv
import sys # Import sys

print(f"[test_anthropic_v2.py] id(Agent): {id(Agent)}") 
print(f"[test_anthropic_v2.py] Agent.__module__: {Agent.__module__}")
if Agent.__module__ in sys.modules:
    print(f"[test_anthropic_v2.py] Agent module file: {sys.modules[Agent.__module__].__file__}")

dotenv_path = os.path.join(os.path.dirname(__file__), '../.env')
load_dotenv(dotenv_path=dotenv_path)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL_NAME = os.getenv("ANTHROPIC_DEFAULT_MODEL", "claude-3-7-sonnet-latest") 

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not found in environment variables or .env file.")
    exit(1)

print(f"Using Anthropic Model: {ANTHROPIC_MODEL_NAME}")
print(f"Anthropic API Key (first 5 chars): {ANTHROPIC_API_KEY[:5]}...")

# 1. Initialize the AnthropicModel
model = None # Define model outside try so it's in scope for Agent
try:
    print("\n--- AnthropicProvider Inspection (test_anthropic_v2.py) ---")
    anthropic_provider_instance = AnthropicProvider(api_key=ANTHROPIC_API_KEY)
    # ... (provider inspection logs from original can be kept or removed for brevity) ...
    print(f"Provider instance: {anthropic_provider_instance}")

    model = AnthropicModel(
        ANTHROPIC_MODEL_NAME,
        provider=anthropic_provider_instance
    )
    print("AnthropicModel initialized successfully.")
except Exception as e:
    print(f"ERROR: Failed to initialize AnthropicModel: {e}")
    exit(1)

# 2. Initialize a minimal Agent with this model AND tools=[]
agent = None # Define agent outside try
try:
    print("\nInitializing Agent with model and tools=[]...")
    agent = Agent(model, tools=[]) # MODIFICATION: Added tools=[]
    print("Agent initialized successfully.")
    
    if agent.model:
        print(f"Agent.model is set. Type: {type(agent.model).__name__}")
    else:
        print("ERROR: Agent.model is NOT set after initialization with tools=[].")
        # exit(1) # Let it proceed to run to see if that also errors
except Exception as e:
    print(f"ERROR: Failed to initialize Agent with tools=[]: {e}")
    exit(1)

# 3. Try a simple run (if agent was created)
async def main():
    if not agent:
        print("Agent not created due to initialization error, skipping run.")
        return

    print("\nAttempting agent.run('Why is the sky blue?')...")
    try:
        response = await agent.run("Why is the sky blue?")
        print("\nAgent run successful!")
        print("Response data:")
        if hasattr(response, '__str__'):
             print(str(response))
        else:
             print(response)
        if hasattr(response, 'output'):
            print(f"Response.output: {response.output}")

    except Exception as e:
        print(f"ERROR: agent.run failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 