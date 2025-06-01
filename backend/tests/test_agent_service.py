"""Tests for agent service functionality"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import AgentService
from app.models.session import JournalDraftDB, ChatMessageDB, JournalEntryDB
from app.models.user import UserPreferencesDB, UserTemplateDB


class TestAgentService:
    """Tests for AgentService class"""
    
    @pytest.fixture
    async def mock_db_session(self):
        """Mock database session"""
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def agent_service(self, mock_db_session):
        """Create AgentService instance with mocked dependencies"""
        return AgentService(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_create_agent_context_with_existing_data(self, agent_service, mock_db_session):
        """Test creating agent context when all data exists"""
        # Mock existing user data
        mock_prefs = UserPreferencesDB(
            id="prefs_id",
            user_id="test_user",
            purpose_statement="Test purpose",
            long_term_goals=["Goal 1", "Goal 2"],
            known_challenges=["Challenge 1"],
            preferred_feedback_style="supportive",
            personal_glossary={"term": "definition"}
        )
        
        mock_template = UserTemplateDB(
            id="template_id",
            user_id="test_user",
            name="Test Template",
            sections={
                "General Reflection": {
                    "description": "General thoughts",
                    "aliases": ["Journal", "Reflection"]
                }
            },
            is_active=True
        )
        
        mock_draft = JournalDraftDB(
            id="draft_id",
            session_id="test_session",
            user_id="test_user",
            draft_data={"General Reflection": "Existing content"},
            is_finalized=False
        )
        
        with patch.object(agent_service.user_prefs_repo, 'get_by_user_id', return_value=mock_prefs), \
             patch('app.agents.service.template_loader.get_user_template') as mock_template_loader, \
             patch.object(agent_service.journal_draft_repo, 'get_by_session_id', return_value=mock_draft):
            
            mock_template_loader.return_value = {
                "name": "Test Template",
                "sections": {
                    "General Reflection": {
                        "description": "General thoughts",
                        "aliases": ["Journal", "Reflection"]
                    }
                }
            }
            
            context = await agent_service.create_agent_context("test_user", "test_session", "journaling")
            
            # Verify context properties
            assert context.user_id == "test_user"
            assert context.session_id == "test_session"
            assert context.conversation_type == "journaling"
            
            # Verify preferences
            assert context.user_preferences["purpose_statement"] == "Test purpose"
            assert context.user_preferences["long_term_goals"] == ["Goal 1", "Goal 2"]
            assert context.user_preferences["preferred_feedback_style"] == "supportive"
            
            # Verify template
            assert context.user_template["name"] == "Test Template"
            assert "General Reflection" in context.user_template["sections"]
            
            # Verify draft
            assert context.current_journal_draft == {"General Reflection": "Existing content"}
    
    @pytest.mark.asyncio
    async def test_create_agent_context_with_defaults(self, agent_service, mock_db_session):
        """Test creating agent context when data doesn't exist (creates defaults)"""
        # Mock that no data exists
        with patch.object(agent_service.user_prefs_repo, 'get_by_user_id', return_value=None), \
             patch('app.agents.service.template_loader.get_user_template') as mock_template_loader, \
             patch.object(agent_service.journal_draft_repo, 'get_by_session_id', return_value=None), \
             patch.object(agent_service, '_create_default_preferences') as mock_create_prefs, \
             patch.object(agent_service.journal_draft_repo, 'create_draft') as mock_create_draft:
            
            # Setup mock returns for defaults
            mock_create_prefs.return_value = UserPreferencesDB(
                id="new_prefs", user_id="test_user", purpose_statement=None,
                long_term_goals=[], known_challenges=[], 
                preferred_feedback_style="supportive", personal_glossary={}
            )
            
            mock_template_loader.return_value = {
                "name": "Default Template",
                "sections": {"General Reflection": {"description": "General thoughts", "aliases": []}}
            }
            
            mock_create_draft.return_value = JournalDraftDB(
                id="new_draft", session_id="test_session", user_id="test_user",
                draft_data={}, is_finalized=False
            )
            
            context = await agent_service.create_agent_context("test_user", "test_session", "journaling")
            
            # Verify defaults were created
            mock_create_prefs.assert_called_once_with("test_user")
            mock_create_draft.assert_called_once()
            
            # Verify context has default values
            assert context.user_preferences["preferred_feedback_style"] == "supportive"
            assert context.user_template["name"] == "Default Template"
            assert context.current_journal_draft == {}
    
    @pytest.mark.asyncio
    async def test_process_agent_response_structure_tool(self, agent_service, mock_db_session):
        """Test processing agent response with structure_journal_tool"""
        # Create mock agent result
        mock_part = MagicMock()
        mock_part.tool_name = "structure_journal_tool"
        mock_part.content = MagicMock()
        mock_part.content.updated_draft_data = {"General Reflection": "New content"}
        
        mock_message = MagicMock()
        mock_message.parts = [mock_part]
        
        mock_result = MagicMock()
        mock_result.new_messages.return_value = [mock_message]
        mock_result.usage = None
        
        context = MagicMock()
        context.session_id = "test_session"
        
        with patch.object(agent_service.journal_draft_repo, 'update_draft_data') as mock_update:
            response = await agent_service.process_agent_response(context, mock_result)
            
            assert len(response["tool_calls"]) == 1
            assert response["tool_calls"][0]["name"] == "structure_journal_tool"
            assert response["updated_draft_data"] == {"General Reflection": "New content"}
            mock_update.assert_called_once_with(mock_db_session, "test_session", {"General Reflection": "New content"})
    
    @pytest.mark.asyncio
    async def test_process_agent_response_save_tool_success(self, agent_service, mock_db_session):
        """Test processing agent response with successful save_journal_tool"""
        # Create mock agent result
        mock_part = MagicMock()
        mock_part.tool_name = "save_journal_tool"
        mock_part.content = MagicMock()
        mock_part.content.status = "success"
        
        mock_message = MagicMock()
        mock_message.parts = [mock_part]
        
        mock_result = MagicMock()
        mock_result.new_messages.return_value = [mock_message]
        mock_result.usage = None
        
        context = MagicMock()
        context.session_id = "test_session"
        
        # Mock draft with content
        mock_draft = MagicMock()
        mock_draft.draft_data = {"General Reflection": "Content to save"}
        
        # Mock created journal entry
        mock_entry = MagicMock()
        mock_entry.id = "saved_entry_id"
        
        with patch.object(agent_service.journal_draft_repo, 'get_by_session_id', return_value=mock_draft), \
             patch.object(agent_service.journal_draft_repo, 'finalize_draft', return_value=mock_entry):
            
            response = await agent_service.process_agent_response(context, mock_result)
            
            assert len(response["tool_calls"]) == 1
            assert response["tool_calls"][0]["name"] == "save_journal_tool"
            assert response["metadata"]["journal_entry_id"] == "saved_entry_id"
    
    @pytest.mark.asyncio
    async def test_process_agent_response_save_tool_no_content(self, agent_service, mock_db_session):
        """Test processing save_journal_tool when no content exists"""
        # Create mock agent result
        mock_part = MagicMock()
        mock_part.tool_name = "save_journal_tool"
        mock_part.content = MagicMock()
        mock_part.content.status = "success"
        
        mock_message = MagicMock()
        mock_message.parts = [mock_part]
        
        mock_result = MagicMock()
        mock_result.new_messages.return_value = [mock_message]
        mock_result.usage = None
        
        context = MagicMock()
        context.session_id = "test_session"
        
        # Mock draft with no content
        mock_draft = MagicMock()
        mock_draft.draft_data = {}
        
        with patch.object(agent_service.journal_draft_repo, 'get_by_session_id', return_value=mock_draft):
            
            response = await agent_service.process_agent_response(context, mock_result)
            
            assert len(response["tool_calls"]) == 1
            assert "journal_entry_id" not in response["metadata"]
    
    @pytest.mark.asyncio
    async def test_process_agent_response_update_preferences_tool(self, agent_service, mock_db_session):
        """Test processing agent response with update_preferences_tool"""
        # Create mock agent result
        mock_part = MagicMock()
        mock_part.tool_name = "update_preferences_tool"
        mock_part.content = MagicMock()
        
        mock_message = MagicMock()
        mock_message.parts = [mock_part]
        
        mock_result = MagicMock()
        mock_result.new_messages.return_value = [mock_message]
        mock_result.usage = None
        
        context = MagicMock()
        context.user_id = "test_user"
        context.user_preferences = {
            "purpose_statement": "Updated purpose",
            "preferred_feedback_style": "direct"
        }
        
        # Note: update_preferences_tool now handles database updates directly
        # The agent service just skips processing to avoid overwriting
        response = await agent_service.process_agent_response(context, mock_result)
        
        assert len(response["tool_calls"]) == 1
        assert response["tool_calls"][0]["name"] == "update_preferences_tool"
        # No database call expected since tool handles it directly
    
    @pytest.mark.asyncio
    async def test_process_agent_response_with_usage_metadata(self, agent_service, mock_db_session):
        """Test processing agent response includes usage metadata"""
        mock_result = MagicMock()
        mock_result.new_messages.return_value = []
        
        # Mock usage object
        mock_usage = MagicMock()
        mock_usage.total_tokens = 150
        mock_result.usage = mock_usage
        
        context = MagicMock()
        
        response = await agent_service.process_agent_response(context, mock_result)
        
        assert response["metadata"]["usage"]["tokens"] == 150
    
    @pytest.mark.asyncio
    async def test_get_message_history_formatting(self, agent_service, mock_db_session):
        """Test message history retrieval and formatting"""
        # Mock message history
        messages = [
            ChatMessageDB(
                id="msg1", session_id="test_session", role="user",
                content="Hello", message_metadata={}
            ),
            ChatMessageDB(
                id="msg2", session_id="test_session", role="assistant", 
                content="Hi there", message_metadata={}
            )
        ]
        
        with patch.object(agent_service.message_repo, 'get_by_session_id', return_value=messages), \
             patch.object(agent_service.message_repo, 'to_pydantic_message') as mock_format:
            
            # Mock the formatting function
            mock_format.side_effect = [
                MagicMock(parts=[MagicMock(content="Hello")]),
                MagicMock(parts=[MagicMock(content="Hi there")])
            ]
            
            history = await agent_service.get_message_history("test_session")
            
            assert len(history) == 2
            assert mock_format.call_count == 2
    
    @pytest.mark.asyncio
    async def test_create_default_preferences(self, agent_service, mock_db_session):
        """Test creation of default user preferences"""
        with patch.object(agent_service.user_prefs_repo, 'create') as mock_create:
            mock_create.return_value = MagicMock()
            
            await agent_service._create_default_preferences("test_user")
            
            mock_create.assert_called_once_with(
                mock_db_session,
                user_id="test_user",
                purpose_statement=None,
                long_term_goals=[],
                known_challenges=[],
                preferred_feedback_style="supportive",
                personal_glossary={}
            )
    
    # Note: _create_default_template method was removed when we switched to file-based templates
    
    @pytest.mark.asyncio
    async def test_process_agent_response_no_tool_calls(self, agent_service, mock_db_session):
        """Test processing agent response with no tool calls"""
        mock_result = MagicMock()
        mock_result.new_messages.return_value = []
        mock_result.usage = None
        
        context = MagicMock()
        
        response = await agent_service.process_agent_response(context, mock_result)
        
        assert response["tool_calls"] == []
        assert response["updated_draft_data"] is None
        assert response["metadata"] == {}
    
    @pytest.mark.asyncio
    async def test_process_agent_response_multiple_tool_calls(self, agent_service, mock_db_session):
        """Test processing agent response with multiple tool calls"""
        # Create mock agent result with multiple tools
        mock_part1 = MagicMock()
        mock_part1.tool_name = "structure_journal_tool"
        mock_part1.content = MagicMock()
        mock_part1.content.updated_draft_data = {"General Reflection": "Content"}
        
        mock_part2 = MagicMock()
        mock_part2.tool_name = "update_preferences_tool"
        mock_part2.content = MagicMock()
        
        mock_message = MagicMock()
        mock_message.parts = [mock_part1, mock_part2]
        
        mock_result = MagicMock()
        mock_result.new_messages.return_value = [mock_message]
        mock_result.usage = None
        
        context = MagicMock()
        context.session_id = "test_session"
        context.user_id = "test_user"
        context.user_preferences = {}
        
        with patch.object(agent_service.journal_draft_repo, 'update_draft_data'), \
             patch.object(agent_service.user_prefs_repo, 'update_by_user_id'):
            
            response = await agent_service.process_agent_response(context, mock_result)
            
            assert len(response["tool_calls"]) == 2
            tool_names = [call["name"] for call in response["tool_calls"]]
            assert "structure_journal_tool" in tool_names
            assert "update_preferences_tool" in tool_names