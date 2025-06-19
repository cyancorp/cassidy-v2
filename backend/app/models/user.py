from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from .base import Base, TimestampedModel


class UserDB(TimestampedModel):
    __tablename__ = "users"
    
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    preferences = relationship("UserPreferencesDB", back_populates="user", uselist=False)
    templates = relationship("UserTemplateDB", back_populates="user")
    chat_sessions = relationship("ChatSessionDB", back_populates="user")
    journal_entries = relationship("JournalEntryDB", back_populates="user")
    auth_sessions = relationship("AuthSessionDB", back_populates="user")
    tasks = relationship("TaskDB", back_populates="user")


class AuthSessionDB(TimestampedModel):
    __tablename__ = "auth_sessions"
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    
    # Relationships
    user = relationship("UserDB", back_populates="auth_sessions")
    
    # Indexes
    __table_args__ = (
        Index("idx_auth_sessions_token_hash", "token_hash"),
        Index("idx_auth_sessions_user_expires", "user_id", "expires_at"),
    )


class UserPreferencesDB(TimestampedModel):
    __tablename__ = "user_preferences"
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    purpose_statement = Column(Text, nullable=True)
    long_term_goals = Column(JSON, default=list, nullable=False)
    known_challenges = Column(JSON, default=list, nullable=False)
    preferred_feedback_style = Column(String(50), default="supportive", nullable=False)
    personal_glossary = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    user = relationship("UserDB", back_populates="preferences")


class UserTemplateDB(TimestampedModel):
    __tablename__ = "user_templates"
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False, default="Default Template")
    sections = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    user = relationship("UserDB", back_populates="templates")
    
    # Constraints
    __table_args__ = (
        Index("idx_user_templates_user_name", "user_id", "name", unique=True),
        Index("idx_user_templates_user_active", "user_id", "is_active"),
    )