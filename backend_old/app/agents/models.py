# Pydantic models specific to the agent and its state. 

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.models.user import UserPreferences, UserTemplate # Changed import

class JournalDraft(BaseModel):
    """Represents the in-progress data for a journal entry being drafted."""
    data: Dict[str, Any] = Field(default_factory=dict)

class CassidyAgentDependencies(BaseModel):
    """Dependencies injected into the Pydantic AI Agent's RunContext."""
    user_id: str
    current_chat_id: str # This will be the session_id from the API path
    chat_type: str = "journaling"
    user_template: UserTemplate
    user_preferences: UserPreferences
    current_journal_draft: JournalDraft = Field(default_factory=JournalDraft)

class ChatSessionState(BaseModel):
    """Represents the persistent state of a chat session for the agent."""
    user_id: str
    session_id: str # This is the chat_id or current_chat_id
    chat_type: str = "journaling"
    current_journal_draft_data: Dict[str, Any] = Field(default_factory=dict)
    is_journal_entry_finalized: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    # Helper to update draft and last_updated time
    def update_draft(self, new_draft_data: Dict[str, Any]):
        self.current_journal_draft_data = new_draft_data
        self.last_updated = datetime.utcnow()

class AgentUserInput(BaseModel):
    """Input model for the agent chat API endpoint."""
    text: str

class AgentResponseOutput(BaseModel):
    """Output model for the agent chat API endpoint."""
    text: str # Agent's textual response
    updated_structured_data: Optional[Dict[str, Any]] = None # e.g., the updated journal draft
    frontend_action_suggestions: Optional[List[str]] = None # For future use, e.g., buttons 