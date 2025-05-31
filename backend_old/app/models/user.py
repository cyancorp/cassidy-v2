from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class UserPreferences(BaseModel):
    purpose_statement: Optional[str] = None
    long_term_goals: List[str] = Field(default_factory=list)
    known_challenges: List[str] = Field(default_factory=list)
    preferred_feedback_style: Optional[str] = None
    personal_glossary: Dict[str, str] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class SectionDetailDef(BaseModel):  # Renamed from TemplateSectionDetail
    description: str = Field(..., description="Detailed description for the LLM explaining what content belongs in this section.")
    aliases: List[str] = Field(default_factory=list, description="Alternative titles for this section found in source text.")


class UserTemplate(BaseModel):
    # sections: List[str] = Field(default_factory=list)
    sections: Dict[str, SectionDetailDef] = Field(default_factory=dict, description="Dictionary mapping standard section names to their details.") # Updated type hint
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class SessionStructuredContent(BaseModel):
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any]
    user_edited: bool = False 