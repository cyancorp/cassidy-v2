"""Tests for agent tools functionality"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.tools import structure_journal_tool, save_journal_tool, update_preferences_tool
from app.agents.models import CassidyAgentDependencies


class MockRunContext:
    """Mock RunContext for testing purposes"""
    def __init__(self, deps):
        self.deps = deps


class TestStructureJournalTool:
    """Tests for the LLM-based structure_journal_tool"""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context for testing"""
        deps = CassidyAgentDependencies(
            user_id="test_user",
            session_id="test_session",
            conversation_type="journaling",
            user_template={
                "name": "Test Template",
                "sections": {
                    "General Reflection": {
                        "description": "General thoughts, daily reflections, or free-form journaling content",
                        "aliases": ["Daily Notes", "Journal", "Reflection", "General"]
                    },
                    "Daily Events": {
                        "description": "Significant events, activities, or experiences from the day",
                        "aliases": ["Events", "Activities", "What Happened"]
                    },
                    "Thoughts & Feelings": {
                        "description": "Emotional state, mood, thoughts, and internal experiences",
                        "aliases": ["Emotions", "Mood", "Feelings", "Thoughts"]
                    }
                }
            },
            user_preferences={
                "purpose_statement": None,
                "long_term_goals": [],
                "known_challenges": [],
                "preferred_feedback_style": "supportive",
                "personal_glossary": {}
            },
            current_journal_draft={},
            current_tasks=[]
        )
        return MockRunContext(deps)
    
    @pytest.mark.asyncio
    async def test_empty_text_input(self, mock_context):
        """Test handling of empty text input"""
        result = await structure_journal_tool(mock_context, "")
        
        assert result.status == "no_content"
        assert result.sections_updated == []
    
    @pytest.mark.asyncio
    async def test_whitespace_only_input(self, mock_context):
        """Test handling of whitespace-only input"""
        result = await structure_journal_tool(mock_context, "   \n\t  ")
        
        assert result.status == "no_content"
        assert result.sections_updated == []
    
    @pytest.mark.asyncio
    @patch('pydantic_ai.Agent')
    async def test_llm_analysis_success_single_section(self, mock_agent_class, mock_context):
        """Test successful LLM analysis returning single section"""
        # Mock the LLM response
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = '{"General Reflection": "Today was a good day with positive feelings."}'
        mock_agent.run.return_value = mock_result
        mock_agent_class.return_value = mock_agent
        
        result = await structure_journal_tool(mock_context, "Today was a good day with positive feelings.")
        
        assert result.status == "success"
        assert result.sections_updated == ["General Reflection"]
        assert result.updated_draft_data == {
            "General Reflection": "Today was a good day with positive feelings."
        }
    
    @pytest.mark.asyncio
    @patch('pydantic_ai.Agent')
    async def test_llm_analysis_success_multiple_sections_array(self, mock_agent_class, mock_context):
        """Test successful LLM analysis returning multiple sections with arrays"""
        # Mock the LLM response with array content
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = json.dumps({
            "Daily Events": [
                "Had morning meeting with Sarah",
                "Lunch with brother about mom's birthday",
                "Evening workout at gym"
            ],
            "Thoughts & Feelings": "Started anxious but ended optimistic"
        })
        mock_agent.run.return_value = mock_result
        mock_agent_class.return_value = mock_agent
        
        result = await structure_journal_tool(mock_context, "Complex multi-section content")
        
        assert result.status == "success"
        assert set(result.sections_updated) == {"Daily Events", "Thoughts & Feelings"}
        assert result.updated_draft_data["Daily Events"] == [
            "Had morning meeting with Sarah",
            "Lunch with brother about mom's birthday", 
            "Evening workout at gym"
        ]
        assert result.updated_draft_data["Thoughts & Feelings"] == "Started anxious but ended optimistic"
    
    @pytest.mark.asyncio
    @patch('pydantic_ai.Agent')
    async def test_llm_analysis_with_json_markdown_wrapper(self, mock_agent_class, mock_context):
        """Test LLM response with markdown JSON wrapper"""
        # Mock the LLM response with markdown wrapper
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = '```json\n{"General Reflection": "Test content"}\n```'
        mock_agent.run.return_value = mock_result
        mock_agent_class.return_value = mock_agent
        
        result = await structure_journal_tool(mock_context, "Test content")
        
        assert result.status == "success"
        assert result.updated_draft_data == {"General Reflection": "Test content"}
    
    
    
    
    
    
    @pytest.mark.asyncio
    @patch('pydantic_ai.Agent')
    async def test_llm_json_parse_error_fallback(self, mock_agent_class, mock_context):
        """Test fallback when LLM returns invalid JSON"""
        # Mock the LLM response with invalid JSON
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = 'Invalid JSON response'
        mock_agent.run.return_value = mock_result
        mock_agent_class.return_value = mock_agent
        
        result = await structure_journal_tool(mock_context, "Test content that should fall back")
        
        assert result.status == "success"
        assert result.sections_updated == ["General Reflection"]
        assert result.updated_draft_data == {
            "General Reflection": "Test content that should fall back"
        }
    
    @pytest.mark.asyncio
    @patch('pydantic_ai.Agent')
    async def test_llm_exception_fallback(self, mock_agent_class, mock_context):
        """Test fallback when LLM call raises exception"""
        # Mock the LLM to raise an exception
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = Exception("LLM service unavailable")
        mock_agent_class.return_value = mock_agent
        
        result = await structure_journal_tool(mock_context, "Test content with LLM failure")
        
        assert result.status == "success"
        assert result.sections_updated == ["General Reflection"]
        assert result.updated_draft_data == {
            "General Reflection": "Test content with LLM failure"
        }
    
    @pytest.mark.asyncio
    async def test_default_template_sections(self):
        """Test behavior with no template sections provided"""
        deps = CassidyAgentDependencies(
            user_id="test_user",
            session_id="test_session", 
            conversation_type="journaling",
            user_template={},  # No sections
            user_preferences={},
            current_journal_draft={},
            current_tasks=[]
        )
        context = MockRunContext(deps)
        
        with patch('pydantic_ai.Agent') as mock_agent_class, \
             patch('app.agents.tools.template_loader') as mock_template_loader:
            
            # Mock template loader to return empty template as well
            mock_template_loader.get_user_template.return_value = {"sections": {}}
            
            mock_agent = AsyncMock()
            mock_result = MagicMock()
            mock_result.output = '{"General Reflection": "Test content"}'
            mock_agent.run.return_value = mock_result
            mock_agent_class.return_value = mock_agent
            
            result = await structure_journal_tool(context, "Test content")
            
            assert result.status == "success"
            assert result.sections_updated == ["General Reflection"]


class TestSaveJournalTool:
    """Tests for the save_journal_tool"""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context for testing"""
        deps = CassidyAgentDependencies(
            user_id="test_user",
            session_id="test_session",
            conversation_type="journaling",
            user_template={},
            user_preferences={},
            current_journal_draft={
                "General Reflection": "Test journal content"
            },
            current_tasks=[]
        )
        return MockRunContext(deps)
    
    @pytest.mark.asyncio
    async def test_save_with_confirmation_true(self, mock_context):
        """Test saving journal with confirmation=True"""
        result = await save_journal_tool(mock_context, confirmation=True)
        
        assert result.status == "success"
        assert result.journal_entry_id is not None
        assert len(result.journal_entry_id) > 0  # Should be a UUID string
    
    @pytest.mark.asyncio
    async def test_save_with_confirmation_false(self, mock_context):
        """Test saving journal with confirmation=False"""
        result = await save_journal_tool(mock_context, confirmation=False)
        
        assert result.status == "cancelled"
        assert result.journal_entry_id == ""
    


class TestUpdatePreferencesTool:
    """Tests for the update_preferences_tool"""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context for testing"""
        deps = CassidyAgentDependencies(
            user_id="test_user",
            session_id="test_session",
            conversation_type="journaling",
            user_template={},
            user_preferences={
                "purpose_statement": "Original purpose",
                "long_term_goals": ["Goal 1"],
                "known_challenges": ["Challenge 1"],
                "preferred_feedback_style": "supportive",
                "personal_glossary": {"term1": "definition1"}
            },
            current_journal_draft={},
            current_tasks=[]
        )
        return MockRunContext(deps)
    
    @pytest.mark.asyncio
    async def test_update_string_fields(self, mock_context):
        """Test updating string preference fields"""
        with patch('pydantic_ai.Agent') as mock_agent_class, \
             patch('app.database.async_session_maker') as mock_session_maker:
            
            # Mock the LLM response to return expected preference updates
            mock_agent = AsyncMock()
            mock_result = MagicMock()
            mock_result.output = '{"purpose_statement": "New purpose statement", "preferred_feedback_style": "detailed"}'
            mock_agent.run.return_value = mock_result
            mock_agent_class.return_value = mock_agent
            
            # Mock database session
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            mock_session_maker.return_value.__aexit__.return_value = None
            
            result = await update_preferences_tool(mock_context, {
                "purpose_statement": "New purpose statement",
                "preferred_feedback_style": "detailed"
            })
            
            assert result.status == "success"
            assert set(result.updated_fields) == {"purpose_statement", "preferred_feedback_style"}
            assert mock_context.deps.user_preferences["purpose_statement"] == "New purpose statement"
            assert mock_context.deps.user_preferences["preferred_feedback_style"] == "detailed"
    
    @pytest.mark.asyncio
    async def test_update_list_fields_replace(self, mock_context):
        """Test updating list fields by replacement"""
        result = await update_preferences_tool(mock_context, {
            "long_term_goals": ["New Goal 1", "New Goal 2"],
            "known_challenges": ["New Challenge"]
        })
        
        assert result.status == "success"
        assert set(result.updated_fields) == {"long_term_goals", "known_challenges"}
        assert mock_context.deps.user_preferences["long_term_goals"] == ["New Goal 1", "New Goal 2"]
        assert mock_context.deps.user_preferences["known_challenges"] == ["New Challenge"]
    
    @pytest.mark.asyncio
    async def test_update_list_fields_append_string(self, mock_context):
        """Test appending string to list fields"""
        with patch('pydantic_ai.Agent') as mock_agent_class, \
             patch('app.database.async_session_maker') as mock_session_maker:
            
            # Mock the LLM response to return string updates that should append
            mock_agent = AsyncMock()
            mock_result = MagicMock()
            mock_result.output = '{"long_term_goals": "Goal 2", "known_challenges": "Challenge 2"}'
            mock_agent.run.return_value = mock_result
            mock_agent_class.return_value = mock_agent
            
            # Mock database session
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            mock_session_maker.return_value.__aexit__.return_value = None
            
            result = await update_preferences_tool(mock_context, {
                "long_term_goals": "Goal 2",  # String instead of list
                "known_challenges": "Challenge 2"
            })
            
            assert result.status == "success"
            assert set(result.updated_fields) == {"long_term_goals", "known_challenges"}
            assert mock_context.deps.user_preferences["long_term_goals"] == ["Goal 1", "Goal 2"]
            assert mock_context.deps.user_preferences["known_challenges"] == ["Challenge 1", "Challenge 2"]
    
    @pytest.mark.asyncio
    async def test_update_list_fields_append_duplicate(self, mock_context):
        """Test that duplicate values are not added to lists"""
        result = await update_preferences_tool(mock_context, {
            "long_term_goals": "Goal 1",  # Already exists
        })
        
        assert result.status == "success"
        assert result.updated_fields == []  # No changes made
        assert mock_context.deps.user_preferences["long_term_goals"] == ["Goal 1"]  # Unchanged
    
    @pytest.mark.asyncio
    async def test_update_new_list_field(self, mock_context):
        """Test adding to non-existent list field"""
        # Remove existing list field
        del mock_context.deps.user_preferences["long_term_goals"]
        
        result = await update_preferences_tool(mock_context, {
            "long_term_goals": "First goal"
        })
        
        assert result.status == "success"
        assert result.updated_fields == ["long_term_goals"]
        assert mock_context.deps.user_preferences["long_term_goals"] == ["First goal"]
    
    @pytest.mark.asyncio
    async def test_update_invalid_fields_ignored(self, mock_context):
        """Test that invalid preference fields are ignored"""
        with patch('pydantic_ai.Agent') as mock_agent_class, \
             patch('app.database.async_session_maker') as mock_session_maker:
            
            # Mock the LLM response to only return valid fields
            mock_agent = AsyncMock()
            mock_result = MagicMock()
            mock_result.output = '{"purpose_statement": "Valid update"}'
            mock_agent.run.return_value = mock_result
            mock_agent_class.return_value = mock_agent
            
            # Mock database session
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            mock_session_maker.return_value.__aexit__.return_value = None
            
            result = await update_preferences_tool(mock_context, {
                "purpose_statement": "Valid update",
                "invalid_field": "Should be ignored",
                "another_invalid": ["Also ignored"]
            })
            
            assert result.status == "success"
            assert result.updated_fields == ["purpose_statement"]
            assert mock_context.deps.user_preferences["purpose_statement"] == "Valid update"
            assert "invalid_field" not in mock_context.deps.user_preferences
            assert "another_invalid" not in mock_context.deps.user_preferences
    
    @pytest.mark.asyncio
    async def test_empty_updates(self, mock_context):
        """Test handling of empty preference updates"""
        result = await update_preferences_tool(mock_context, {})
        
        assert result.status == "success"
        assert result.updated_fields == []
    
    @pytest.mark.asyncio
    async def test_personal_glossary_update(self, mock_context):
        """Test updating personal glossary (dict field)"""
        result = await update_preferences_tool(mock_context, {
            "personal_glossary": {"new_term": "new_definition"}
        })
        
        assert result.status == "success"
        assert result.updated_fields == ["personal_glossary"]
        assert mock_context.deps.user_preferences["personal_glossary"] == {"new_term": "new_definition"}