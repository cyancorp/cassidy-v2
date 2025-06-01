from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class SectionDefinition(BaseModel):
    """Definition of a journal template section"""
    description: str = Field(..., description="What this section is for")
    aliases: List[str] = Field(default_factory=list, description="Alternative names for this section")
    examples: Optional[List[str]] = Field(default=None, description="Example content for this section")


class JournalTemplate(BaseModel):
    """Complete journal template definition"""
    name: str = Field(..., description="Name of this template")
    description: str = Field(..., description="Description of when to use this template")
    sections: Dict[str, SectionDefinition] = Field(..., description="Template sections")
    
    class Config:
        extra = "forbid"  # Don't allow extra fields
        
    def to_agent_format(self) -> Dict:
        """Convert to format expected by the agent system"""
        return {
            "name": self.name,
            "sections": {
                section_name: {
                    "description": section_def.description,
                    "aliases": section_def.aliases
                }
                for section_name, section_def in self.sections.items()
            }
        }