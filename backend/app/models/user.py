from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import TypeDecorator
from datetime import datetime
import uuid
import json

from .base import Base, TimestampedModel


class JSONField(TypeDecorator):
    """Cross-database JSON field that uses JSONB for PostgreSQL and JSON for SQLite"""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == 'postgresql':
            return value
        else:
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == 'postgresql':
            return value
        else:
            return json.loads(value) if isinstance(value, str) else value


class UserDB(TimestampedModel):
    __tablename__ = "users"
    
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # User preferences stored as JSON
    preferences = Column(JSONField, nullable=False, default=dict)
    
    # Relationships
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