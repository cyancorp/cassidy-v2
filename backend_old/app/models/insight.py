from pydantic import BaseModel, Field
from typing import List
from .common import TimestampedModel

class Insight(TimestampedModel):
    """Model for AI-generated insights or feedback."""
    insight_id: str # Can be derived from timestamp or a UUID
    related_session_ids: List[str] = Field(default_factory=list)
    content: str
    type: str = "general" # e.g., 'goal_progress', 'emotional_trend', 'suggestion'
    # Potentially add confidence score or source later 