from sqlalchemy import Column, String, Boolean, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import Base, TimestampedModel


class ChatSessionDB(TimestampedModel):
    __tablename__ = "chat_sessions"
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    conversation_type = Column(String(50), nullable=False, default="journaling")
    is_active = Column(Boolean, default=True, nullable=False)
    session_metadata = Column("metadata", JSON, default=dict, nullable=False)
    
    # Relationships
    user = relationship("UserDB", back_populates="chat_sessions")
    messages = relationship("ChatMessageDB", back_populates="session", cascade="all, delete-orphan")
    journal_draft = relationship("JournalDraftDB", back_populates="session", uselist=False)
    journal_entries = relationship("JournalEntryDB", back_populates="session")
    
    # Indexes
    __table_args__ = (
        Index("idx_chat_sessions_user_type", "user_id", "conversation_type"),
        Index("idx_chat_sessions_user_active", "user_id", "is_active"),
    )


class ChatMessageDB(TimestampedModel):
    __tablename__ = "chat_messages"
    
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    message_metadata = Column("metadata", JSON, default=dict, nullable=False)
    
    # Relationships
    session = relationship("ChatSessionDB", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index("idx_chat_messages_session_created", "session_id", "created_at"),
    )


class JournalDraftDB(TimestampedModel):
    __tablename__ = "journal_drafts"
    
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False, unique=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    draft_data = Column(JSON, default=dict, nullable=False)
    is_finalized = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    session = relationship("ChatSessionDB", back_populates="journal_draft")
    user = relationship("UserDB")


class JournalEntryDB(TimestampedModel):
    __tablename__ = "journal_entries"
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=True)
    title = Column(String(255), nullable=True)
    structured_data = Column(JSON, nullable=False)
    entry_metadata = Column("metadata", JSON, default=dict, nullable=False)
    
    # Relationships
    user = relationship("UserDB", back_populates="journal_entries")
    session = relationship("ChatSessionDB", back_populates="journal_entries")
    
    # Indexes
    __table_args__ = (
        Index("idx_journal_entries_user_created", "user_id", "created_at"),
    )