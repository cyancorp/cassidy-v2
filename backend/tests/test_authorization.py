"""Tests for authorization and access control - ensuring users cannot access each other's content"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import datetime

from app.main import app
from app.models.user import UserDB
from app.models.session import ChatSessionDB
from app.core.deps import get_current_user
from app.database import get_db


class TestSessionAuthorization:
    """Test that users cannot access each other's sessions"""
    
    @pytest.fixture
    def user_a(self):
        """Mock user A"""
        return UserDB(
            id="11111111-1111-1111-1111-111111111111",
            username="user_a",
            email="user_a@example.com",
            password_hash="hashed",
            is_verified=True,
            is_active=True
        )
    
    @pytest.fixture
    def user_b(self):
        """Mock user B"""
        return UserDB(
            id="22222222-2222-2222-2222-222222222222",
            username="user_b",
            email="user_b@example.com",
            password_hash="hashed",
            is_verified=True,
            is_active=True
        )
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def client_as_user_a(self, user_a, mock_db):
        """Test client authenticated as user A"""
        def override_get_current_user():
            return user_a
        
        def override_get_db():
            return mock_db
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db
        
        client = TestClient(app)
        
        yield client
        
        app.dependency_overrides.clear()
    
    def test_user_cannot_access_other_users_session(self, client_as_user_a):
        """Test that user A cannot access user B's session"""
        with patch('app.api.v1.endpoints.sessions.ChatSessionRepository') as mock_session_repo_class:
            
            # Mock session repository - session belongs to user B
            mock_session_repo = AsyncMock()
            user_b_session_id = str(uuid4())
            mock_session = ChatSessionDB(
                id=user_b_session_id, 
                user_id="22222222-2222-2222-2222-222222222222",  # Different user
                conversation_type="journaling", 
                is_active=True,
                session_metadata={},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            mock_session_repo.get_by_id.return_value = mock_session
            mock_session_repo_class.return_value = mock_session_repo
            
            # User A tries to access user B's session
            response = client_as_user_a.get(f"/api/v1/sessions/{user_b_session_id}")
            
            assert response.status_code == 404
            assert "Session not found" in response.json()["detail"]
    
    def test_user_can_access_own_session(self, client_as_user_a):
        """Test that user A can access their own session"""
        with patch('app.api.v1.endpoints.sessions.ChatSessionRepository') as mock_session_repo_class:
            
            # Mock session repository - session belongs to user A
            mock_session_repo = AsyncMock()
            user_a_session_id = str(uuid4())
            mock_session = ChatSessionDB(
                id=user_a_session_id, 
                user_id="11111111-1111-1111-1111-111111111111",  # Same user
                conversation_type="journaling", 
                is_active=True,
                session_metadata={"test": "data"},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            mock_session_repo.get_by_id.return_value = mock_session
            mock_session_repo_class.return_value = mock_session_repo
            
            # User A accesses their own session
            response = client_as_user_a.get(f"/api/v1/sessions/{user_a_session_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == user_a_session_id
            assert data["user_id"] == "11111111-1111-1111-1111-111111111111"
    
    def test_user_only_sees_own_sessions_in_list(self, client_as_user_a):
        """Test that user A only sees their own sessions when listing sessions"""
        with patch('app.api.v1.endpoints.sessions.ChatSessionRepository') as mock_session_repo_class:
            
            # Mock session repository - only returns user A's sessions
            mock_session_repo = AsyncMock()
            user_a_sessions = [
                ChatSessionDB(
                    id=str(uuid4()), 
                    user_id="11111111-1111-1111-1111-111111111111",
                    conversation_type="journaling", 
                    is_active=True,
                    session_metadata={},
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ),
                ChatSessionDB(
                    id=str(uuid4()), 
                    user_id="11111111-1111-1111-1111-111111111111",
                    conversation_type="coaching", 
                    is_active=True,
                    session_metadata={},
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
            ]
            mock_session_repo.get_active_sessions.return_value = user_a_sessions
            mock_session_repo_class.return_value = mock_session_repo
            
            # User A lists sessions
            response = client_as_user_a.get("/api/v1/sessions")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            # Verify all sessions belong to user A
            for session in data:
                assert session["user_id"] == "11111111-1111-1111-1111-111111111111"
            
            # Verify the repository was called with user A's ID
            mock_session_repo.get_active_sessions.assert_called_once_with(mock_session_repo_class().get_active_sessions.call_args[0][0], "11111111-1111-1111-1111-111111111111")


class TestAgentChatAuthorization:
    """Test that users cannot access each other's agent chats"""
    
    @pytest.fixture
    def user_a(self):
        """Mock user A"""
        return UserDB(
            id="11111111-1111-1111-1111-111111111111",
            username="user_a",
            email="user_a@example.com",
            password_hash="hashed",
            is_verified=True,
            is_active=True
        )
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def client_as_user_a(self, user_a, mock_db):
        """Test client authenticated as user A"""
        def override_get_current_user():
            return user_a
        
        def override_get_db():
            return mock_db
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db
        
        client = TestClient(app)
        
        yield client
        
        app.dependency_overrides.clear()
    
    def test_user_cannot_chat_in_other_users_session(self, client_as_user_a):
        """Test that user A cannot send chat messages to user B's session"""
        with patch('app.api.v1.endpoints.agent.ChatSessionRepository') as mock_session_repo_class:
            
            # Mock session repository - session belongs to user B
            mock_session_repo = AsyncMock()
            user_b_session_id = str(uuid4())
            mock_session = ChatSessionDB(
                id=user_b_session_id, 
                user_id="22222222-2222-2222-2222-222222222222",  # Different user
                conversation_type="journaling", 
                is_active=True
            )
            mock_session_repo.get_by_id.return_value = mock_session
            mock_session_repo_class.return_value = mock_session_repo
            
            # User A tries to chat in user B's session
            response = client_as_user_a.post(
                f"/api/v1/agent/chat/{user_b_session_id}",
                json={"text": "Trying to access another user's session"}
            )
            
            assert response.status_code == 404
            assert "Session not found" in response.json()["detail"]


class TestUserPreferencesAuthorization:
    """Test that users cannot access each other's preferences"""
    
    @pytest.fixture
    def user_a(self):
        """Mock user A"""
        return UserDB(
            id="11111111-1111-1111-1111-111111111111",
            username="user_a",
            email="user_a@example.com",
            password_hash="hashed",
            is_verified=True,
            is_active=True
        )
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def client_as_user_a(self, user_a, mock_db):
        """Test client authenticated as user A"""
        def override_get_current_user():
            return user_a
        
        def override_get_db():
            return mock_db
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db
        
        client = TestClient(app)
        
        yield client
        
        app.dependency_overrides.clear()
    
    def test_user_gets_own_preferences_only(self, client_as_user_a):
        """Test that users only get their own preferences"""
        from app.models.user import UserPreferencesDB
        
        with patch('app.api.v1.endpoints.users.UserPreferencesRepository') as mock_prefs_repo_class:
            
            # Mock preferences repository - returns user A's preferences
            mock_prefs_repo = AsyncMock()
            mock_prefs = UserPreferencesDB(
                id="prefs_id",
                user_id="11111111-1111-1111-1111-111111111111",
                purpose_statement="User A's purpose",
                long_term_goals=["User A goal"],
                known_challenges=["User A challenge"],
                preferred_feedback_style="supportive",
                personal_glossary={"term": "User A definition"},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            mock_prefs_repo.get_by_user_id.return_value = mock_prefs
            mock_prefs_repo_class.return_value = mock_prefs_repo
            
            # User A gets preferences
            response = client_as_user_a.get("/api/v1/user/preferences")
            
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "11111111-1111-1111-1111-111111111111"
            assert data["purpose_statement"] == "User A's purpose"
            
            # Verify the repository was called with user A's ID only
            mock_prefs_repo.get_by_user_id.assert_called_once_with(mock_prefs_repo_class().get_by_user_id.call_args[0][0], "11111111-1111-1111-1111-111111111111")
    
    def test_user_updates_own_preferences_only(self, client_as_user_a):
        """Test that users can only update their own preferences"""
        from app.models.user import UserPreferencesDB
        
        with patch('app.api.v1.endpoints.users.UserPreferencesRepository') as mock_prefs_repo_class:
            
            # Mock preferences repository
            mock_prefs_repo = AsyncMock()
            mock_prefs = UserPreferencesDB(
                id="prefs_id",
                user_id="11111111-1111-1111-1111-111111111111",
                purpose_statement="Original purpose",
                long_term_goals=[],
                known_challenges=[],
                preferred_feedback_style="supportive",
                personal_glossary={},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            updated_prefs = UserPreferencesDB(
                id="prefs_id",
                user_id="11111111-1111-1111-1111-111111111111",
                purpose_statement="Updated purpose",
                long_term_goals=["New goal"],
                known_challenges=[],
                preferred_feedback_style="detailed",
                personal_glossary={},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            mock_prefs_repo.get_by_user_id.return_value = mock_prefs
            mock_prefs_repo.update_by_user_id.return_value = updated_prefs
            mock_prefs_repo_class.return_value = mock_prefs_repo
            
            # User A updates preferences
            response = client_as_user_a.post(
                "/api/v1/user/preferences",
                json={
                    "purpose_statement": "Updated purpose",
                    "long_term_goals": ["New goal"],
                    "preferred_feedback_style": "detailed"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "11111111-1111-1111-1111-111111111111"
            assert data["purpose_statement"] == "Updated purpose"
            
            # Verify the repository was called with user A's ID only
            mock_prefs_repo.get_by_user_id.assert_called_once_with(mock_prefs_repo_class().get_by_user_id.call_args[0][0], "11111111-1111-1111-1111-111111111111")
            mock_prefs_repo.update_by_user_id.assert_called_once()
            update_call_args = mock_prefs_repo.update_by_user_id.call_args
            assert update_call_args[0][1] == "11111111-1111-1111-1111-111111111111"  # Second argument should be 11111111-1111-1111-1111-111111111111


class TestTemplateAuthorization:
    """Test that users cannot access each other's templates"""
    
    @pytest.fixture
    def user_a(self):
        """Mock user A"""
        return UserDB(
            id="11111111-1111-1111-1111-111111111111",
            username="user_a",
            email="user_a@example.com",
            password_hash="hashed",
            is_verified=True,
            is_active=True
        )
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def client_as_user_a(self, user_a, mock_db):
        """Test client authenticated as user A"""
        def override_get_current_user():
            return user_a
        
        def override_get_db():
            return mock_db
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db
        
        client = TestClient(app)
        
        yield client
        
        app.dependency_overrides.clear()
    
    def test_user_gets_own_template_only(self, client_as_user_a):
        """Test that users only get their own template"""
        with patch('app.api.v1.endpoints.users.template_loader') as mock_template_loader:
            
            # Mock template loader to return user A's template
            user_a_template = {
                "name": "User A Template",
                "sections": {
                    "Daily Reflection": {
                        "description": "User A's daily thoughts",
                        "aliases": ["Thoughts", "Reflection"]
                    }
                }
            }
            mock_template_loader.get_user_template.return_value = user_a_template
            
            # User A gets template
            response = client_as_user_a.get("/api/v1/user/template")
            
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "11111111-1111-1111-1111-111111111111"
            assert data["name"] == "User A Template"
            
            # Verify template loader was called with user A's ID
            mock_template_loader.get_user_template.assert_called_once_with("11111111-1111-1111-1111-111111111111")


class TestCrossUserDataIsolation:
    """Integration tests to ensure complete data isolation between users"""
    
    @pytest.fixture
    def user_a(self):
        return UserDB(id="11111111-1111-1111-1111-111111111111", username="user_a", email="user_a@test.com", 
                     password_hash="hash", is_verified=True, is_active=True)
    
    @pytest.fixture
    def user_b(self):
        return UserDB(id="22222222-2222-2222-2222-222222222222", username="user_b", email="user_b@test.com", 
                     password_hash="hash", is_verified=True, is_active=True)
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()
    
    def test_complete_data_isolation(self, user_a, user_b, mock_db):
        """Test that users have complete data isolation across all endpoints"""
        
        # Test session isolation
        with patch('app.api.v1.endpoints.sessions.ChatSessionRepository') as mock_session_repo_class:
            mock_session_repo = AsyncMock()
            
            # User A's sessions
            user_a_sessions = [
                ChatSessionDB(
                    id="33333333-3333-3333-3333-333333333333", 
                    user_id="11111111-1111-1111-1111-111111111111", 
                    conversation_type="journaling", 
                    is_active=True, 
                    session_metadata={},
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ),
                ChatSessionDB(
                    id="44444444-4444-4444-4444-444444444444", 
                    user_id="11111111-1111-1111-1111-111111111111", 
                    conversation_type="coaching", 
                    is_active=True, 
                    session_metadata={},
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
            ]
            
            # User B's sessions  
            user_b_sessions = [
                ChatSessionDB(
                    id="55555555-5555-5555-5555-555555555555", 
                    user_id="22222222-2222-2222-2222-222222222222", 
                    conversation_type="journaling", 
                    is_active=True, 
                    session_metadata={},
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ),
            ]
            
            def mock_get_active_sessions(db, user_id):
                if user_id == "11111111-1111-1111-1111-111111111111":
                    return user_a_sessions
                elif user_id == "22222222-2222-2222-2222-222222222222":
                    return user_b_sessions
                return []
            
            mock_session_repo.get_active_sessions.side_effect = mock_get_active_sessions
            mock_session_repo_class.return_value = mock_session_repo
            
            # Override dependencies for user A
            def override_get_current_user_a():
                return user_a
            def override_get_db():
                return mock_db
            
            app.dependency_overrides[get_current_user] = override_get_current_user_a
            app.dependency_overrides[get_db] = override_get_db
            
            with TestClient(app) as client_a:
                # User A should only see their sessions
                response = client_a.get("/api/v1/sessions")
                assert response.status_code == 200
                sessions = response.json()
                assert len(sessions) == 2
                for session in sessions:
                    assert session["user_id"] == "11111111-1111-1111-1111-111111111111"
                    assert session["id"] in ["33333333-3333-3333-3333-333333333333", "44444444-4444-4444-4444-444444444444"]
            
            # Override dependencies for user B
            def override_get_current_user_b():
                return user_b
            
            app.dependency_overrides[get_current_user] = override_get_current_user_b
            
            with TestClient(app) as client_b:
                # User B should only see their sessions
                response = client_b.get("/api/v1/sessions")
                assert response.status_code == 200
                sessions = response.json()
                assert len(sessions) == 1
                assert sessions[0]["user_id"] == "22222222-2222-2222-2222-222222222222"
                assert sessions[0]["id"] == "55555555-5555-5555-5555-555555555555"
            
            app.dependency_overrides.clear()