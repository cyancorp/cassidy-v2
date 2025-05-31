import json
from pathlib import Path
from typing import Type, TypeVar, Generic, List, Optional
import logging
from pydantic import BaseModel

from ..core.config import settings
from ..models import (
    SessionRawInput, SessionStructuredContent, SessionConversation, 
    # Insight - Needs direct import below
    # UserTemplate, UserPreferences - Needs direct import below
)
# Import user models directly if needed for type hints
from ..models.user import UserTemplate, UserPreferences
from ..models.insight import Insight # Added direct import for Insight

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define a generic type variable for Pydantic models
ModelType = TypeVar('ModelType', bound=BaseModel)

class JsonRepository(Generic[ModelType]):
    """Generic repository for handling Pydantic models as JSON files."""

    def __init__(self, model_type: Type[ModelType], base_directory: Path):
        self.model_type = model_type
        self.base_directory = base_directory
        # Ensure the base directory exists (should have been created by settings)
        if not self.base_directory.exists():
            logger.warning(f"Base directory {self.base_directory} not found. Creating it.")
            self.base_directory.mkdir(parents=True, exist_ok=True)

    def _get_filepath(self, item_id: str) -> Path:
        """Constructs the full path for a given item ID."""
        return self.base_directory / f"{item_id}.json"

    def save(self, item_id: str, data: ModelType) -> bool:
        """Saves a Pydantic model instance as a JSON file."""
        filepath = self._get_filepath(item_id)
        try:
            json_data = data.model_dump_json(indent=2)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_data)
            logger.info(f"Saved {self.model_type.__name__} with ID {item_id} to {filepath}")
            return True
        except IOError as e:
            logger.error(f"Error saving {self.model_type.__name__} ID {item_id} to {filepath}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving {self.model_type.__name__} ID {item_id}: {e}")
            return False

    def load(self, item_id: str) -> Optional[ModelType]:
        """Loads a Pydantic model instance from a JSON file."""
        filepath = self._get_filepath(item_id)
        if not filepath.exists():
            logger.warning(f"{self.model_type.__name__} with ID {item_id} not found at {filepath}")
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json_data = f.read()
            model_instance = self.model_type.model_validate_json(json_data)
            logger.info(f"Loaded {self.model_type.__name__} with ID {item_id} from {filepath}")
            return model_instance
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON for {self.model_type.__name__} ID {item_id} from {filepath}: {e}")
            return None
        except IOError as e:
            logger.error(f"Error reading file for {self.model_type.__name__} ID {item_id} from {filepath}: {e}")
            return None
        except Exception as e: # Includes Pydantic validation errors
            logger.error(f"Error loading/validating {self.model_type.__name__} ID {item_id}: {e}")
            return None

    def list_ids(self) -> List[str]:
        """Lists the IDs of all items in the repository (based on filenames)."""
        try:
            return [p.stem for p in self.base_directory.glob('*.json') if p.is_file()]
        except Exception as e:
            logger.error(f"Error listing IDs in {self.base_directory}: {e}")
            return []

# --- Specific Repository Instances --- 
# Note: For user data with fixed filenames, we might need slightly different methods

session_raw_repo = JsonRepository(SessionRawInput, settings.SESSIONS_DIR)
session_structured_repo = JsonRepository(SessionStructuredContent, settings.SESSIONS_DIR)
session_conversation_repo = JsonRepository(SessionConversation, settings.SESSIONS_DIR)
insight_repo = JsonRepository(Insight, settings.INSIGHTS_DIR)

# --- Special Handling for User Data (User-Specific Filenames) --- 

def _get_user_template_path(user_id: str) -> Path:
    """Get the path to the user's template file.
    
    Convention: store as user/{user_id}/template.json rather than user/{user_id}_template.json
    Ensures data is organized by user
    """
    # Ensure user directory exists
    user_dir = settings.USER_DATA_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Return the path to the template file
    return user_dir / "template.json"

def _get_user_prefs_path(user_id: str) -> Path:
    """Get the path to the user's preferences file.
    
    Convention: store as user/{user_id}/preferences.json rather than user/{user_id}_preferences.json
    Ensures data is organized by user
    """
    # Ensure user directory exists
    user_dir = settings.USER_DATA_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Return the path to the preferences file
    return user_dir / "preferences.json"

def save_user_template(user_id: str, data: UserTemplate) -> bool:
    filepath = _get_user_template_path(user_id)
    try:
        json_data = data.model_dump_json(indent=2)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json_data)
        logger.info(f"Saved UserTemplate for user {user_id} to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error saving UserTemplate for user {user_id}: {e}")
        return False

def load_user_template(user_id: str) -> UserTemplate:
    """Get the path to the user's template file.
    
    Convention: store as user/{user_id}/template.json rather than user/{user_id}_template.json
    Ensures data is organized by user
    """
    filepath = _get_user_template_path(user_id)
    if not filepath.exists():
        logger.info(f"User template file for user {user_id} not found at {filepath}, returning default.")
        from datetime import datetime
        default_template = UserTemplate(
            last_updated=datetime.utcnow()
        ) # Create default instance with explicit last_updated
        # Optionally save the default for this new user if that's desired behavior
        # save_user_template(user_id, default_template)
        return default_template
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            json_data = f.read()
        model_instance = UserTemplate.model_validate_json(json_data)
        
        # Ensure last_updated is set
        from datetime import datetime
        if not model_instance.last_updated:
            model_instance.last_updated = datetime.utcnow()
            logger.info(f"Added missing last_updated timestamp to template for user {user_id}")
            
        logger.info(f"Loaded UserTemplate for user {user_id} from {filepath}")
        return model_instance
    except Exception as e:
        logger.error(f"Error loading UserTemplate for user {user_id} from {filepath}: {e}. Returning default.")
        from datetime import datetime
        return UserTemplate(last_updated=datetime.utcnow())

def save_user_preferences(user_id: str, data: UserPreferences) -> bool:
    filepath = _get_user_prefs_path(user_id)
    try:
        json_data = data.model_dump_json(indent=2)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json_data)
        logger.info(f"Saved UserPreferences for user {user_id} to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error saving UserPreferences for user {user_id}: {e}")
        return False

def load_user_preferences(user_id: str) -> UserPreferences:
    """Get the path to the user's preferences file.
    
    Convention: store as user/{user_id}/preferences.json rather than user/{user_id}_preferences.json
    Ensures data is organized by user
    """
    filepath = _get_user_prefs_path(user_id)
    if not filepath.exists():
        logger.info(f"User preferences file for user {user_id} not found at {filepath}, returning default.")
        from datetime import datetime
        default_prefs = UserPreferences(
            last_updated=datetime.utcnow()
        ) # Create default instance with explicit last_updated
        # Optionally save the default for this new user
        # save_user_preferences(user_id, default_prefs)
        return default_prefs
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            json_data = f.read()
        model_instance = UserPreferences.model_validate_json(json_data)
        
        # Ensure last_updated is set
        from datetime import datetime
        if not model_instance.last_updated:
            model_instance.last_updated = datetime.utcnow()
            logger.info(f"Added missing last_updated timestamp to preferences for user {user_id}")
            
        logger.info(f"Loaded UserPreferences for user {user_id} from {filepath}")
        return model_instance
    except Exception as e:
        logger.error(f"Error loading UserPreferences for user {user_id} from {filepath}: {e}. Returning default.")
        from datetime import datetime
        return UserPreferences(last_updated=datetime.utcnow())

# --- Session Data Handling (Needs adjusting filenames) ---

def save_session_data(session_id: str, data: BaseModel, user_id: str = "default_user"):
    """Saves different types of session data based on their model type."""
    if isinstance(data, SessionRawInput):
        filename = f"{user_id}_{session_id}_raw.json"
        repo = session_raw_repo
    elif isinstance(data, SessionStructuredContent):
        filename = f"{user_id}_{session_id}_structured.json"
        repo = session_structured_repo
    elif isinstance(data, SessionConversation):
        filename = f"{user_id}_{session_id}_conversation.json"
        repo = session_conversation_repo
    else:
        logger.error(f"Unsupported session data type: {type(data)}")
        return False
    
    filepath = settings.SESSIONS_DIR / filename
    try:
        json_data = data.model_dump_json(indent=2)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json_data)
        logger.info(f"Saved {type(data).__name__} to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error saving {type(data).__name__} to {filepath}: {e}")
        return False

# Add loading functions for specific session data types if needed later
# def load_session_raw(session_id: str) -> Optional[SessionRawInput]: ... 