from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


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


class UserProfileResponse(BaseModel):
    user_id: UUID
    username: str
    email: Optional[str]
    is_verified: bool
    created_at: datetime


class SectionDetailDef(BaseModel):
    description: str = Field(..., description="Detailed description for the LLM")
    aliases: List[str] = Field(default_factory=list, description="Alternative titles")


class UserPreferencesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    user_id: UUID
    purpose_statement: Optional[str] = None
    long_term_goals: List[str] = Field(default_factory=list)
    known_challenges: List[str] = Field(default_factory=list)
    preferred_feedback_style: str = "supportive"
    personal_glossary: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UserPreferencesUpdate(BaseModel):
    purpose_statement: Optional[str] = None
    long_term_goals: Optional[List[str]] = None
    known_challenges: Optional[List[str]] = None
    preferred_feedback_style: Optional[str] = None
    personal_glossary: Optional[Dict[str, str]] = None


class UserTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    user_id: UUID
    name: str = "Default Template"
    sections: Dict[str, SectionDetailDef] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    sections: Optional[Dict[str, SectionDetailDef]] = None


class CreateSessionRequest(BaseModel):
    conversation_type: str = "journaling"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateSessionResponse(BaseModel):
    session_id: UUID
    conversation_type: str
    created_at: datetime


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    conversation_type: str
    is_active: bool
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentChatResponse(BaseModel):
    text: str
    session_id: UUID
    updated_draft_data: Optional[Dict[str, Any]] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)