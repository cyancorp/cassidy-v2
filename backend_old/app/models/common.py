from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

# --- Base Model for Timestamps ---
class TimestampedModel(BaseModel):
    """Base model with an optional timestamp."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# --- Session Related Models ---

class SessionInfo(BaseModel):
    """Basic info containing just the session ID."""
    session_id: str

class SessionRawInput(TimestampedModel):
    session_id: str
    raw_text: str

class SessionStructuredContent(TimestampedModel):
    session_id: str
    summary: Optional[str] = None
    completed_tasks: List[str] = Field(default_factory=list)
    current_goals: List[str] = Field(default_factory=list)
    emotional_state: Optional[str] = None
    planned_tasks: List[str] = Field(default_factory=list)
    # Allow for arbitrary custom fields extracted by AI
    custom_fields: Optional[Dict[str, Any]] = None

# Potentially add SessionConversationLog later if needed
# class SessionConversationLog(TimestampedModel):
#     session_id: str
#     history: List[Dict[str, str]] # List of {"role": "user/assistant", "content": "..."}

# Add other common types or base models here if needed later 