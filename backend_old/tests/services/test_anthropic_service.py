import pytest
import json
from unittest.mock import MagicMock, patch

# Add project root to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import anthropic_service
from app import models
from app.repositories import json_repository # Needed for mocking load functions
from anthropic import APIError # Import error for mocking

# --- Mock Data --- 

def mock_claude_response(json_output: dict):
    """Creates a mock Claude API response object."""
    response_mock = MagicMock()
    text_block_mock = MagicMock()
    text_block_mock.text = json.dumps(json_output)
    response_mock.content = [text_block_mock]
    return response_mock

def get_default_user_prefs() -> models.UserPreferences:
    return models.UserPreferences(purpose_statement="Test purpose")

def get_default_user_template() -> models.UserTemplate:
    return models.UserTemplate()

# --- Tests --- 

@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch):
    """Mocks dependencies like the Claude client and repository loads."""
    mock_client_instance = MagicMock()
    # Default successful response
    mock_client_instance.messages.create.return_value = mock_claude_response({
        "summary": "Mocked summary",
        "completed_tasks": ["Mocked task 1"],
        "current_goals": [],
        "emotional_state": "Mocked neutral",
        "planned_tasks": ["Mocked plan 1"]
    })
    monkeypatch.setattr(anthropic_service, "client", mock_client_instance)
    
    # Target the functions as they are referenced within anthropic_service
    monkeypatch.setattr(anthropic_service.repositories, "load_user_preferences", get_default_user_prefs)
    monkeypatch.setattr(anthropic_service.repositories, "load_user_template", get_default_user_template)
    
    return mock_client_instance 

def test_structure_raw_input_success(mock_dependencies):
    """Test successful structuring of raw input."""
    session_id = "test_session_success"
    raw_text = "This is a test journal entry about completing task 1 and planning task 1."
    
    structured_content = anthropic_service.structure_raw_input(session_id, raw_text)
    
    # Assert Claude API was called
    mock_dependencies.messages.create.assert_called_once()
    call_args, call_kwargs = mock_dependencies.messages.create.call_args
    assert call_kwargs['model'] == "claude-3-haiku-20240307"
    assert raw_text in call_kwargs['messages'][0]['content']
    assert "Test purpose" in call_kwargs['messages'][0]['content'] # Check context injection
    
    # Assert the result is structured correctly
    assert structured_content is not None
    assert isinstance(structured_content, models.SessionStructuredContent)
    assert structured_content.session_id == session_id
    assert structured_content.summary == "Mocked summary"
    assert structured_content.completed_tasks == ["Mocked task 1"]
    assert structured_content.emotional_state == "Mocked neutral"
    assert structured_content.planned_tasks == ["Mocked plan 1"]
    assert structured_content.current_goals == [] # From mock response

def test_structure_raw_input_api_error(mock_dependencies, monkeypatch):
    """Test handling of an Anthropic API error."""
    # Setup mock to raise an error - provide dummy request/body
    dummy_request = MagicMock() # Mock the request object
    mock_dependencies.messages.create.side_effect = APIError(
        message="Mock API Error", 
        request=dummy_request, 
        body={"error": "mock"} # Provide a dummy body dict
    )
    
    session_id = "test_session_api_error"
    raw_text = "This entry will cause an API error."
    structured_content = anthropic_service.structure_raw_input(session_id, raw_text)
    mock_dependencies.messages.create.assert_called_once()
    assert structured_content is None

def test_structure_raw_input_json_error(mock_dependencies):
    """Test handling of invalid JSON response from Claude."""
    # Setup mock to return invalid JSON
    invalid_response_mock = MagicMock()
    text_block_mock = MagicMock()
    text_block_mock.text = "This is not valid JSON{"
    invalid_response_mock.content = [text_block_mock]
    mock_dependencies.messages.create.return_value = invalid_response_mock
    
    session_id = "test_session_json_error"
    raw_text = "This entry gets bad JSON back."
    
    structured_content = anthropic_service.structure_raw_input(session_id, raw_text)
    
    # Assert Claude API was called
    mock_dependencies.messages.create.assert_called_once()
    # Assert None is returned on error
    assert structured_content is None

def test_structure_raw_input_validation_error(mock_dependencies):
    """Test handling of Pydantic validation error for Claude response."""
    # Setup mock to return JSON missing required fields or wrong types (if model had them)
    # Our current model is quite forgiving, let's return extra fields
    mock_dependencies.messages.create.return_value = mock_claude_response({
        "summary": "Valid summary",
        "some_unexpected_field": "Claude made this up",
        # Missing other expected fields from default template
    })
    
    session_id = "test_session_validation_error"
    raw_text = "This entry returns unexpected fields."
    
    structured_content = anthropic_service.structure_raw_input(session_id, raw_text)
    
    # Assert Claude API was called
    mock_dependencies.messages.create.assert_called_once()
    
    # Assert the valid parts are parsed and extra goes to custom_fields
    assert structured_content is not None
    assert structured_content.summary == "Valid summary"
    assert structured_content.custom_fields == {"some_unexpected_field": "Claude made this up"}
    # Check that default empty lists were populated for missing standard fields
    assert structured_content.completed_tasks == []
    assert structured_content.planned_tasks == []
    assert structured_content.current_goals == []
    assert structured_content.emotional_state is None

# TODO: Test construct_structuring_prompt logic separately if it becomes more complex.
