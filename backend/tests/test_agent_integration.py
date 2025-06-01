"""Integration tests for agent functionality"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import AgentService
from app.agents.factory import AgentFactory
from app.models.session import ChatSessionDB, JournalDraftDB
from app.models.user import UserDB


class TestAgentIntegration:
    """Integration tests for agent service and tools"""
    
    @pytest.fixture
    async def mock_db_session(self):
        """Mock database session"""
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def mock_user(self):
        """Mock user"""
        return UserDB(
            id="test_user_id",
            username="test_user",
            email="test@example.com",
            password_hash="hashed",
            is_verified=True,
            is_active=True
        )
    
    @pytest.fixture
    def mock_session(self):
        """Mock chat session"""
        return ChatSessionDB(
            id="test_session_id",
            user_id="test_user_id",
            conversation_type="journaling",
            is_active=True,
            session_metadata={}
        )
    
    @pytest.mark.asyncio
    async def test_journal_entry_creation_workflow(self, mock_db_session, mock_user, mock_session):
        """Test complete journal entry creation workflow"""
        # Setup
        agent_service = AgentService(mock_db_session)
        
        # Mock repository responses
        with patch.object(agent_service.user_prefs_repo, 'get_by_user_id') as mock_get_prefs, \
             patch.object(agent_service.user_template_repo, 'get_active_by_user_id') as mock_get_template, \
             patch.object(agent_service.journal_draft_repo, 'get_by_session_id') as mock_get_draft, \
             patch.object(agent_service.journal_draft_repo, 'create_draft') as mock_create_draft, \
             patch.object(agent_service.journal_draft_repo, 'update_draft_data') as mock_update_draft, \
             patch.object(agent_service.journal_draft_repo, 'finalize_draft') as mock_finalize_draft, \
             patch.object(agent_service.message_repo, 'get_by_session_id') as mock_get_messages:
            
            # Setup mock returns
            mock_get_prefs.return_value = None  # Will create default
            mock_get_template.return_value = None  # Will create default
            mock_get_draft.return_value = None  # Will create new
            mock_create_draft.return_value = JournalDraftDB(
                id="draft_id",
                session_id="test_session_id",
                user_id="test_user_id",
                draft_data={},
                is_finalized=False
            )
            mock_get_messages.return_value = []
            
            # Create context
            context = await agent_service.create_agent_context(
                mock_user.id, mock_session.id, "journaling"
            )
            
            # Verify context creation
            assert context.user_id == mock_user.id
            assert context.session_id == mock_session.id
            assert context.conversation_type == "journaling"
            assert context.current_journal_draft == {}
            
            # Mock agent result for structure_journal_tool
            mock_agent_result = MagicMock()
            mock_agent_result.new_messages.return_value = [
                MagicMock(parts=[
                    MagicMock(
                        tool_name="structure_journal_tool",
                        content=MagicMock(
                            sections_updated=["General Reflection"],
                            updated_draft_data={"General Reflection": "Test journal content"},
                            status="success"
                        )
                    )
                ])
            ]
            mock_agent_result.usage = None
            
            # Process the result
            response_data = await agent_service.process_agent_response(context, mock_agent_result)
            
            # Verify structure tool processing
            assert response_data["updated_draft_data"] == {"General Reflection": "Test journal content"}
            assert len(response_data["tool_calls"]) == 1
            assert response_data["tool_calls"][0]["name"] == "structure_journal_tool"
            mock_update_draft.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_journal_save_workflow(self, mock_db_session):
        """Test journal save workflow"""
        agent_service = AgentService(mock_db_session)
        
        # Mock existing draft
        mock_draft = JournalDraftDB(
            id="draft_id",
            session_id="test_session_id", 
            user_id="test_user_id",
            draft_data={"General Reflection": "Content to save"},
            is_finalized=False
        )
        
        # Mock finalized entry
        from app.models.session import JournalEntryDB
        mock_entry = JournalEntryDB(
            id="entry_id",
            user_id="test_user_id",
            session_id="test_session_id",
            title="Test Entry",
            structured_data={"General Reflection": "Content to save"},
            metadata={}
        )
        
        with patch.object(agent_service.journal_draft_repo, 'get_by_session_id') as mock_get_draft, \
             patch.object(agent_service.journal_draft_repo, 'finalize_draft') as mock_finalize:
            
            mock_get_draft.return_value = mock_draft
            mock_finalize.return_value = mock_entry
            
            # Mock agent result for save_journal_tool
            mock_agent_result = MagicMock()
            mock_agent_result.new_messages.return_value = [
                MagicMock(parts=[
                    MagicMock(
                        tool_name="save_journal_tool",
                        content=MagicMock(
                            journal_entry_id="generated_id",
                            status="success"
                        )
                    )
                ])
            ]
            mock_agent_result.usage = None
            
            # Create context with existing draft
            context = MagicMock()
            context.session_id = "test_session_id"
            
            # Process the result
            response_data = await agent_service.process_agent_response(context, mock_agent_result)
            
            # Verify save processing
            assert response_data["metadata"]["journal_entry_id"] == mock_entry.id
            mock_finalize.assert_called_once_with(mock_db_session, "test_session_id")
    
    @pytest.mark.asyncio
    async def test_message_history_formatting(self, mock_db_session):
        """Test message history formatting for agent context"""
        agent_service = AgentService(mock_db_session)
        
        # Mock message history
        from app.models.session import ChatMessageDB
        messages = [
            ChatMessageDB(
                id="msg1",
                session_id="test_session",
                role="user",
                content="Hello, I want to journal",
                message_metadata={}
            ),
            ChatMessageDB(
                id="msg2", 
                session_id="test_session",
                role="assistant",
                content="I'll help you with journaling",
                message_metadata={}
            )
        ]
        
        with patch.object(agent_service.message_repo, 'get_by_session_id') as mock_get_messages:
            mock_get_messages.return_value = messages
            
            history = await agent_service.get_message_history("test_session")
            
            assert len(history) == 2
            
            # Check first message (user)
            assert hasattr(history[0], 'parts')
            assert len(history[0].parts) == 1
            assert history[0].parts[0].content == "Hello, I want to journal"
            
            # Check second message (assistant) 
            assert hasattr(history[1], 'parts')
            assert len(history[1].parts) == 1
            assert history[1].parts[0].content == "I'll help you with journaling"
    
    @pytest.mark.asyncio
    @patch('app.agents.factory.AgentFactory.get_agent')
    async def test_multi_turn_conversation_context(self, mock_get_agent, mock_db_session):
        """Test that context is maintained across multiple turns"""
        # Mock agent
        mock_agent = AsyncMock()
        mock_get_agent.return_value = mock_agent
        
        agent_service = AgentService(mock_db_session)
        
        # Mock first turn - add content
        with patch.object(agent_service, 'create_agent_context') as mock_create_context:
            mock_context = MagicMock()
            mock_context.current_journal_draft = {}
            mock_create_context.return_value = mock_context
            
            # First turn result - structure tool called
            first_result = MagicMock()
            first_result.new_messages.return_value = [
                MagicMock(parts=[
                    MagicMock(
                        tool_name="structure_journal_tool",
                        content=MagicMock(
                            updated_draft_data={"General Reflection": "First entry"},
                            sections_updated=["General Reflection"],
                            status="success"
                        )
                    )
                ])
            ]
            first_result.usage = None
            
            # Process first turn
            with patch.object(agent_service.journal_draft_repo, 'update_draft_data'):
                await agent_service.process_agent_response(mock_context, first_result)
            
            # Second turn - context should have updated draft
            mock_context.current_journal_draft = {"General Reflection": "First entry"}
            
            # Second turn result - save tool called
            second_result = MagicMock()
            second_result.new_messages.return_value = [
                MagicMock(parts=[
                    MagicMock(
                        tool_name="save_journal_tool",
                        content=MagicMock(
                            journal_entry_id="saved_id",
                            status="success"
                        )
                    )
                ])
            ]
            second_result.usage = None
            
            # Mock draft retrieval for save
            mock_draft = MagicMock()
            mock_draft.draft_data = {"General Reflection": "First entry"}
            
            with patch.object(agent_service.journal_draft_repo, 'get_by_session_id') as mock_get_draft, \
                 patch.object(agent_service.journal_draft_repo, 'finalize_draft') as mock_finalize:
                
                mock_get_draft.return_value = mock_draft
                mock_finalize.return_value = MagicMock(id="final_entry_id")
                
                # Process second turn
                response = await agent_service.process_agent_response(mock_context, second_result)
                
                # Verify save succeeded with context from first turn
                assert response["metadata"]["journal_entry_id"] == "final_entry_id"
                mock_finalize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_llm_failure(self, mock_db_session):
        """Test error handling when LLM fails"""
        agent_service = AgentService(mock_db_session)
        
        # Mock agent result with no tool calls (LLM failure scenario)
        mock_agent_result = MagicMock()
        mock_agent_result.new_messages.return_value = []
        mock_agent_result.usage = None
        
        context = MagicMock()
        context.session_id = "test_session"
        
        # Process should handle gracefully
        response_data = await agent_service.process_agent_response(context, mock_agent_result)
        
        assert response_data["tool_calls"] == []
        assert response_data["updated_draft_data"] is None
        assert response_data["metadata"] == {}
    
    @pytest.mark.asyncio
    async def test_preferences_update_workflow(self, mock_db_session):
        """Test preferences update workflow"""
        agent_service = AgentService(mock_db_session)
        
        # Mock agent result for update_preferences_tool
        mock_agent_result = MagicMock()
        mock_agent_result.new_messages.return_value = [
            MagicMock(parts=[
                MagicMock(
                    tool_name="update_preferences_tool",
                    content=MagicMock(
                        updated_fields=["purpose_statement"],
                        status="success"
                    )
                )
            ])
        ]
        mock_agent_result.usage = None
        
        context = MagicMock()
        context.user_id = "test_user"
        context.user_preferences = {"purpose_statement": "Updated purpose"}
        
        with patch.object(agent_service.user_prefs_repo, 'update_by_user_id') as mock_update_prefs:
            
            # Process the result
            response_data = await agent_service.process_agent_response(context, mock_agent_result)
            
            # Verify preferences update
            assert len(response_data["tool_calls"]) == 1
            assert response_data["tool_calls"][0]["name"] == "update_preferences_tool"
            mock_update_prefs.assert_called_once_with(
                mock_db_session, 
                "test_user", 
                purpose_statement="Updated purpose"
            )