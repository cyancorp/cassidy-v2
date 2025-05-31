from sqlalchemy import Column, DateTime, func, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class TimestampedModel(Base):
    __abstract__ = True
    
    # Use UUID for primary keys - compatible with both SQLite and PostgreSQL
    id = Column(
        String(36),  # Use String for SQLite compatibility
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now()
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now()
    )