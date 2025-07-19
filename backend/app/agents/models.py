from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID
from dataclasses import dataclass

from app.models.api import SectionDetailDef


@dataclass  
class CassidyAgentDependencies:
    """Dependencies provided to the Cassidy AI agent"""
    user_id: str
    session_id: str
    conversation_type: str
    user_template: Dict[str, Any]  # Will contain sections as dict
    user_preferences: Dict[str, Any]  # User preferences
    current_journal_draft: Dict[str, Any]  # Current draft data
    current_tasks: List[Dict[str, Any]]  # Current pending tasks
    db: Any = None  # Database session
    user: Any = None  # User object


class StructureJournalRequest(BaseModel):
    """Request to structure journal content"""
    user_text: str = Field(..., description="Raw user input to be structured")


class StructureJournalResponse(BaseModel):
    """Response from structuring journal content"""
    sections_updated: List[str] = Field(default_factory=list, description="List of sections that were updated")
    updated_draft_data: Dict[str, Any] = Field(default_factory=dict, description="The updated journal draft data")
    status: str = "success"


class SaveJournalRequest(BaseModel):
    """Request to save/finalize journal draft"""
    confirmation: bool = Field(default=True, description="User confirmation to save")


class SaveJournalResponse(BaseModel):
    """Response from saving journal"""
    journal_entry_id: str = Field(..., description="ID of the created journal entry")
    status: str = "success"


class UpdatePreferencesRequest(BaseModel):
    """Request to update user preferences"""
    preference_updates: Dict[str, Any] = Field(..., description="Dictionary of preference fields to update")


class UpdatePreferencesResponse(BaseModel):
    """Response from updating preferences"""
    updated_fields: List[str] = Field(default_factory=list, description="List of fields that were updated")
    status: str = "success"