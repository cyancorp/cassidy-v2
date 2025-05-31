from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./cassidy.db"
    
    # Anthropic
    ANTHROPIC_API_KEY: str
    ANTHROPIC_DEFAULT_MODEL: str = "claude-3-7-sonnet-latest"
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    
    # Debug mode
    DEBUG: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"]
    
    # Application
    APP_NAME: str = "Cassidy AI Journaling Assistant"
    VERSION: str = "2.0.0"
    
    # Additional fields that might be in .env
    APP_ENV: str = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()