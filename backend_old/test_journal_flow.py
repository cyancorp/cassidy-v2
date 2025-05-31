# Test script for verifying the full journal workflow
import asyncio
import logging
import sys
import json
from pprint import pformat
import pytest

# Setup logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])

logger = logging.getLogger(__name__)

@pytest.mark.asyncio  # Add this decorator for pytest-asyncio
async def test_journal_flow():
    """Test all journal tools in sequence."""
    try:
        # 1. Set up test data
        from app.models.user import UserPreferences, UserTemplate, SectionDetailDef
        from app.agents.models import CassidyAgentDependencies, JournalDraft
        from pydantic_ai import Agent
        
        # Create test user preferences
        test_prefs = UserPreferences(
            purpose_statement="Test journaling for personal growth",
            long_term_goals=["Improve self-awareness", "Record daily events"],
            known_challenges=["Finding time to journal"],
            preferred_feedback_style="supportive",
            personal_glossary={"mindfulness": "Being present and aware"}
        )
        
        # Create test template
        test_template = UserTemplate(
            sections={
                "Events": SectionDetailDef(description="Key events from your day"),
                "Thoughts": SectionDetailDef(description="Reflections and ideas"),
                "Feelings": SectionDetailDef(description="Emotional state"),
            }
        )
        
        # 2. Create test dependencies
        test_chat_id = "test_journal_session_001"
        test_user_id = "test_user_001"
        
        # Create dependencies object
        deps = CassidyAgentDependencies(
            user_id=test_user_id,
            current_chat_id=test_chat_id,
            chat_type="journaling",
            user_template=test_template,
            user_preferences=test_prefs,
            current_journal_draft=JournalDraft()
        )
        
        # 3. Import the tools directly
        from app.agents.tools import (
            _structure_journal_entry_run, 
            _update_preferences_run, 
            _finalize_journal_run,
            StructureJournalInput,
            UpdatePreferencesInput
        )
        
        # 4. Test structure journal tool
        logger.info("STEP 1: Testing structure journal tool...")
        test_journal_text = """
        Today was a productive day. I had a meeting with my team in the morning and we made
        good progress on the project. I felt really good about our achievements. In the afternoon, 
        I went for a walk to clear my mind and had some interesting thoughts about my career direction.
        """
        
        structure_result = _structure_journal_entry_run(
            ctx=deps,
            args=StructureJournalInput(user_text=test_journal_text)
        )
        
        if structure_result and structure_result.updated_draft_data:
            logger.info("✅ Structure journal tool test passed!")
            logger.info(f"Structured content: \n{pformat(structure_result.updated_draft_data)}")
            
            # Update our dependencies with the structured content
            deps.current_journal_draft.data = structure_result.updated_draft_data
        else:
            logger.error("❌ Structure journal tool test failed!")
            return False
        
        # 5. Test update preferences tool
        logger.info("\nSTEP 2: Testing update preferences tool...")
        test_preferences_text = """
        I'm trying to develop a habit of mindfulness and meditation. My goal is to become 
        more emotionally balanced. One challenge I face is consistent practice.
        """
        
        preferences_result = _update_preferences_run(
            ctx=deps,
            args=UpdatePreferencesInput(user_text=test_preferences_text)
        )
        
        if preferences_result and preferences_result.updated_preferences_data:
            logger.info("✅ Update preferences tool test passed!")
            logger.info(f"Updated preferences: \n{preferences_result.updated_preferences_data.model_dump_json(indent=2)}")
            
            # Update our dependencies with the new preferences
            deps.user_preferences = preferences_result.updated_preferences_data
        else:
            logger.error("❌ Update preferences tool test failed or no updates found!")
            # Continue anyway as this isn't critical
        
        # 6. Test finalize journal tool
        logger.info("\nSTEP 3: Testing finalize journal tool...")
        finalize_result = _finalize_journal_run(ctx=deps)
        
        if finalize_result and finalize_result.finalized_session_id:
            logger.info("✅ Finalize journal tool test passed!")
            logger.info(f"Finalization message: {finalize_result.confirmation_message}")
            logger.info(f"Finalized session ID: {finalize_result.finalized_session_id}")
        else:
            logger.error("❌ Finalize journal tool test failed!")
            logger.info(f"Message: {finalize_result.confirmation_message if finalize_result else 'No result'}")
            return False
        
        # 7. Check if the journal was actually saved in the data directory
        import os
        from app.core.config import settings
        
        expected_file = os.path.join(settings.SESSIONS_DIR, f"{test_chat_id}_structured.json")
        if os.path.exists(expected_file):
            logger.info(f"✅ Verified journal file was saved to: {expected_file}")
            
            # Read the file to verify contents
            with open(expected_file, 'r') as f:
                saved_content = json.load(f)
            logger.info(f"Saved journal content: \n{pformat(saved_content)}")
            
            # Clean up - delete the test file
            os.remove(expected_file)
            logger.info(f"Cleaned up test file: {expected_file}")
        else:
            logger.error(f"❌ Journal file was not saved to: {expected_file}")
            return False
        
        return True
            
    except Exception as e:
        logger.error(f"❌ EXCEPTION: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("=== STARTING JOURNAL FLOW TEST ===")
    result = asyncio.run(test_journal_flow())
    if result:
        logger.info("✓ All journal flow tests passed!")
        sys.exit(0)
    else:
        logger.error("✗ Journal flow tests failed!")
        sys.exit(1) 