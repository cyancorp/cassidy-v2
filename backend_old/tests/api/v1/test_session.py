from fastapi.testclient import TestClient
from datetime import datetime
import os

# REMOVE path manipulation
# import sys
# from pathlib import Path
# sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Import only the necessary models
from app.models import SessionRawInput
# REMOVE app and settings imports
# from app.main import app 
# from app.core.config import settings

# REMOVE explicit client creation
# client = TestClient(app)

def test_start_new_session(client: TestClient, app_settings): # Add fixtures as arguments
    """Test the /api/v1/session/start endpoint."""
    # Use the client fixture
    response = client.post(f"{app_settings.API_V1_STR}/session/start") # Use app_settings fixture
    
    assert response.status_code == 200
    data = response.json()
    
    # Validate the response structure using the Pydantic model
    try:
        session_data = SessionRawInput(**data)
    except Exception as e:
        assert False, f"Response validation failed: {e}"
    
    assert session_data.raw_text == "Session started."
    assert isinstance(session_data.session_id, str)
    assert len(session_data.session_id) > 0 
    assert abs((datetime.utcnow() - session_data.timestamp).total_seconds()) < 5

    # Check if the corresponding file was created
    expected_file = app_settings.SESSIONS_DIR / f"{session_data.session_id}_raw.json" # Use app_settings fixture
    assert expected_file.exists()
    # Clean up the created file
    os.remove(expected_file)

# TODO: Add more tests for submit_raw, save_structured, error cases etc. 