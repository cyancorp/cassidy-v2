import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings

engine = None
async_session_maker = None


async def init_db():
    """Initialize database connection and create tables"""
    global engine, async_session_maker
    
    # Create async engine
    if settings.DATABASE_URL.startswith("sqlite"):
        # SQLite configuration for local development
        engine = create_async_engine(
            settings.DATABASE_URL,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG
        )
    else:
        # PostgreSQL configuration for production
        engine = create_async_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=300,  # 5 minutes
            echo=settings.DEBUG
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
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


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