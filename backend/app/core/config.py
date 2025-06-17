from pydantic_settings import BaseSettings
from typing import List
import os
import boto3
from functools import lru_cache
from .database_url import get_database_url


@lru_cache(maxsize=1)
def get_anthropic_api_key() -> str:
    """Get Anthropic API key from environment or SSM Parameter Store (cached)"""
    # Try environment variable first (for local development and Lambda)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return api_key
    
    # Try SSM Parameter Store (for Lambda fallback)
    param_name = os.getenv("ANTHROPIC_API_KEY_PARAM")
    if param_name:
        try:
            ssm = boto3.client('ssm', config=boto3.session.Config(
                retries={'max_attempts': 2, 'mode': 'standard'},
                read_timeout=10,
                connect_timeout=5
            ))
            response = ssm.get_parameter(Name=param_name, WithDecryption=True)
            return response['Parameter']['Value']
        except Exception as e:
            print(f"Failed to load API key from SSM: {e}")
            return ""
    
    return ""


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = ""  # Will be set dynamically in Lambda
    
    # Anthropic - loaded on-demand
    ANTHROPIC_DEFAULT_MODEL: str = "claude-sonnet-4-20250514"  # Use Sonnet 4 for everything
    ANTHROPIC_STRUCTURING_MODEL: str = "claude-sonnet-4-20250514"  # Model for LLM analysis tasks
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    
    # Debug mode
    DEBUG: bool = False
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://cassidy-frontend-1748872354.s3-website-us-east-1.amazonaws.com", "http://localhost:3000", "http://localhost:5173", "http://localhost:5174"]
    
    # Application
    APP_NAME: str = "Cassidy AI Journaling Assistant"
    VERSION: str = "2.0.0"
    
    # Additional fields that might be in .env
    APP_ENV: str = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()