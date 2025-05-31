import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add the project root directory to the Python path
# This assumes conftest.py is in backend/tests/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure the app module can be found
try:
    from app.main import app
    from app.core.config import settings # Also import settings if needed globally
except ModuleNotFoundError as e:
    print(f"Error importing app or settings in conftest: {e}")
    print("Ensure PYTHONPATH is set correctly or the test runner is invoked from the correct directory.")
    # Optionally raise the error to halt tests if app import fails
    # raise

@pytest.fixture(scope="module")
def client() -> TestClient:
    """Provides a TestClient instance for the FastAPI application."""
    # Ensure the app was imported successfully
    if 'app' not in globals():
        pytest.fail("FastAPI app could not be imported in conftest.py")
    
    # Return the TestClient instance
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def app_settings():
    """Provides the application settings."""
    if 'settings' not in globals():
         pytest.fail("Settings could not be imported in conftest.py")
    return settings

# Add other global fixtures here if needed 