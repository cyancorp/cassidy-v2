import asyncio
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings

engine = None
async_session_maker = None


async def init_db():
    """Initialize database connection and create tables"""
    global engine, async_session_maker
    
    # Get database URL dynamically
    from app.core.database_url import get_database_url
    database_url = get_database_url()
    
    # Create async engine
    if database_url.startswith("sqlite"):
        # SQLite configuration for local development
        engine = create_async_engine(
            database_url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG
        )
    else:
        # PostgreSQL configuration for production
        connect_args = {}
        
        # Add SSL for RDS connections in Lambda
        if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            from app.core.database_url import create_ssl_context
            connect_args["ssl"] = create_ssl_context()
            
        engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=300,  # 5 minutes
            echo=settings.DEBUG,
            connect_args=connect_args
        )
    
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Create all tables
    from app.models.base import Base
    from app.models.user import UserDB, AuthSessionDB, UserPreferencesDB, UserTemplateDB
    from app.models.session import ChatSessionDB, ChatMessageDB, JournalDraftDB, JournalEntryDB
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connection"""
    global engine
    if engine:
        await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    from fastapi import HTTPException
    global engine, async_session_maker
    
    # If engine not initialized (e.g., due to startup failure), try to initialize now
    if engine is None or async_session_maker is None:
        try:
            await init_db()
        except Exception as e:
            print(f"Failed to initialize database in get_db: {e}")
            # Raise HTTPException which FastAPI will handle with CORS headers
            raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        async with async_session_maker() as session:
            try:
                yield session
            finally:
                await session.close()
    except Exception as e:
        print(f"Database session error: {e}")
        raise HTTPException(status_code=503, detail="Database connection error")


async def create_sample_user():
    """Create sample user for development/testing"""
    from app.services.auth import AuthService
    from app.models.api import RegisterRequest
    
    async with async_session_maker() as db:
        auth_service = AuthService(db)
        
        # Check if user already exists
        existing_user = await auth_service.user_repo.get_by_username(db, "user_123")
        if existing_user:
            print("Sample user 'user_123' already exists")
            return existing_user
        
        # Create sample user
        register_request = RegisterRequest(
            username="user_123",
            email="user123@example.com",
            password="1234"
        )
        
        try:
            response = await auth_service.register_user(register_request)
            print(f"Created sample user: username='user_123', password='1234', user_id={response.user_id}")
            return response
        except ValueError as e:
            print(f"Error creating sample user: {e}")
            return None