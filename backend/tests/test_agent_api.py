"""Tests for agent API endpoints"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import UserDB
from app.models.session import ChatSessionDB
from app.core.deps import get_current_user
from app.database import get_db


class TestAgentAPI:
    """Tests for agent API endpoints"""
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        return UserDB(
            id="test_user",
            username="test_user",
            email="test@example.com",
            password_hash="hashed",
            is_verified=True,
            is_active=True
        )
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def test_client_with_auth(self, mock_user, mock_db):
        """Create test client with auth dependencies overridden"""
        def override_get_current_user():
            return mock_user
        
        def override_get_db():
            return mock_db
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db
        
        client = TestClient(app)
        
        yield client
        
        # Clean up overrides
        app.dependency_overrides.clear()
    
    def test_agent_chat_success_structure_journal(self, test_client_with_auth):
        """Test successful agent chat with structure journal tool"""
        with patch('app.api.v1.endpoints.agent.ChatSessionRepository') as mock_session_repo_class, \
             patch('app.api.v1.endpoints.agent.AgentService') as mock_agent_service_class, \
             patch('app.api.v1.endpoints.agent.AgentFactory') as mock_agent_factory, \
             patch('app.api.v1.endpoints.agent.ChatMessageRepository') as mock_message_repo_class:
            
            # Mock session repository
            mock_session_repo = AsyncMock()
            test_session_uuid = "123e4567-e89b-12d3-a456-426614174000"
            mock_session = ChatSessionDB(id=test_session_uuid, user_id="test_user", 
                                       conversation_type="journaling", is_active=True)
            mock_session_repo.get_by_id.return_value = mock_session
            mock_session_repo_class.return_value = mock_session_repo
            
            # Mock agent service
            mock_agent_service = AsyncMock()
            mock_context = MagicMock()
            mock_agent_service.create_agent_context.return_value = mock_context
            mock_agent_service.get_message_history.return_value = []
            mock_agent_service.process_agent_response.return_value = {
                "updated_draft_data": {"General Reflection": "Test content"},
                "tool_calls": [{"name": "structure_journal_tool", "output": {"status": "success"}}],
                "metadata": {}
            }
            mock_agent_service_class.return_value = mock_agent_service
            
            # Mock agent
            mock_agent = AsyncMock()
            mock_result = MagicMock()
            mock_result.output = "I've structured your journal entry successfully."
            mock_result.new_messages.return_value = []
            mock_agent.run.return_value = mock_result
            
            # Mock the async get_agent method
            async def mock_get_agent(*args, **kwargs):
                return mock_agent
            mock_agent_factory.get_agent.side_effect = mock_get_agent
            
            # Mock message repository
            mock_message_repo = AsyncMock()
            mock_message_repo_class.return_value = mock_message_repo
            
            response = test_client_with_auth.post(
                f"/api/v1/agent/chat/{test_session_uuid}",
                json={"text": "I feel happy today"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["text"] == "I've structured your journal entry successfully."
            assert data["session_id"] == test_session_uuid
            assert data["updated_draft_data"] == {"General Reflection": "Test content"}
            assert len(data["tool_calls"]) == 1
    
    def test_agent_chat_session_not_found(self, test_client_with_auth):
        """Test agent chat with non-existent session"""
        with patch('app.api.v1.endpoints.agent.ChatSessionRepository') as mock_session_repo_class:
            
            # Mock session repository - session not found
            mock_session_repo = AsyncMock()
            mock_session_repo.get_by_id.return_value = None
            mock_session_repo_class.return_value = mock_session_repo
            
            nonexistent_uuid = "999e4567-e89b-12d3-a456-426614174999"
            response = test_client_with_auth.post(
                f"/api/v1/agent/chat/{nonexistent_uuid}",
                json={"text": "Test message"}
            )
            
            assert response.status_code == 404
            assert "Session not found" in response.json()["detail"]
    
    def test_agent_chat_wrong_user_session(self, test_client_with_auth):
        """Test agent chat with session belonging to different user"""
        with patch('app.api.v1.endpoints.agent.ChatSessionRepository') as mock_session_repo_class:
            
            # Mock session repository - session belongs to different user
            mock_session_repo = AsyncMock()
            other_user_session_uuid = "888e4567-e89b-12d3-a456-426614174888"
            mock_session = ChatSessionDB(id=other_user_session_uuid, user_id="other_user",
                                       conversation_type="journaling", is_active=True)
            mock_session_repo.get_by_id.return_value = mock_session
            mock_session_repo_class.return_value = mock_session_repo
            
            response = test_client_with_auth.post(
                f"/api/v1/agent/chat/{other_user_session_uuid}",
                json={"text": "Test message"}
            )
            
            assert response.status_code == 404
            assert "Session not found" in response.json()["detail"]
    
    def test_agent_chat_with_message_history(self, test_client_with_auth):
        """Test agent chat includes message history"""
        with patch('app.api.v1.endpoints.agent.ChatSessionRepository') as mock_session_repo_class, \
             patch('app.api.v1.endpoints.agent.AgentService') as mock_agent_service_class, \
             patch('app.api.v1.endpoints.agent.AgentFactory') as mock_agent_factory, \
             patch('app.api.v1.endpoints.agent.ChatMessageRepository') as mock_message_repo_class:
            
            # Mock session
            mock_session_repo = AsyncMock()
            test_session_uuid = "777e4567-e89b-12d3-a456-426614174777"
            mock_session = ChatSessionDB(id=test_session_uuid, user_id="test_user",
                                       conversation_type="journaling", is_active=True)
            mock_session_repo.get_by_id.return_value = mock_session
            mock_session_repo_class.return_value = mock_session_repo
            
            # Mock agent service with message history
            mock_agent_service = AsyncMock()
            mock_context = MagicMock()
            mock_agent_service.create_agent_context.return_value = mock_context
            mock_agent_service.get_message_history.return_value = [
                MagicMock(),  # Previous messages
                MagicMock()
            ]
            mock_agent_service.process_agent_response.return_value = {
                "updated_draft_data": None,
                "tool_calls": [],
                "metadata": {}
            }
            mock_agent_service_class.return_value = mock_agent_service
            
            # Mock agent
            mock_agent = AsyncMock()
            mock_result = MagicMock()
            mock_result.output = "Response with context from previous messages."
            mock_result.new_messages.return_value = []
            mock_agent.run.return_value = mock_result
            
            # Mock the async get_agent method
            async def mock_get_agent(*args, **kwargs):
                return mock_agent
            mock_agent_factory.get_agent.side_effect = mock_get_agent
            
            # Mock message repository
            mock_message_repo = AsyncMock()
            mock_message_repo_class.return_value = mock_message_repo
            
            response = test_client_with_auth.post(
                f"/api/v1/agent/chat/{test_session_uuid}",
                json={"text": "Continue our conversation"}
            )
            
            assert response.status_code == 200
            
            # Verify message history was loaded and passed to agent
            mock_agent_service.get_message_history.assert_called_once_with(test_session_uuid)
            mock_agent.run.assert_called_once()
            call_args = mock_agent.run.call_args
            assert "message_history" in call_args[1]
    
    def test_agent_chat_saves_messages(self, test_client_with_auth):
        """Test that agent chat saves user and assistant messages"""
        with patch('app.api.v1.endpoints.agent.ChatSessionRepository') as mock_session_repo_class, \
             patch('app.api.v1.endpoints.agent.AgentService') as mock_agent_service_class, \
             patch('app.api.v1.endpoints.agent.AgentFactory') as mock_agent_factory, \
             patch('app.api.v1.endpoints.agent.ChatMessageRepository') as mock_message_repo_class:
            
            # Mock session
            mock_session_repo = AsyncMock()
            test_session_uuid = "666e4567-e89b-12d3-a456-426614174666"
            mock_session = ChatSessionDB(id=test_session_uuid, user_id="test_user",
                                       conversation_type="journaling", is_active=True)
            mock_session_repo.get_by_id.return_value = mock_session
            mock_session_repo_class.return_value = mock_session_repo
            
            # Mock agent service
            mock_agent_service = AsyncMock()
            mock_context = MagicMock()
            mock_agent_service.create_agent_context.return_value = mock_context
            mock_agent_service.get_message_history.return_value = []
            mock_agent_service.process_agent_response.return_value = {
                "updated_draft_data": None,
                "tool_calls": [],
                "metadata": {}
            }
            mock_agent_service_class.return_value = mock_agent_service
            
            # Mock agent
            mock_agent = AsyncMock()
            mock_result = MagicMock()
            mock_result.output = "Agent response"
            mock_result.new_messages.return_value = []
            mock_agent.run.return_value = mock_result
            
            # Mock the async get_agent method
            async def mock_get_agent(*args, **kwargs):
                return mock_agent
            mock_agent_factory.get_agent.side_effect = mock_get_agent
            
            # Mock message repository
            mock_message_repo = AsyncMock()
            mock_message_repo_class.return_value = mock_message_repo
            
            response = test_client_with_auth.post(
                f"/api/v1/agent/chat/{test_session_uuid}",
                json={"text": "User message", "metadata": {"key": "value"}}
            )
            
            assert response.status_code == 200
            
            # Verify messages were saved
            assert mock_message_repo.create_message.call_count == 2
            
            # Check user message was saved
            user_call = mock_message_repo.create_message.call_args_list[0]
            assert user_call[1]["role"] == "user"
            assert user_call[1]["content"] == "User message"
            assert user_call[1]["metadata"] == {"key": "value"}
            
            # Check assistant message was saved
            assistant_call = mock_message_repo.create_message.call_args_list[1]
            assert assistant_call[1]["role"] == "assistant"
            assert assistant_call[1]["content"] == "Agent response"
    
    def test_agent_chat_handles_agent_exception(self, test_client_with_auth):
        """Test agent chat handles exceptions gracefully"""
        with patch('app.api.v1.endpoints.agent.ChatSessionRepository') as mock_session_repo_class, \
             patch('app.api.v1.endpoints.agent.AgentService') as mock_agent_service_class, \
             patch('app.api.v1.endpoints.agent.AgentFactory') as mock_agent_factory:
            
            # Mock session
            mock_session_repo = AsyncMock()
            test_session_uuid = "666e4567-e89b-12d3-a456-426614174666"
            mock_session = ChatSessionDB(id=test_session_uuid, user_id="test_user",
                                       conversation_type="journaling", is_active=True)
            mock_session_repo.get_by_id.return_value = mock_session
            mock_session_repo_class.return_value = mock_session_repo
            
            # Mock agent service
            mock_agent_service = AsyncMock()
            mock_context = MagicMock()
            mock_agent_service.create_agent_context.return_value = mock_context
            mock_agent_service.get_message_history.return_value = []
            mock_agent_service_class.return_value = mock_agent_service
            
            # Mock agent that raises exception
            mock_agent = AsyncMock()
            mock_agent.run.side_effect = Exception("Agent processing failed")
            
            # Mock the async get_agent method
            async def mock_get_agent(*args, **kwargs):
                return mock_agent
            mock_agent_factory.get_agent.side_effect = mock_get_agent
            
            response = test_client_with_auth.post(
                f"/api/v1/agent/chat/{test_session_uuid}",
                json={"text": "Test message"}
            )
            
            assert response.status_code == 500
            assert "Sorry, I encountered an error" in response.json()["detail"]
    
    def test_agent_chat_fallback_without_message_history(self, test_client_with_auth):
        """Test agent chat falls back when message history fails"""
        with patch('app.api.v1.endpoints.agent.ChatSessionRepository') as mock_session_repo_class, \
             patch('app.api.v1.endpoints.agent.AgentService') as mock_agent_service_class, \
             patch('app.api.v1.endpoints.agent.AgentFactory') as mock_agent_factory, \
             patch('app.api.v1.endpoints.agent.ChatMessageRepository') as mock_message_repo_class:
            
            # Mock session
            mock_session_repo = AsyncMock()
            test_session_uuid = "666e4567-e89b-12d3-a456-426614174666"
            mock_session = ChatSessionDB(id=test_session_uuid, user_id="test_user",
                                       conversation_type="journaling", is_active=True)
            mock_session_repo.get_by_id.return_value = mock_session
            mock_session_repo_class.return_value = mock_session_repo
            
            # Mock agent service
            mock_agent_service = AsyncMock()
            mock_context = MagicMock()
            mock_agent_service.create_agent_context.return_value = mock_context
            # Return non-empty history so the fallback logic is triggered
            mock_agent_service.get_message_history.return_value = [MagicMock()]
            mock_agent_service.process_agent_response.return_value = {
                "updated_draft_data": None,
                "tool_calls": [],
                "metadata": {}
            }
            mock_agent_service_class.return_value = mock_agent_service
            
            # Mock agent that fails with message history but succeeds without
            mock_agent = AsyncMock()
            mock_result = MagicMock()
            mock_result.output = "Agent response without history"
            mock_result.new_messages.return_value = []
            
            def mock_run(*args, **kwargs):
                if "message_history" in kwargs and kwargs["message_history"]:
                    raise Exception("Message history format error")
                return mock_result
            
            mock_agent.run.side_effect = mock_run
            
            # Mock the async get_agent method
            async def mock_get_agent_async(*args, **kwargs):
                return mock_agent
            mock_agent_factory.get_agent.side_effect = mock_get_agent_async
            
            # Mock message repository
            mock_message_repo = AsyncMock()
            mock_message_repo_class.return_value = mock_message_repo
            
            response = test_client_with_auth.post(
                f"/api/v1/agent/chat/{test_session_uuid}",
                json={"text": "Test message"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["text"] == "Agent response without history"
            
            # Verify agent was called twice (once with history, once without)
            assert mock_agent.run.call_count == 2