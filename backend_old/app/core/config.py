from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Define the base directory of the backend module
_BACKEND_DIR_SENTINEL = Path(__file__).resolve().parent.parent.parent # Corrected: .../backend
# Define the default data directory path relative to the BACKEND_DIR, and resolve it
_DEFAULT_DATA_DIR_IN_BACKEND = (_BACKEND_DIR_SENTINEL / "data").resolve()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Load environment variables from .env file in the project root
        env_file=(_BACKEND_DIR_SENTINEL.parent / ".env"), # .env is in project root
        env_file_encoding='utf-8',
        extra='ignore' # Ignore extra fields from .env not defined here
    )

    # --- Core Settings ---
    PROJECT_NAME: str = "Continual Improvement Tool Backend"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False # Default to False for safety

    # --- Anthropic API Settings ---
    ANTHROPIC_API_KEY: str
    ANTHROPIC_DEFAULT_MODEL: str = "claude-3-7-sonnet-latest"

    # --- Data Storage Settings ---
    # Define base data path, defaulting to an absolute path within backend/data
    DATA_DIR: Path = _DEFAULT_DATA_DIR_IN_BACKEND
    # Define subdirectories based on PRD
    SESSIONS_DIR: Path | None = None
    INSIGHTS_DIR: Path | None = None
    USER_DATA_DIR: Path | None = None

    def __init__(self, **values):
        super().__init__(**values)
        # DATA_DIR is now from an absolute default (within backend) or .env. 
        # Pydantic-settings should handle resolving it if it comes from .env as a relative path.
        # For clarity and safety, we resolve it here too.
        self.DATA_DIR = Path(self.DATA_DIR).resolve()

        # Construct specific data paths using the self.DATA_DIR
        self.SESSIONS_DIR = (self.DATA_DIR / "sessions").resolve()
        self.INSIGHTS_DIR = (self.DATA_DIR / "insights").resolve()
        self.USER_DATA_DIR = (self.DATA_DIR / "user").resolve()
        # Ensure data directories exist
        self._create_data_dirs()

    def _create_data_dirs(self):
        """Creates the necessary data directories if they don't exist."""
        if not self.DATA_DIR.exists():
            self.DATA_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Created data directory: {self.DATA_DIR}")
        if self.SESSIONS_DIR and not self.SESSIONS_DIR.exists():
            self.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Created sessions directory: {self.SESSIONS_DIR}")
        if self.INSIGHTS_DIR and not self.INSIGHTS_DIR.exists():
            self.INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Created insights directory: {self.INSIGHTS_DIR}")
        if self.USER_DATA_DIR and not self.USER_DATA_DIR.exists():
            self.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Created user data directory: {self.USER_DATA_DIR}")

# Create a single instance of the settings to be imported elsewhere
settings = Settings()

# You can optionally print settings on startup for debugging
# if settings.DEBUG:
#    print("--- Application Settings ---")
#    print(settings.model_dump())
#    print("--------------------------")
