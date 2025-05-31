from pydantic import BaseModel, Field
from typing import List, Dict, Any
from datetime import datetime
from .common import TimestampedModel

class SessionRawInput(TimestampedModel):
    """Model for the original user input (text/speech transcription)."""
    session_id: str # Typically the timestamp string
    raw_text: str

class SessionStructuredContent(TimestampedModel):
    """Model for the structured content after AI processing, based on UserTemplate."""
    session_id: str
    data: Dict[str, Any] = Field(default_factory=dict) # Flexible data based on template
    user_edited: bool = False

class ConversationTurn(BaseModel):
    """A single turn in the follow-up conversation."""
    speaker: str # 'user' or 'ai'
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SessionConversation(TimestampedModel):
    """Model for storing the follow-up conversation related to a session."""
    session_id: str
    turns: List[ConversationTurn] = Field(default_factory=list)

# Could potentially combine StructuredContent and Conversation into a single SessionLog later 