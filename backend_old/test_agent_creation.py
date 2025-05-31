# Simple test script to test agent creation
import asyncio
import logging
import sys

# Setup logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])

logger = logging.getLogger(__name__)

async def test_agent_creation():
    try:
        # First import UserPreferences to create a test instance
        from app.models.user import UserPreferences, UserTemplate, SectionDetailDef
        
        # Create test preferences
        test_prefs = UserPreferences(
            purpose_statement="Test journaling",
            long_term_goals=["Test goal 1", "Test goal 2"],
            known_challenges=["Test challenge"],
            preferred_feedback_style="supportive",
            personal_glossary={"test": "definition"}
        )
        
        # Create test template
        test_template = UserTemplate(
            sections={
                "Events": SectionDetailDef(description="Key events from your day"),
                "Thoughts": SectionDetailDef(description="Reflections and ideas"),
            }
        )
        
        logger.info("Created test user preferences and template")
        
        # Import the agent creation function
        from app.agents.main import create_cassidy_agent
        
        logger.info("Starting agent creation test...")
        agent = await create_cassidy_agent(user_preferences=test_prefs)
        
        if agent:
            logger.info("✅ SUCCESS: Agent created successfully!")
            logger.info(f"Agent model: {agent.model}")
            if hasattr(agent, 'tools'):
                logger.info(f"Agent tools: {len(agent.tools)}")
            elif hasattr(agent, 'tool'):
                logger.info(f"Agent tool count: {len(agent.tool) if isinstance(agent.tool, list) else 1}")
            else:
                logger.info("Agent tools: attribute not found")
            return True
        else:
            logger.error("❌ FAILURE: Agent creation returned None")
            return False
            
    except Exception as e:
        logger.error(f"❌ EXCEPTION: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("=== STARTING AGENT CREATION TEST ===")
    result = asyncio.run(test_agent_creation())
    if result:
        logger.info("✓ Test passed!")
        sys.exit(0)
    else:
        logger.error("✗ Test failed!")
        sys.exit(1) 