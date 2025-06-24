"""Tests for task creation, completion, and listing functionality"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.task_tools import (
    create_task_tool, 
    complete_task_tool, 
    list_tasks_tool
)
from app.agents.tools import (
    create_task_agent_tool,
    complete_task_agent_tool,
    list_tasks_agent_tool,
    complete_task_by_title_agent_tool
)
from app.agents.models import CassidyAgentDependencies


class MockRunContext:
    """Mock RunContext for testing task tools that use RunContext pattern"""
    def __init__(self, deps):
        self.deps = deps


class TestTaskCreation:
    """Tests for task creation functionality"""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context for testing"""
        deps = CassidyAgentDependencies(
            user_id="test_user_123",
            session_id="test_session_456",
            conversation_type="journaling",
            user_template={},
            user_preferences={},
            current_journal_draft={},
            current_tasks=[]
        )
        return MockRunContext(deps)
    
    @pytest.mark.asyncio
    async def test_create_task_basic(self):
        """Test creating a basic task"""
        user_id = "test_user_123"
        title = "Buy groceries"
        description = "Get milk, bread, and eggs"
        
        with patch('app.agents.task_tools.database.async_session_maker') as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            
            # Mock task repository
            with patch('app.agents.task_tools.TaskRepository') as mock_task_repo_class:
                mock_task_repo = AsyncMock()
                mock_task_repo_class.return_value = mock_task_repo
                
                # Mock task creation
                mock_task = MagicMock()
                mock_task.id = "task_123"
                mock_task.title = title
                mock_task.description = description
                mock_task.user_id = user_id
                mock_task.priority = 3
                mock_task.is_completed = False
                mock_task.due_date = None
                mock_task.created_at = MagicMock()
                mock_task.created_at.isoformat.return_value = "2024-01-01T00:00:00"
                mock_task_repo.create_task.return_value = mock_task
                
                result = await create_task_tool(user_id, title, description)
                
                # Verify result
                assert result["success"] is True
                assert result["task"]["id"] == "task_123"
                assert result["task"]["title"] == title
                assert result["task"]["description"] == description
                
                # Verify repository was called correctly
                mock_task_repo.create_task.assert_called_once()
                call_args = mock_task_repo.create_task.call_args
                assert call_args[1]["title"] == title
                assert call_args[1]["description"] == description
                assert call_args[1]["user_id"] == user_id
    
    @pytest.mark.asyncio
    async def test_create_task_with_due_date(self):
        """Test creating a task with a due date"""
        user_id = "test_user_123"
        title = "Submit report"
        description = "Complete quarterly report"
        due_date = "2024-12-31"
        
        with patch('app.agents.task_tools.database.async_session_maker') as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            
            with patch('app.agents.task_tools.TaskRepository') as mock_task_repo_class:
                mock_task_repo = AsyncMock()
                mock_task_repo_class.return_value = mock_task_repo
                
                mock_task = MagicMock()
                mock_task.id = "task_456"
                mock_task.title = title
                mock_task.description = description
                mock_task.due_date = due_date
                mock_task.priority = 3
                mock_task.is_completed = False
                mock_task.created_at = MagicMock()
                mock_task.created_at.isoformat.return_value = "2024-01-01T00:00:00"
                mock_task_repo.create_task.return_value = mock_task
                
                result = await create_task_tool(user_id, title, description, due_date=due_date)
                
                assert result["success"] is True
                assert result["task"]["id"] == "task_456"
                assert result["task"]["due_date"] == due_date
                
                # Verify due_date was passed to repository
                call_args = mock_task_repo.create_task.call_args
                assert call_args[1]["due_date"] == due_date
    
    @pytest.mark.asyncio
    async def test_create_task_agent_tool(self, mock_context):
        """Test the agent wrapper for create_task_tool"""
        title = "Test task"
        description = "Test description"
        
        with patch('app.agents.tools.create_task_tool') as mock_create_task:
            mock_create_task.return_value = {
                "success": True,
                "task_id": "agent_task_123",
                "title": title,
                "description": description
            }
            
            result = await create_task_agent_tool(mock_context, title, description)
            
            assert result["success"] is True
            assert result["task_id"] == "agent_task_123"
            
            # Verify the underlying function was called with correct parameters
            mock_create_task.assert_called_once_with(
                mock_context.deps.user_id, 
                title, 
                description, 
                due_date=None, 
                source_session_id=mock_context.deps.session_id
            )
    
    @pytest.mark.asyncio
    async def test_create_task_database_error(self):
        """Test handling of database errors during task creation"""
        user_id = "test_user_123"
        title = "Test task"
        
        with patch('app.agents.task_tools.database.async_session_maker') as mock_session_maker:
            mock_session_maker.side_effect = Exception("Database connection failed")
            
            result = await create_task_tool(user_id, title)
            
            assert result["success"] is False
            assert result["message"] == "Failed to create task"
            assert "Database connection failed" in result["error"]


class TestTaskCompletion:
    """Tests for task completion functionality"""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context for testing"""
        deps = CassidyAgentDependencies(
            user_id="test_user_123",
            session_id="test_session_456",
            conversation_type="journaling",
            user_template={},
            user_preferences={},
            current_journal_draft={},
            current_tasks=[
                {"id": "task_123", "title": "Buy milk", "description": "Get 2% milk"},
                {"id": "task_456", "title": "Walk dog", "description": "30 minute walk"}
            ]
        )
        return MockRunContext(deps)
    
    @pytest.mark.asyncio
    async def test_complete_task_by_id(self):
        """Test completing a task by ID"""
        user_id = "test_user_123"
        task_id = "task_123"
        
        with patch('app.agents.task_tools.database.async_session_maker') as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            
            with patch('app.agents.task_tools.TaskRepository') as mock_task_repo_class:
                mock_task_repo = AsyncMock()
                mock_task_repo_class.return_value = mock_task_repo
                
                # Mock task lookup
                mock_task = MagicMock()
                mock_task.id = task_id
                mock_task.title = "Buy milk"
                mock_task.user_id = user_id
                mock_task.is_completed = False
                mock_task_repo.get_by_id.return_value = mock_task
                
                # Mock task completion (updated task)
                mock_updated_task = MagicMock()
                mock_updated_task.id = task_id
                mock_updated_task.title = "Buy milk"
                mock_updated_task.is_completed = True
                mock_updated_task.completed_at = "2024-01-01T00:00:00"
                mock_task_repo.update_task.return_value = mock_updated_task
                
                result = await complete_task_tool(user_id, task_id)
                
                assert result["success"] is True
                assert result["task"]["id"] == task_id
                assert result["task"]["title"] == "Buy milk"
                assert result["task"]["is_completed"] is True
                
                # Verify repository methods were called
                mock_task_repo.get_by_id.assert_called_once_with(mock_db, task_id)
                mock_task_repo.update_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_complete_task_not_found(self):
        """Test completing a task that doesn't exist"""
        user_id = "test_user_123"
        task_id = "nonexistent_task"
        
        with patch('app.agents.task_tools.database.async_session_maker') as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            
            with patch('app.agents.task_tools.TaskRepository') as mock_task_repo_class:
                mock_task_repo = AsyncMock()
                mock_task_repo_class.return_value = mock_task_repo
                
                # Mock task not found
                mock_task_repo.get_by_id.return_value = None
                
                result = await complete_task_tool(user_id, task_id)
                
                assert result["success"] is False
                assert "Task not found" in result["message"]
    
    @pytest.mark.asyncio
    async def test_complete_task_wrong_user(self):
        """Test completing a task that belongs to a different user"""
        user_id = "test_user_123"
        task_id = "task_456"
        
        with patch('app.agents.task_tools.database.async_session_maker') as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            
            with patch('app.agents.task_tools.TaskRepository') as mock_task_repo_class:
                mock_task_repo = AsyncMock()
                mock_task_repo_class.return_value = mock_task_repo
                
                # Mock task belonging to different user
                mock_task = MagicMock()
                mock_task.id = task_id
                mock_task.user_id = "different_user_789"
                mock_task_repo.get_by_id.return_value = mock_task
                
                result = await complete_task_tool(user_id, task_id)
                
                assert result["success"] is False
                assert "access denied" in result["message"].lower()
    
    @pytest.mark.asyncio
    async def test_complete_task_by_title(self, mock_context):
        """Test completing a task by title (fuzzy matching)"""
        task_title = "milk"
        
        with patch('app.agents.tools.complete_task_tool') as mock_complete_task:
            mock_complete_task.return_value = {
                "success": True,
                "task_id": "task_123",
                "title": "Buy milk"
            }
            
            result = await complete_task_by_title_agent_tool(mock_context, task_title)
            
            assert result["success"] is True
            assert result["task_id"] == "task_123"
            
            # Verify the underlying function was called with the matched task ID
            mock_complete_task.assert_called_once_with(
                mock_context.deps.user_id, 
                "task_123"
            )
    
    @pytest.mark.asyncio
    async def test_complete_task_by_title_fuzzy_match(self):
        """Test fuzzy matching when completing tasks by title using agent tool"""
        partial_title = "dog"
        
        # Create a mock context with tasks that include "dog" in the title
        deps = CassidyAgentDependencies(
            user_id="test_user_123",
            session_id="test_session_456",
            conversation_type="journaling",
            user_template={},
            user_preferences={},
            current_journal_draft={},
            current_tasks=[
                {"id": "task_1", "title": "Walk the dog"},
                {"id": "task_2", "title": "Feed dog treats"},
                {"id": "task_3", "title": "Buy cat food"},
            ]
        )
        mock_context = MockRunContext(deps)
        
        with patch('app.agents.tools.complete_task_tool') as mock_complete_task:
            mock_complete_task.return_value = {
                "success": True,
                "task_id": "task_1",
                "title": "Walk the dog"
            }
            
            result = await complete_task_by_title_agent_tool(mock_context, partial_title)
            
            assert result["success"] is True
            assert result["task_id"] == "task_1"
            
            # Should complete the first matching task
            mock_complete_task.assert_called_once_with("test_user_123", "task_1")


class TestTaskListing:
    """Tests for task listing functionality"""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context for testing"""
        deps = CassidyAgentDependencies(
            user_id="test_user_123",
            session_id="test_session_456",
            conversation_type="journaling",
            user_template={},
            user_preferences={},
            current_journal_draft={},
            current_tasks=[]
        )
        return MockRunContext(deps)
    
    @pytest.mark.asyncio
    async def test_list_pending_tasks(self):
        """Test listing pending tasks for a user"""
        user_id = "test_user_123"
        
        with patch('app.agents.task_tools.database.async_session_maker') as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            
            with patch('app.agents.task_tools.TaskRepository') as mock_task_repo_class:
                mock_task_repo = AsyncMock()
                mock_task_repo_class.return_value = mock_task_repo
                
                # Mock tasks
                mock_tasks = [
                    MagicMock(
                        id="task_1", 
                        title="Buy groceries", 
                        description="Get milk and bread",
                        due_date=None,
                        is_completed=False
                    ),
                    MagicMock(
                        id="task_2", 
                        title="Call dentist", 
                        description="Schedule cleaning",
                        due_date="2024-12-30",
                        is_completed=False
                    )
                ]
                mock_task_repo.get_pending_by_user_id.return_value = mock_tasks
                
                result = await list_tasks_tool(user_id, include_completed=False)
                
                assert result["success"] is True
                assert len(result["tasks"]) == 2
                assert result["tasks"][0]["title"] == "Buy groceries"
                assert result["tasks"][1]["title"] == "Call dentist"
                assert result["tasks"][1]["due_date"] == "2024-12-30"
                
                # Verify repository was called correctly
                mock_task_repo.get_pending_by_user_id.assert_called_once_with(mock_db, user_id)
    
    @pytest.mark.asyncio
    async def test_list_all_tasks_including_completed(self):
        """Test listing all tasks including completed ones"""
        user_id = "test_user_123"
        
        with patch('app.agents.task_tools.database.async_session_maker') as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            
            with patch('app.agents.task_tools.TaskRepository') as mock_task_repo_class:
                mock_task_repo = AsyncMock()
                mock_task_repo_class.return_value = mock_task_repo
                
                # Mock tasks including completed ones
                mock_tasks = [
                    MagicMock(
                        id="task_1", 
                        title="Buy groceries", 
                        description="Get milk and bread",
                        is_completed=False
                    ),
                    MagicMock(
                        id="task_2", 
                        title="Walk dog", 
                        description="30 minute walk",
                        is_completed=True
                    )
                ]
                # Mock the tasks with the required attributes for the tool
                for task in mock_tasks:
                    task.priority = 3
                    task.completed_at = None if not task.is_completed else "2024-01-01T00:00:00"
                    task.due_date = None
                    task.created_at = MagicMock()
                    task.created_at.isoformat.return_value = "2024-01-01T00:00:00"
                    task.source_session_id = None
                
                mock_task_repo.get_by_user_id.return_value = mock_tasks
                
                result = await list_tasks_tool(user_id, include_completed=True)
                
                assert result["success"] is True
                assert len(result["tasks"]) == 2
                assert result["tasks"][0]["is_completed"] is False
                assert result["tasks"][1]["is_completed"] is True
                
                # Verify repository was called correctly
                mock_task_repo.get_by_user_id.assert_called_once_with(mock_db, user_id)
    
    @pytest.mark.asyncio
    async def test_list_tasks_agent_tool(self, mock_context):
        """Test the agent wrapper for list_tasks_tool"""
        include_completed = False
        
        with patch('app.agents.tools.list_tasks_tool') as mock_list_tasks:
            mock_list_tasks.return_value = {
                "success": True,
                "tasks": [
                    {"id": "task_1", "title": "Test task", "is_completed": False}
                ]
            }
            
            result = await list_tasks_agent_tool(mock_context, include_completed)
            
            assert result["success"] is True
            assert len(result["tasks"]) == 1
            
            # Verify the underlying function was called
            mock_list_tasks.assert_called_once_with(
                mock_context.deps.user_id, 
                include_completed
            )
    
    @pytest.mark.asyncio
    async def test_list_tasks_empty_result(self):
        """Test listing tasks when user has no tasks"""
        user_id = "test_user_123"
        
        with patch('app.agents.task_tools.database.async_session_maker') as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            
            with patch('app.agents.task_tools.TaskRepository') as mock_task_repo_class:
                mock_task_repo = AsyncMock()
                mock_task_repo_class.return_value = mock_task_repo
                
                # Mock empty result
                mock_task_repo.get_pending_by_user_id.return_value = []
                
                result = await list_tasks_tool(user_id, include_completed=False)
                
                assert result["success"] is True
                assert len(result["tasks"]) == 0


class TestTaskIntegration:
    """Integration tests for task functionality workflow"""
    
    @pytest.mark.asyncio
    async def test_complete_task_workflow(self):
        """Test the complete workflow: create -> list -> complete -> list"""
        user_id = "test_user_123"
        task_title = "Integration test task"
        
        with patch('app.agents.task_tools.database.async_session_maker') as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_db
            
            with patch('app.agents.task_tools.TaskRepository') as mock_task_repo_class:
                mock_task_repo = AsyncMock()
                mock_task_repo_class.return_value = mock_task_repo
                
                # Step 1: Create task
                mock_created_task = MagicMock()
                mock_created_task.id = "integration_task_123"
                mock_created_task.title = task_title
                mock_created_task.user_id = user_id
                mock_task_repo.create.return_value = mock_created_task
                
                create_result = await create_task_tool(user_id, task_title)
                assert create_result["success"] is True
                
                # Step 2: List tasks (should include the new task)
                mock_task_repo.get_pending_by_user_id.return_value = [mock_created_task]
                
                list_result = await list_tasks_tool(user_id, include_completed=False)
                assert list_result["success"] is True
                assert len(list_result["tasks"]) == 1
                assert list_result["tasks"][0]["title"] == task_title
                
                # Step 3: Complete the task
                mock_task_repo.get_by_id.return_value = mock_created_task
                mock_task_repo.complete_task.return_value = mock_created_task
                
                complete_result = await complete_task_tool(user_id, "integration_task_123")
                assert complete_result["success"] is True
                
                # Step 4: List tasks again (should be empty for pending tasks)
                mock_task_repo.get_pending_by_user_id.return_value = []
                
                final_list_result = await list_tasks_tool(user_id, include_completed=False)
                assert final_list_result["success"] is True
                assert len(final_list_result["tasks"]) == 0