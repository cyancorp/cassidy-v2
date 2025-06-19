from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import Base, TimestampedModel


class TaskDB(TimestampedModel):
    __tablename__ = "tasks"
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, nullable=False)  # Priority for ordering (unique per user)
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(String(50), nullable=True)  # ISO format timestamp
    source_session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=True)  # Optional link to journal session
    
    # Relationships
    user = relationship("UserDB", back_populates="tasks")
    source_session = relationship("ChatSessionDB", back_populates="extracted_tasks")
    
    # Indexes and Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "priority", name="uq_user_task_priority"),  # Unique priority per user
        Index("idx_tasks_user_priority", "user_id", "priority"),
        Index("idx_tasks_user_completed", "user_id", "is_completed"),
    )