# Backend V2 Technical Specification

## Overview

This document specifies the architecture for Cassidy Backend V2, a rebuild focused on:
- Database-backed persistence (replacing JSON file storage)
- AWS Lambda deployment architecture
- Scalable multi-user support
- Enhanced AI agent integration with Pydantic-AI
- Maintained frontend API compatibility

## Core Requirements

### Functional Requirements
1. **Multi-User Journaling System**: Support multiple users with isolated data
2. **AI-Powered Conversation Types**: Extensible conversation types (starting with "journaling")
3. **Structured Content Processing**: AI agent processes raw input into structured journal entries
4. **User Preferences & Templates**: Customizable journaling templates and user preferences
5. **Session Management**: Persistent conversation sessions with message history
6. **Data Export/Import**: User data portability

### Non-Functional Requirements
1. **Serverless Architecture**: AWS Lambda compatible (stateless, cold start optimized)
2. **Database Persistence**: PostgreSQL with connection pooling
3. **API Compatibility**: Maintain existing frontend API contracts
4. **Security**: User data isolation, API authentication ready
5. **Performance**: Sub-2s response times, efficient database queries
6. **Scalability**: Auto-scaling via Lambda, efficient database schema

## Authentication System

### Password Hashing & JWT Service

```python
# app/core/security.py
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from app.core.config import settings

class SecurityService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    @staticmethod
    def create_access_token(user_id: str, username: str, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=24)
        
        payload = {
            "sub": str(user_id),
            "username": username,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """Decode and validate a JWT token"""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

# app/services/auth.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user import UserRepository, AuthSessionRepository
from app.core.security import SecurityService
from app.models.api import LoginRequest, RegisterRequest, LoginResponse, RegisterResponse
from app.models.user import User
from datetime import datetime, timedelta
import hashlib

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository()
        self.auth_session_repo = AuthSessionRepository()
        self.security = SecurityService()
    
    async def register_user(self, request: RegisterRequest) -> RegisterResponse:
        """Register a new user"""
        # Check if username already exists
        existing_user = await self.user_repo.get_by_username(self.db, request.username)
        if existing_user:
            raise ValueError("Username already exists")
        
        # Check if email already exists (if provided)
        if request.email:
            existing_email = await self.user_repo.get_by_email(self.db, request.email)
            if existing_email:
                raise ValueError("Email already exists")
        
        # Hash password and create user
        password_hash = self.security.hash_password(request.password)
        user = await self.user_repo.create_user(
            self.db, 
            username=request.username,
            email=request.email,
            password_hash=password_hash
        )
        
        return RegisterResponse(
            user_id=user.id,
            username=user.username
        )
    
    async def login_user(
        self, 
        request: LoginRequest, 
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> LoginResponse:
        """Authenticate user and create session"""
        # Find user by username
        user = await self.user_repo.get_by_username(self.db, request.username)
        if not user:
            raise ValueError("Invalid credentials")
        
        # Verify password
        if not self.security.verify_password(request.password, user.password_hash):
            raise ValueError("Invalid credentials")
        
        # Create access token
        expires_delta = timedelta(hours=24)
        access_token = self.security.create_access_token(
            user_id=str(user.id),
            username=user.username,
            expires_delta=expires_delta
        )
        
        # Create session record
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()
        expires_at = datetime.utcnow() + expires_delta
        
        await self.auth_session_repo.create_session(
            self.db,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address
        )
        
        return LoginResponse(
            access_token=access_token,
            expires_in=int(expires_delta.total_seconds()),
            user_id=user.id,
            username=user.username
        )
    
    async def logout_user(self, token: str) -> bool:
        """Logout user by revoking session"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return await self.auth_session_repo.revoke_session(self.db, token_hash)
    
    async def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from token"""
        # Decode token
        payload = self.security.decode_token(token)
        if not payload:
            return None
        
        # Check if session is valid
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session = await self.auth_session_repo.get_by_token_hash(self.db, token_hash)
        if not session:
            return None
        
        # Get user
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        return await self.user_repo.get_by_id(self.db, user_id)

### Authentication Middleware

```python
# app/core/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.auth import AuthService
from app.models.user import User
from typing import Optional

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to get current authenticated user"""
    auth_service = AuthService(db)
    user = await auth_service.get_current_user(credentials.credentials)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Optional dependency to get current user (allows anonymous access)"""
    if not credentials:
        return None
    
    auth_service = AuthService(db)
    return await auth_service.get_current_user(credentials.credentials)

### Sample User Creation

```python
# app/core/sample_data.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.auth import AuthService
from app.models.api import RegisterRequest
from app.models.user import UserTemplate, UserPreferences, SectionDetailDef
from app.repositories.user import UserTemplateRepository, UserPreferencesRepository
from datetime import datetime

async def create_sample_user(db: AsyncSession) -> None:
    """Create sample user for development/testing"""
    auth_service = AuthService(db)
    
    # Check if user already exists
    existing_user = await auth_service.user_repo.get_by_username(db, "user_123")
    if existing_user:
        print("Sample user 'user_123' already exists")
        return
    
    # Create sample user
    register_request = RegisterRequest(
        username="user_123",
        email="user123@example.com",
        password="1234"
    )
    
    try:
        response = await auth_service.register_user(register_request)
        user_id = response.user_id
        print(f"Created sample user: username='user_123', password='1234', user_id={user_id}")
        
        # Create sample preferences
        prefs_repo = UserPreferencesRepository()
        sample_prefs = UserPreferences(
            user_id=user_id,
            purpose_statement="General journaling assistance",
            long_term_goals=["Personal growth", "Better self-understanding"],
            known_challenges=["Finding time to reflect"],
            preferred_feedback_style="supportive",
            personal_glossary={"mindfulness": "Being present and aware"}
        )
        await prefs_repo.create(db, **sample_prefs.model_dump(exclude={"id", "created_at", "updated_at"}))
        
        # Create sample template
        template_repo = UserTemplateRepository()
        sample_template = UserTemplate(
            user_id=user_id,
            name="Trading Journal Template",
            sections={
                "Open Reflection": SectionDetailDef(
                    description="General thoughts, daily reflections, or free-form journaling content",
                    aliases=["Daily Notes", "Journal", "Reflection", "General"]
                ),
                "Emotional State": SectionDetailDef(
                    description="Content describing mood, feelings, stress levels, or well-being",
                    aliases=["Mood", "Feelings", "Well-being"]
                ),
                "Trading Journal": SectionDetailDef(
                    description="Details of specific trades made, positions opened or closed",
                    aliases=["Trades", "Positions", "Trading Activity"]
                ),
                "Market Thoughts": SectionDetailDef(
                    description="Broader analysis of market trends, specific assets, macroeconomic views",
                    aliases=["Market Analysis", "Market Commentary", "Asset Analysis"]
                )
            }
        )
        await template_repo.create(db, **sample_template.model_dump(exclude={"id", "created_at", "updated_at"}))
        
        print("Created sample preferences and template for user_123")
        
    except ValueError as e:
        print(f"Error creating sample user: {e}")
```

## Architecture Overview

### Technology Stack
- **Runtime**: Python 3.11+ with FastAPI
- **AI Framework**: Pydantic-AI 0.2.3+ with Anthropic Claude
- **Database**: PostgreSQL (AWS RDS) with SQLAlchemy ORM
- **Deployment**: AWS Lambda with Function URLs
- **Connection Pooling**: SQLAlchemy with pgbouncer
- **Environment**: AWS Systems Manager Parameter Store for secrets

### Deployment Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   AWS Lambda     │    │   AWS RDS       │
│   (React SPA)   │◄──►│   (FastAPI)      │◄──►│   (PostgreSQL)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   Anthropic API  │
                       │   (Claude)       │
                       └──────────────────┘
```

## Database Schema

### Core Tables

#### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
```

#### auth_sessions
```sql
CREATE TABLE auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_agent TEXT,
    ip_address INET,
    INDEX(token_hash),
    INDEX(user_id, expires_at)
);
```

#### user_preferences
```sql
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose_statement TEXT,
    long_term_goals JSONB DEFAULT '[]',
    known_challenges JSONB DEFAULT '[]',
    preferred_feedback_style VARCHAR(50) DEFAULT 'supportive',
    personal_glossary JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);
```

#### user_templates
```sql
CREATE TABLE user_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL DEFAULT 'Default Template',
    sections JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, name)
);
```

#### chat_sessions
```sql
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_type VARCHAR(50) NOT NULL DEFAULT 'journaling',
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### chat_messages
```sql
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    INDEX(session_id, created_at)
);
```

#### journal_drafts
```sql
CREATE TABLE journal_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    draft_data JSONB NOT NULL DEFAULT '{}',
    is_finalized BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(session_id)
);
```

#### journal_entries
```sql
CREATE TABLE journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE SET NULL,
    title VARCHAR(255),
    structured_data JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    INDEX(user_id, created_at DESC)
);
```

## Pydantic Models Architecture

### Core Models

```python
# app/models/base.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID, uuid4

class TimestampedModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# app/models/user.py
class User(TimestampedModel):
    username: str
    email: Optional[str] = None
    password_hash: str
    is_verified: bool = False
    is_active: bool = True

class AuthSession(TimestampedModel):
    user_id: UUID
    token_hash: str
    expires_at: datetime
    is_revoked: bool = False
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

class SectionDetailDef(BaseModel):
    description: str = Field(..., description="Detailed description for the LLM")
    aliases: List[str] = Field(default_factory=list, description="Alternative titles")

class UserPreferences(TimestampedModel):
    user_id: UUID
    purpose_statement: Optional[str] = None
    long_term_goals: List[str] = Field(default_factory=list)
    known_challenges: List[str] = Field(default_factory=list)
    preferred_feedback_style: str = "supportive"
    personal_glossary: Dict[str, str] = Field(default_factory=dict)

class UserTemplate(TimestampedModel):
    user_id: UUID
    name: str = "Default Template"
    sections: Dict[str, SectionDetailDef] = Field(default_factory=dict)
    is_active: bool = True

# app/models/session.py
class ChatSession(TimestampedModel):
    user_id: UUID
    conversation_type: str = "journaling"
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChatMessage(TimestampedModel):
    session_id: UUID
    role: str  # 'user', 'assistant', 'system'
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class JournalDraft(TimestampedModel):
    session_id: UUID
    user_id: UUID
    draft_data: Dict[str, Any] = Field(default_factory=dict)
    is_finalized: bool = False

class JournalEntry(TimestampedModel):
    user_id: UUID
    session_id: Optional[UUID] = None
    title: Optional[str] = None
    structured_data: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)

# app/models/agent.py
class CassidyAgentDependencies(BaseModel):
    user_id: UUID
    session_id: UUID
    conversation_type: str = "journaling"
    user_template: UserTemplate
    user_preferences: UserPreferences
    current_journal_draft: JournalDraft
```

### API Models

```python
# app/models/api.py
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=4, max_length=255)

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: UUID
    username: str

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    password: str = Field(..., min_length=4, max_length=255)

class RegisterResponse(BaseModel):
    user_id: UUID
    username: str
    message: str = "User created successfully"

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class UserProfileResponse(BaseModel):
    user_id: UUID
    username: str
    email: Optional[str]
    is_verified: bool
    created_at: datetime

class AgentChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentChatResponse(BaseModel):
    text: str
    session_id: UUID
    updated_draft_data: Optional[Dict[str, Any]] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CreateSessionRequest(BaseModel):
    conversation_type: str = "journaling"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CreateSessionResponse(BaseModel):
    session_id: UUID
    conversation_type: str
    created_at: datetime

class UserPreferencesUpdate(BaseModel):
    purpose_statement: Optional[str] = None
    long_term_goals: Optional[List[str]] = None
    known_challenges: Optional[List[str]] = None
    preferred_feedback_style: Optional[str] = None
    personal_glossary: Optional[Dict[str, str]] = None

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    sections: Optional[Dict[str, SectionDetailDef]] = None
```

## Database Repository Layer

### Base Repository Pattern

```python
# app/repositories/base.py
from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from app.database import get_db_session
from app.models.base import TimestampedModel

T = TypeVar('T', bound=TimestampedModel)

class BaseRepository(Generic[T]):
    def __init__(self, model_class: Type[T]):
        self.model_class = model_class
    
    async def create(self, db: Session, **kwargs) -> T:
        db_obj = self.model_class(**kwargs)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get_by_id(self, db: Session, id: UUID) -> Optional[T]:
        result = await db.execute(select(self.model_class).where(self.model_class.id == id))
        return result.scalar_one_or_none()
    
    async def get_by_user_id(self, db: Session, user_id: UUID) -> List[T]:
        result = await db.execute(
            select(self.model_class).where(self.model_class.user_id == user_id)
        )
        return result.scalars().all()
    
    async def update(self, db: Session, id: UUID, **kwargs) -> Optional[T]:
        kwargs['updated_at'] = datetime.utcnow()
        await db.execute(
            update(self.model_class).where(self.model_class.id == id).values(**kwargs)
        )
        await db.commit()
        return await self.get_by_id(db, id)
    
    async def delete(self, db: Session, id: UUID) -> bool:
        result = await db.execute(
            delete(self.model_class).where(self.model_class.id == id)
        )
        await db.commit()
        return result.rowcount > 0

# app/repositories/user.py
class UserRepository(BaseRepository[User]):
    async def get_by_username(self, db: Session, username: str) -> Optional[User]:
        result = await db.execute(
            select(User).where(User.username == username, User.is_active == True)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, db: Session, email: str) -> Optional[User]:
        result = await db.execute(
            select(User).where(User.email == email, User.is_active == True)
        )
        return result.scalar_one_or_none()
    
    async def create_user(self, db: Session, username: str, email: Optional[str], password_hash: str) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

class AuthSessionRepository(BaseRepository[AuthSession]):
    async def get_by_token_hash(self, db: Session, token_hash: str) -> Optional[AuthSession]:
        result = await db.execute(
            select(AuthSession)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.expires_at > datetime.utcnow(),
                AuthSession.is_revoked == False
            )
        )
        return result.scalar_one_or_none()
    
    async def create_session(
        self, 
        db: Session, 
        user_id: UUID, 
        token_hash: str, 
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AuthSession:
        session = AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session
    
    async def revoke_session(self, db: Session, token_hash: str) -> bool:
        result = await db.execute(
            update(AuthSession)
            .where(AuthSession.token_hash == token_hash)
            .values(is_revoked=True)
        )
        await db.commit()
        return result.rowcount > 0
    
    async def revoke_all_user_sessions(self, db: Session, user_id: UUID) -> int:
        result = await db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.is_revoked == False)
            .values(is_revoked=True)
        )
        await db.commit()
        return result.rowcount

class UserPreferencesRepository(BaseRepository[UserPreferences]):
    async def get_by_user_id(self, db: Session, user_id: UUID) -> Optional[UserPreferences]:
        result = await db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        return result.scalar_one_or_none()

class UserTemplateRepository(BaseRepository[UserTemplate]):
    async def get_active_by_user_id(self, db: Session, user_id: UUID) -> Optional[UserTemplate]:
        result = await db.execute(
            select(UserTemplate)
            .where(UserTemplate.user_id == user_id, UserTemplate.is_active == True)
            .limit(1)
        )
        return result.scalar_one_or_none()

# app/repositories/session.py
class ChatSessionRepository(BaseRepository[ChatSession]):
    async def get_active_sessions(self, db: Session, user_id: UUID) -> List[ChatSession]:
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.is_active == True)
            .order_by(ChatSession.updated_at.desc())
        )
        return result.scalars().all()

class JournalDraftRepository(BaseRepository[JournalDraft]):
    async def get_by_session_id(self, db: Session, session_id: UUID) -> Optional[JournalDraft]:
        result = await db.execute(
            select(JournalDraft).where(JournalDraft.session_id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def finalize_draft(self, db: Session, session_id: UUID) -> Optional[JournalEntry]:
        # Get the draft
        draft = await self.get_by_session_id(db, session_id)
        if not draft:
            return None
        
        # Create journal entry
        entry = JournalEntry(
            user_id=draft.user_id,
            session_id=draft.session_id,
            structured_data=draft.draft_data,
            title=self._generate_title(draft.draft_data)
        )
        db.add(entry)
        
        # Mark draft as finalized
        await self.update(db, draft.id, is_finalized=True)
        
        await db.commit()
        await db.refresh(entry)
        return entry
```

## AWS Lambda Architecture

### Lambda Function Structure

```python
# lambda_function.py
import json
import asyncio
from mangum import Mangum
from app.main import app

# Lambda handler
handler = Mangum(app, lifespan="off")

def lambda_handler(event, context):
    """AWS Lambda entry point"""
    return handler(event, context)

# app/main.py
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from app.database import init_db, close_db
from app.core.config import settings
from app.api.v1.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()

app = FastAPI(
    title="Cassidy AI Journaling Assistant",
    version="2.0.0",
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api/v1")

# Health check for Lambda
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

### Database Connection Management

```python
# app/database.py
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings

engine = None
async_session_maker = None

async def init_db():
    global engine, async_session_maker
    
    # Connection string from environment/parameter store
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=StaticPool,
        pool_pre_ping=True,
        pool_recycle=300,  # 5 minutes
        connect_args={"connect_timeout": 10}
    )
    
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

async def close_db():
    global engine
    if engine:
        await engine.dispose()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
```

### Configuration Management

```python
# app/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional
import boto3
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # Anthropic
    ANTHROPIC_API_KEY: str
    ANTHROPIC_DEFAULT_MODEL: str = "claude-3-7-sonnet-latest"
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    
    # Lambda specific
    AWS_REGION: str = "us-east-1"
    LAMBDA_FUNCTION_NAME: Optional[str] = None
    
    # Debug mode
    DEBUG: bool = False
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]
    
    class Config:
        env_file = ".env"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load sensitive values from Parameter Store in production
        if self.LAMBDA_FUNCTION_NAME or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
            self._load_from_parameter_store()
    
    def _load_from_parameter_store(self):
        try:
            ssm = boto3.client('ssm', region_name=self.AWS_REGION)
            
            parameters = [
                '/cassidy/database-url',
                '/cassidy/anthropic-api-key',
                '/cassidy/jwt-secret-key'
            ]
            
            response = ssm.get_parameters(Names=parameters, WithDecryption=True)
            
            for param in response['Parameters']:
                if param['Name'] == '/cassidy/database-url':
                    self.DATABASE_URL = param['Value']
                elif param['Name'] == '/cassidy/anthropic-api-key':
                    self.ANTHROPIC_API_KEY = param['Value']
                elif param['Name'] == '/cassidy/jwt-secret-key':
                    self.JWT_SECRET_KEY = param['Value']
        except Exception as e:
            # In development, silently fail and use environment variables
            if self.DEBUG:
                print(f"Failed to load from Parameter Store: {e}")

settings = Settings()
```

## AI Agent Integration

### Enhanced Agent Factory

```python
# app/agents/factory.py
from typing import Optional
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from app.models.agent import CassidyAgentDependencies
from app.agents.tools import get_tools_for_conversation_type
from app.core.config import settings

class AgentFactory:
    _agents: dict[str, Agent] = {}
    
    @classmethod
    async def get_agent(cls, conversation_type: str = "journaling") -> Agent:
        """Get or create agent for conversation type"""
        if conversation_type not in cls._agents:
            cls._agents[conversation_type] = await cls._create_agent(conversation_type)
        return cls._agents[conversation_type]
    
    @classmethod
    async def _create_agent(cls, conversation_type: str) -> Agent:
        """Create new agent instance"""
        provider = AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
        model = AnthropicModel(settings.ANTHROPIC_DEFAULT_MODEL, provider=provider)
        
        tools = get_tools_for_conversation_type(conversation_type)
        system_prompt = cls._get_system_prompt(conversation_type)
        
        agent = Agent(
            model,
            tools=tools,
            system_prompt=system_prompt,
            debug=settings.DEBUG
        )
        
        return agent
    
    @classmethod
    def _get_system_prompt(cls, conversation_type: str) -> str:
        """Get system prompt for conversation type"""
        if conversation_type == "journaling":
            return """
You are Cassidy, an AI journaling assistant. Help users structure their thoughts 
into their personal journal template sections. Always use the provided tools to 
process user input and save journal entries when requested.

Key behaviors:
1. Use StructureJournalTool for any journal content
2. Use SaveJournal when user wants to save/finalize
3. Use UpdatePreferences for preference updates
4. Be encouraging and supportive
5. Guide users through their template sections
"""
        return "You are Cassidy, a helpful AI assistant."

# app/agents/service.py
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.factory import AgentFactory
from app.models.agent import CassidyAgentDependencies
from app.repositories.user import UserPreferencesRepository, UserTemplateRepository
from app.repositories.session import JournalDraftRepository

class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_prefs_repo = UserPreferencesRepository()
        self.user_template_repo = UserTemplateRepository()
        self.journal_draft_repo = JournalDraftRepository()
    
    async def create_agent_context(
        self, 
        user_id: UUID, 
        session_id: UUID,
        conversation_type: str = "journaling"
    ) -> CassidyAgentDependencies:
        """Create agent context with user data"""
        
        # Load user data
        user_prefs = await self.user_prefs_repo.get_by_user_id(self.db, user_id)
        user_template = await self.user_template_repo.get_active_by_user_id(self.db, user_id)
        journal_draft = await self.journal_draft_repo.get_by_session_id(self.db, session_id)
        
        # Create defaults if needed
        if not user_prefs:
            user_prefs = await self._create_default_preferences(user_id)
        if not user_template:
            user_template = await self._create_default_template(user_id)
        if not journal_draft:
            journal_draft = await self.journal_draft_repo.create(
                self.db, user_id=user_id, session_id=session_id
            )
        
        return CassidyAgentDependencies(
            user_id=user_id,
            session_id=session_id,
            conversation_type=conversation_type,
            user_template=user_template,
            user_preferences=user_prefs,
            current_journal_draft=journal_draft
        )
```

### Conversation Type System

```python
# app/agents/conversation_types.py
from enum import Enum
from typing import Protocol, List
from pydantic_ai.tools import Tool

class ConversationType(str, Enum):
    JOURNALING = "journaling"
    GENERAL = "general"
    REFLECTION = "reflection"

class ConversationHandler(Protocol):
    """Protocol for conversation type handlers"""
    
    def get_tools(self) -> List[Tool]:
        """Get tools for this conversation type"""
        ...
    
    def get_system_prompt_addition(self) -> str:
        """Get additional system prompt content"""
        ...
    
    def get_dynamic_instructions(self, context) -> str:
        """Get dynamic instructions based on context"""
        ...

# app/agents/handlers/journaling.py
class JournalingHandler:
    def get_tools(self) -> List[Tool]:
        from app.agents.tools.journaling import (
            StructureJournalTool,
            SaveJournalTool,
            UpdatePreferencesTool
        )
        return [StructureJournalTool, SaveJournalTool, UpdatePreferencesTool]
    
    def get_system_prompt_addition(self) -> str:
        return """
        JOURNALING MODE: You are helping the user with structured journaling.
        Always use StructureJournalTool to process journal content.
        Use SaveJournal when the user wants to save their entry.
        """
    
    def get_dynamic_instructions(self, context: CassidyAgentDependencies) -> str:
        sections = list(context.user_template.sections.keys())
        filled_sections = [s for s in sections if s in context.current_journal_draft.draft_data]
        unfilled_sections = [s for s in sections if s not in filled_sections]
        
        if unfilled_sections:
            return f"Guide the user to fill these sections: {', '.join(unfilled_sections)}"
        else:
            return "All sections filled. Ask if they want to save or add more content."
```

## API Layer

### Authentication Endpoints

```python
# app/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.auth import AuthService
from app.models.api import (
    LoginRequest, LoginResponse, 
    RegisterRequest, RegisterResponse,
    UserProfileResponse
)
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/register", response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    auth_service = AuthService(db)
    try:
        return await auth_service.register_user(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return access token"""
    auth_service = AuthService(db)
    
    # Extract user agent and IP
    user_agent = http_request.headers.get("user-agent")
    ip_address = http_request.client.host if http_request.client else None
    
    try:
        return await auth_service.login_user(request, user_agent, ip_address)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout current user"""
    # Note: In a real implementation, you'd extract the token from the request
    # and pass it to logout_user. This is simplified for the spec.
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile"""
    return UserProfileResponse(
        user_id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at
    )
```

### Enhanced Endpoints

```python
# app/api/v1/endpoints/agent.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.database import get_db
from app.models.api import AgentChatRequest, AgentChatResponse
from app.agents.service import AgentService
from app.agents.factory import AgentFactory
from app.repositories.session import ChatSessionRepository, ChatMessageRepository

router = APIRouter()

@router.post("/chat/{session_id}", response_model=AgentChatResponse)
async def agent_chat(
    session_id: UUID,
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user),  # Auth dependency
    db: AsyncSession = Depends(get_db)
):
    """Main agent chat endpoint"""
    
    # Verify session belongs to user
    session_repo = ChatSessionRepository()
    session = await session_repo.get_by_id(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Create agent service and context
    agent_service = AgentService(db)
    context = await agent_service.create_agent_context(
        current_user.id, session_id, session.conversation_type
    )
    
    # Get agent for conversation type
    agent = await AgentFactory.get_agent(session.conversation_type)
    
    # Load message history
    message_repo = ChatMessageRepository()
    message_history = await message_repo.get_by_session_id(db, session_id)
    
    # Run agent
    result = await agent.run(
        request.text,
        context=context,
        message_history=[msg.to_pydantic_message() for msg in message_history]
    )
    
    # Save messages
    await message_repo.create(db, session_id=session_id, role="user", content=request.text)
    await message_repo.create(db, session_id=session_id, role="assistant", content=result.output)
    
    # Get updated draft data
    updated_draft = await agent_service.journal_draft_repo.get_by_session_id(db, session_id)
    
    return AgentChatResponse(
        text=result.output,
        session_id=session_id,
        updated_draft_data=updated_draft.draft_data if updated_draft else None,
        tool_calls=[call.model_dump() for call in result.all_tool_calls()],
        metadata={"usage": result.usage.model_dump() if result.usage else {}}
    )

# app/api/v1/endpoints/sessions.py
@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new chat session"""
    session_repo = ChatSessionRepository()
    session = await session_repo.create(
        db,
        user_id=current_user_id,
        conversation_type=request.conversation_type,
        metadata=request.metadata
    )
    
    return CreateSessionResponse(
        session_id=session.id,
        conversation_type=session.conversation_type,
        created_at=session.created_at
    )

@router.get("/sessions", response_model=List[ChatSession])
async def list_sessions(
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's chat sessions"""
    session_repo = ChatSessionRepository()
    return await session_repo.get_active_sessions(db, current_user_id)
```

## Frontend API Compatibility

### Maintained Endpoints

The following endpoints maintain backward compatibility:

1. **GET /api/v1/user/preferences** - Returns user preferences
2. **POST /api/v1/user/preferences** - Updates user preferences  
3. **GET /api/v1/user/template** - Returns user template
4. **POST /api/v1/user/template** - Updates user template
5. **POST /api/v1/agent/chat/{session_id}** - Agent chat (enhanced)

### Enhanced Response Formats

```json
// Agent Chat Response (enhanced)
{
  "text": "Agent response text",
  "session_id": "uuid",
  "updated_draft_data": {
    "Events": "Today I...",
    "Thoughts": "I think...",
    "Feelings": "I feel..."
  },
  "tool_calls": [
    {
      "name": "StructureJournalTool", 
      "input": {"user_text": "..."}, 
      "output": {"status": "success"}
    }
  ],
  "metadata": {
    "usage": {"tokens": 150},
    "processing_time_ms": 1200
  }
}
```

## Testing Strategy

### Test Architecture

The testing strategy focuses on API integration tests that simulate real frontend interactions, ensuring the complete user journey works end-to-end.

### Test Setup & Fixtures

```python
# tests/conftest.py
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import get_db
from app.core.sample_data import create_sample_user
from app.models.user import User
from app.services.auth import AuthService
from app.models.api import LoginRequest

# Test database URL (in-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def test_db():
    """Create test database and return session"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession)
    
    async with async_session_maker() as session:
        # Create sample user
        await create_sample_user(session)
        yield session
    
    await engine.dispose()

@pytest.fixture
async def authenticated_client(test_db):
    """Create authenticated HTTP client with test user token"""
    
    # Override the database dependency
    async def get_test_db():
        yield test_db
    
    app.dependency_overrides[get_db] = get_test_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Login as test user
        login_response = await client.post("/api/v1/auth/login", json={
            "username": "user_123",
            "password": "1234"
        })
        
        assert login_response.status_code == 200
        token_data = login_response.json()
        access_token = token_data["access_token"]
        
        # Set authorization header for future requests
        client.headers.update({"Authorization": f"Bearer {access_token}"})
        
        yield client, token_data
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.fixture
async def journal_session(authenticated_client):
    """Create a journal session for testing"""
    client, token_data = authenticated_client
    
    # Create new journal session
    session_response = await client.post("/api/v1/sessions", json={
        "conversation_type": "journaling"
    })
    
    assert session_response.status_code == 200
    session_data = session_response.json()
    
    return client, token_data, session_data["session_id"]
```

### Authentication Tests

```python
# tests/test_auth.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_user():
    """Test user registration"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert "user_id" in data

@pytest.mark.asyncio
async def test_login_success(test_db):
    """Test successful login"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={
            "username": "user_123",
            "password": "1234"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "user_123"
        assert data["token_type"] == "bearer"
        assert "access_token" in data
        assert data["expires_in"] > 0

@pytest.mark.asyncio
async def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={
            "username": "user_123",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_user_profile(authenticated_client):
    """Test getting current user profile"""
    client, token_data = authenticated_client
    
    response = await client.get("/api/v1/auth/me")
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "user_123"
    assert data["user_id"] == token_data["user_id"]
```

### Session Management Tests

```python
# tests/test_sessions.py
import pytest

@pytest.mark.asyncio
async def test_create_journal_session(authenticated_client):
    """Test creating a new journal session"""
    client, token_data = authenticated_client
    
    response = await client.post("/api/v1/sessions", json={
        "conversation_type": "journaling",
        "metadata": {"test": "data"}
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_type"] == "journaling"
    assert "session_id" in data
    assert "created_at" in data

@pytest.mark.asyncio
async def test_list_user_sessions(authenticated_client):
    """Test listing user's sessions"""
    client, token_data = authenticated_client
    
    # Create a few sessions
    for i in range(3):
        await client.post("/api/v1/sessions", json={
            "conversation_type": "journaling"
        })
    
    # List sessions
    response = await client.get("/api/v1/sessions")
    
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) >= 3
    assert all(session["conversation_type"] == "journaling" for session in sessions)
```

### End-to-End Journaling Workflow Tests

```python
# tests/test_journaling_workflow.py
import pytest
import asyncio

@pytest.mark.asyncio
async def test_complete_journaling_workflow_sad_entry(journal_session, test_db):
    """
    Test complete journaling workflow:
    1. User says 'create a journal entry to say i'm sad'
    2. Agent prompts for more info
    3. User provides more details
    4. User says 'save the journal'
    5. Verify journal entry is saved in database
    """
    client, token_data, session_id = journal_session
    
    # Step 1: Initial sad journal entry
    response1 = await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "create a journal entry to say i'm sad"
    })
    
    assert response1.status_code == 200
    data1 = response1.json()
    
    # Agent should respond and structure the content
    assert "sad" in data1["text"].lower()
    assert data1["updated_draft_data"] is not None
    assert len(data1["updated_draft_data"]) > 0
    
    # Verify StructureJournalTool was called
    tool_calls = data1.get("tool_calls", [])
    structure_calls = [call for call in tool_calls if call["name"] == "StructureJournalTool"]
    assert len(structure_calls) > 0
    
    # Step 2: Agent should prompt for more information
    assert any(keyword in data1["text"].lower() for keyword in [
        "more", "tell me", "expand", "why", "what", "how", "feel"
    ])
    
    # Step 3: User provides more details
    response2 = await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "I'm sad because I lost money in the stock market today. The market dropped 3% and my portfolio is down $5000."
    })
    
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Draft should be updated with more content
    assert data2["updated_draft_data"] is not None
    draft_content = str(data2["updated_draft_data"])
    assert "stock market" in draft_content.lower()
    assert "5000" in draft_content or "$5000" in draft_content
    
    # Step 4: User requests to save
    response3 = await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "save the journal"
    })
    
    assert response3.status_code == 200
    data3 = response3.json()
    
    # Verify SaveJournal tool was called
    tool_calls = data3.get("tool_calls", [])
    save_calls = [call for call in tool_calls if call["name"] == "SaveJournal"]
    assert len(save_calls) > 0
    
    # Agent should confirm save
    assert any(keyword in data3["text"].lower() for keyword in [
        "saved", "finalized", "saved successfully"
    ])
    
    # Step 5: Verify journal entry exists in database
    from app.repositories.session import JournalDraftRepository
    from app.models.session import JournalEntry
    from sqlalchemy import select
    
    # Check if journal entry was created
    result = await test_db.execute(
        select(JournalEntry).where(JournalEntry.session_id == session_id)
    )
    journal_entry = result.scalar_one_or_none()
    
    assert journal_entry is not None
    assert journal_entry.user_id == token_data["user_id"]
    assert "sad" in str(journal_entry.structured_data).lower()
    assert "stock market" in str(journal_entry.structured_data).lower()

@pytest.mark.asyncio
async def test_journaling_workflow_with_template_sections(journal_session, test_db):
    """
    Test that journal entries are properly structured according to user template
    """
    client, token_data, session_id = journal_session
    
    # Send content that should map to multiple template sections
    response = await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "Today I'm feeling anxious about my trading performance. I bought 100 shares of AAPL at $150 and sold at $145, losing $500. The market seems bearish and I think we might see more downside."
    })
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that content was structured into appropriate sections
    draft_data = data["updated_draft_data"]
    assert draft_data is not None
    
    # Should have multiple sections based on our sample template
    assert len(draft_data) > 1
    
    # Check for specific section mapping
    sections = list(draft_data.keys())
    expected_sections = ["Emotional State", "Trading Journal", "Market Thoughts"]
    
    # At least some of the expected sections should be present
    assert any(section in sections for section in expected_sections)
    
    # Verify content mapping
    all_content = str(draft_data).lower()
    assert "anxious" in all_content
    assert "aapl" in all_content
    assert "500" in all_content
    assert "bearish" in all_content

@pytest.mark.asyncio
async def test_journaling_workflow_rejection_and_retry(journal_session):
    """
    Test workflow when user initially doesn't want to save, then changes mind
    """
    client, token_data, session_id = journal_session
    
    # Add some journal content
    await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "I had a good day today, feeling optimistic about my investments"
    })
    
    # User initially doesn't want to save
    response1 = await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "no don't save it yet, I want to add more"
    })
    
    assert response1.status_code == 200
    data1 = response1.json()
    
    # Should not have SaveJournal tool calls
    tool_calls = data1.get("tool_calls", [])
    save_calls = [call for call in tool_calls if call["name"] == "SaveJournal"]
    assert len(save_calls) == 0
    
    # Add more content
    await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "Actually, I also want to mention that I learned about a new trading strategy today"
    })
    
    # Now user wants to save
    response2 = await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "ok now save it"
    })
    
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Should have SaveJournal tool call
    tool_calls = data2.get("tool_calls", [])
    save_calls = [call for call in tool_calls if call["name"] == "SaveJournal"]
    assert len(save_calls) > 0

@pytest.mark.asyncio
async def test_multiple_journal_entries_same_session(journal_session, test_db):
    """
    Test creating multiple journal entries in the same session
    """
    client, token_data, session_id = journal_session
    
    # First journal entry
    await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "Morning reflection: I'm excited about today's trading opportunities"
    })
    
    await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "save this entry"
    })
    
    # Second journal entry
    await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "Evening reflection: The market was volatile today but I managed my positions well"
    })
    
    response = await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "save this one too"
    })
    
    assert response.status_code == 200
    
    # Verify both entries exist in database
    from app.models.session import JournalEntry
    from sqlalchemy import select
    
    result = await test_db.execute(
        select(JournalEntry).where(JournalEntry.session_id == session_id)
    )
    journal_entries = result.scalars().all()
    
    assert len(journal_entries) >= 2
    
    # Check content
    all_content = " ".join([str(entry.structured_data) for entry in journal_entries])
    assert "morning" in all_content.lower()
    assert "evening" in all_content.lower()
    assert "excited" in all_content.lower()
    assert "volatile" in all_content.lower()
```

### Performance & Load Tests

```python
# tests/test_performance.py
import pytest
import asyncio
import time

@pytest.mark.asyncio
async def test_agent_response_time(journal_session):
    """Test that agent responses are within acceptable time limits"""
    client, token_data, session_id = journal_session
    
    start_time = time.time()
    
    response = await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": "I want to journal about my day"
    })
    
    end_time = time.time()
    response_time = end_time - start_time
    
    assert response.status_code == 200
    assert response_time < 5.0  # Should respond within 5 seconds
    
    # Check if response time metadata is included
    data = response.json()
    if "metadata" in data and "processing_time_ms" in data["metadata"]:
        processing_time_ms = data["metadata"]["processing_time_ms"]
        assert processing_time_ms < 5000  # Less than 5 seconds in milliseconds

@pytest.mark.asyncio
async def test_concurrent_users(test_db):
    """Test multiple users journaling concurrently"""
    
    async def create_user_and_journal(username: str, content: str):
        # Create user
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Register
            await client.post("/api/v1/auth/register", json={
                "username": username,
                "password": "testpass"
            })
            
            # Login
            login_response = await client.post("/api/v1/auth/login", json={
                "username": username,
                "password": "testpass"
            })
            
            token = login_response.json()["access_token"]
            client.headers.update({"Authorization": f"Bearer {token}"})
            
            # Create session
            session_response = await client.post("/api/v1/sessions", json={
                "conversation_type": "journaling"
            })
            session_id = session_response.json()["session_id"]
            
            # Send journal content
            journal_response = await client.post(f"/api/v1/agent/chat/{session_id}", json={
                "text": content
            })
            
            return journal_response.status_code == 200
    
    # Create multiple concurrent users
    tasks = [
        create_user_and_journal(f"user_{i}", f"Journal entry {i}: I'm feeling great today!")
        for i in range(5)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # All requests should succeed
    assert all(results)
```

### Error Handling Tests

```python
# tests/test_error_handling.py
import pytest

@pytest.mark.asyncio
async def test_unauthorized_access():
    """Test that unauthorized requests are rejected"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/sessions", json={
            "conversation_type": "journaling"
        })
        
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_invalid_session_id(authenticated_client):
    """Test chat request with invalid session ID"""
    client, token_data = authenticated_client
    
    response = await client.post("/api/v1/agent/chat/invalid-session-id", json={
        "text": "test message"
    })
    
    assert response.status_code == 422  # Invalid UUID format

@pytest.mark.asyncio
async def test_chat_with_nonexistent_session(authenticated_client):
    """Test chat request with valid but nonexistent session ID"""
    client, token_data = authenticated_client
    
    fake_session_id = "12345678-1234-5678-9012-123456789012"
    response = await client.post(f"/api/v1/agent/chat/{fake_session_id}", json={
        "text": "test message"
    })
    
    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_very_long_input(journal_session):
    """Test handling of very long user input"""
    client, token_data, session_id = journal_session
    
    # Create very long input (over 10k characters)
    long_text = "I am journaling today. " * 500
    
    response = await client.post(f"/api/v1/agent/chat/{session_id}", json={
        "text": long_text
    })
    
    assert response.status_code == 422  # Should be rejected due to max_length validation
```

### Test Configuration

```python
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
asyncio_mode = auto
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests

# requirements-test.txt
pytest==7.4.0
pytest-asyncio==0.21.0
httpx==0.24.1
pytest-mock==3.11.1
pytest-cov==4.1.0
```

### Running Tests

```bash
# Run all tests
pytest

# Run only authentication tests
pytest tests/test_auth.py

# Run only journaling workflow tests
pytest tests/test_journaling_workflow.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run integration tests only
pytest -m integration

# Run tests excluding slow ones
pytest -m "not slow"
```

### CI/CD Integration

```yaml
# Add to .github/workflows/deploy.yml before deployment
- name: Run tests
  run: |
    pip install -r requirements-test.txt
    pytest --cov=app --cov-fail-under=80
    
- name: Run integration tests
  run: |
    pytest tests/test_journaling_workflow.py -v
```

### Test Data Validation

The tests validate:

1. **Authentication Flow**: Registration, login, token validation
2. **Session Management**: Creating sessions, listing user sessions
3. **Complete Journaling Workflow**: 
   - User expresses desire to journal
   - Agent structures content using tools
   - Agent prompts for more information
   - User provides additional details
   - User requests to save
   - System saves to database correctly
4. **Template Section Mapping**: Content gets structured into correct template sections
5. **Error Handling**: Unauthorized access, invalid inputs, nonexistent resources
6. **Performance**: Response times under acceptable limits
7. **Concurrency**: Multiple users can journal simultaneously
8. **Data Persistence**: Journal entries are correctly saved and retrievable from database

These tests ensure the API behaves exactly as the frontend expects, validating the complete user journey from authentication through journal creation and persistence.

## Migration Strategy

### Phase 1: Database Setup
1. Create AWS infrastructure (RDS, Lambda, VPC)
2. Run database migrations
3. Set up Parameter Store secrets

### Phase 2: Core Services Migration  
1. Migrate user preferences and templates
2. Implement session management
3. Test basic agent functionality

### Phase 3: Enhanced Features
1. Add conversation types system
2. Implement advanced tools
3. Performance optimization

### Phase 4: Production Deployment
1. Full data migration from JSON files
2. Frontend integration testing
3. Production deployment

## Performance Considerations

### Lambda Optimizations
- Use provisioned concurrency for consistent performance
- Implement connection pooling with pgbouncer
- Optimize cold start times with slim dependencies

### Database Optimizations
- Index on frequently queried columns (user_id, session_id, created_at)
- Use JSONB indexes for structured_data queries
- Implement read replicas for scaling

### Caching Strategy
- Cache user preferences and templates in memory
- Use Lambda environment variables for configuration
- Implement Redis for session state if needed

## Security Considerations

### Authentication & Authorization
- JWT-based authentication (ready for integration)
- User data isolation at database level  
- API rate limiting per user

### Data Protection
- Encrypt sensitive data at rest
- Use AWS Parameter Store for secrets
- Implement audit logging for sensitive operations

## Monitoring & Observability

### Metrics
- Lambda performance metrics (duration, errors, cold starts)
- Database performance (connection count, query time)
- Agent performance (response time, tool usage)

### Logging
- Structured logging with correlation IDs
- Agent conversation logging for debugging
- Error tracking with stack traces

### Alerts
- High error rates
- Database connection issues
- Agent timeout/failures

This specification provides a comprehensive foundation for rebuilding the Cassidy backend with enterprise-grade architecture suitable for AWS Lambda deployment while maintaining frontend compatibility.

## Implementation Requirements

### Data Structure Migration from backend_old

#### Reference Data Structures
The existing backend contains JSON files that define the data structures to be migrated:

**User Preferences Structure** (from `backend_old/data/user_123/preferences.json`):
```json
{
  "purpose_statement": "string",
  "long_term_goals": ["string", "string"],
  "known_challenges": ["string", "string"],
  "preferred_feedback_style": "supportive|direct|encouraging",
  "personal_glossary": {
    "term": "definition"
  }
}
```

**User Template Structure** (from `backend_old/data/user_123/template.json`):
```json
{
  "name": "Trading Journal Template",
  "sections": {
    "Section Name": {
      "description": "Detailed description for LLM to understand section purpose",
      "aliases": ["Alternative Name 1", "Alternative Name 2"]
    }
  }
}
```

**Journal Session Structure** (from `backend_old/data/sessions/*.json`):
```json
{
  "session_id": "timestamp_structured",
  "conversation_type": "journaling",
  "messages": [
    {
      "role": "user|assistant|system",
      "content": "message text",
      "timestamp": "ISO datetime"
    }
  ],
  "structured_journal_data": {
    "Section Name": "content for this section",
    "Another Section": "content for this section"
  },
  "is_finalized": false
}
```

#### Migration Strategy Details
1. **User Data Migration**: Extract preferences and templates from `backend_old/data/user_123/`
2. **Session Data Migration**: Convert session JSON files to chat_sessions + chat_messages + journal_drafts
3. **Finalized Entries**: Sessions with `is_finalized: true` become journal_entries

### SQLAlchemy ORM Requirements

#### Base Model Requirements
```python
# Functional requirement: All database models must inherit from Base
# Must include: created_at, updated_at timestamps
# Must use UUID primary keys with gen_random_uuid()
# Must support async operations with AsyncSession
```

#### Required Database Models
1. **UserDB** - Maps to `users` table
2. **AuthSessionDB** - Maps to `auth_sessions` table  
3. **UserPreferencesDB** - Maps to `user_preferences` table
4. **UserTemplateDB** - Maps to `user_templates` table
5. **ChatSessionDB** - Maps to `chat_sessions` table
6. **ChatMessageDB** - Maps to `chat_messages` table
7. **JournalDraftDB** - Maps to `journal_drafts` table
8. **JournalEntryDB** - Maps to `journal_entries` table

### AI Agent Tools Functional Specifications

#### StructureJournalTool
**Purpose**: Process user input and structure it into user's template sections
**Input**: 
- `user_text`: Raw user input string
- Context includes: user_template, current_journal_draft
**Output**:
- Updates current_journal_draft.draft_data with structured content
- Returns sections that were updated
**Logic**: Map user input to appropriate template sections based on content and section descriptions

#### SaveJournalTool  
**Purpose**: Finalize current journal draft into a permanent journal entry
**Input**:
- Context includes: current_journal_draft, session_id, user_id
**Output**:
- Creates new JournalEntry from draft_data
- Marks JournalDraft as finalized
- Clears draft_data for new entry
**Logic**: Only save if draft_data is not empty

#### UpdatePreferencesTool
**Purpose**: Update user preferences based on conversation
**Input**:
- `preference_updates`: Dict of preference fields to update
**Output**:
- Updates UserPreferences record
- Returns confirmation of changes
**Logic**: Merge updates with existing preferences

#### Tool Factory Function
```python
def get_tools_for_conversation_type(conversation_type: str) -> List[Tool]:
    """Return appropriate tools for conversation type"""
    # "journaling" -> [StructureJournalTool, SaveJournalTool, UpdatePreferencesTool]
    # "general" -> []
    # Default: []
```

### Missing Repository Methods

#### AgentService Missing Methods
```python
async def _create_default_preferences(self, user_id: UUID) -> UserPreferences:
    """Create default preferences for new user"""
    # Default values: purpose_statement=None, preferred_feedback_style="supportive"

async def _create_default_template(self, user_id: UUID) -> UserTemplate:
    """Create default template with basic sections"""
    # Default sections: "General Reflection", "Daily Events", "Thoughts & Feelings"
```

#### JournalDraftRepository Missing Methods
```python
def _generate_title(self, draft_data: Dict[str, Any]) -> str:
    """Generate title from draft content"""
    # Logic: Take first 50 chars of first non-empty section, or "Journal Entry - {date}"
```

#### ChatMessageRepository (Missing Class)
```python
class ChatMessageRepository(BaseRepository[ChatMessage]):
    async def get_by_session_id(self, db: Session, session_id: UUID) -> List[ChatMessage]:
        """Get all messages for a session ordered by created_at"""
    
    def to_pydantic_message(self, message: ChatMessage) -> dict:
        """Convert ChatMessage to pydantic-ai message format"""
        # Return: {"role": message.role, "content": message.content}
```

### Frontend Compatibility Endpoints

#### User Preferences Endpoints
```python
# GET /api/v1/user/preferences
# Response: UserPreferences model (current user's preferences)

# POST /api/v1/user/preferences  
# Request: UserPreferencesUpdate model
# Response: Updated UserPreferences model
```

#### User Template Endpoints
```python
# GET /api/v1/user/template
# Response: UserTemplate model (active template for current user)

# POST /api/v1/user/template
# Request: TemplateUpdate model  
# Response: Updated UserTemplate model
```

### API Router Structure

#### Required Router Setup
```python
# app/api/v1/api.py must combine all endpoint routers:
# - auth.router (prefix="/auth")
# - agent.router (prefix="/agent") 
# - sessions.router (prefix="/sessions")
# - users.router (prefix="/user") # For preferences/template endpoints
```

#### Missing User Endpoints Router
```python
# app/api/v1/endpoints/users.py
# Must include preferences and template CRUD endpoints
# Must use get_current_user dependency for authentication
```

### Dependencies and Configuration

#### Required Python Dependencies
```
# Core Framework
fastapi==0.104.1
uvicorn==0.24.0

# Database
sqlalchemy==2.0.23
asyncpg==0.29.0
alembic==1.12.1

# AI Agent
pydantic-ai==0.2.3
anthropic==0.7.8

# Authentication
bcrypt==4.0.1
PyJWT==2.8.0

# AWS Lambda
mangum==0.17.0
boto3==1.34.0

# Testing
pytest==7.4.0
pytest-asyncio==0.21.0
httpx==0.24.1

# Development
python-multipart==0.0.6
python-dotenv==1.0.0
```

#### Environment Variables Required
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# Anthropic
ANTHROPIC_API_KEY=your_key_here

# JWT
JWT_SECRET_KEY=your_secret_key_here
JWT_ALGORITHM=HS256

# AWS (for Lambda)
AWS_REGION=us-east-1

# Development
DEBUG=false
```

### Database Migration Strategy

#### Phase 1: Schema Creation
1. Run Alembic migrations to create all tables
2. Create sample user with bcrypt-hashed password

#### Phase 2: Data Migration Script
```python
# Migration logic needed:
# 1. Read backend_old/data/user_123/preferences.json -> user_preferences table
# 2. Read backend_old/data/user_123/template.json -> user_templates table  
# 3. Read backend_old/data/sessions/*.json files:
#    - Create chat_sessions records
#    - Create chat_messages records from messages array
#    - Create journal_drafts from structured_journal_data
#    - If is_finalized=true, create journal_entries
```

#### Session Data Transformation
```python
# Transform session JSON to database records:
# session_filename -> chat_session.id (parse timestamp)
# messages[] -> chat_messages records
# structured_journal_data -> journal_draft.draft_data
# is_finalized -> journal_entry if true, journal_draft if false
```

### Error Handling Requirements

#### Type Corrections Needed
```python
# Fix in app/api/v1/endpoints/sessions.py:
current_user: User = Depends(get_current_user)  # Not UUID

# Fix in app/api/v1/endpoints/agent.py:
# Import User model where missing
# Fix message history conversion method call
```

#### Required Error Classes
```python
# Custom exceptions for better error handling:
class UserNotFoundError(Exception): pass
class SessionNotFoundError(Exception): pass
class InvalidJournalDataError(Exception): pass
```

### AWS Lambda Deployment Requirements

#### Lambda Configuration
```yaml
# Required Lambda environment:
# - Memory: 1024MB minimum (for AI model loading)
# - Timeout: 30 seconds
# - Environment variables from Parameter Store
# - VPC configuration for RDS access
```

#### Required AWS Resources
1. **RDS PostgreSQL instance** (t3.micro minimum)
2. **Parameter Store entries** for secrets
3. **Lambda function** with appropriate IAM roles
4. **VPC and Security Groups** for database access

### Testing Data Requirements

#### Test Database Setup
```python
# Tests require:
# - In-memory SQLite for speed
# - Sample user creation function
# - Template and preferences seeding
# - Session cleanup between tests
```

#### Test Data Examples
```python
# Required test scenarios:
# 1. "create journal entry to say i'm sad" -> agent processes -> save -> verify DB
# 2. Multi-section content mapping to template sections  
# 3. Save rejection -> additional content -> save acceptance
# 4. Multiple entries in same session
# 5. Concurrent user testing
```

This completes the functional specification with all information needed for a code generation AI to implement the complete backend system. 