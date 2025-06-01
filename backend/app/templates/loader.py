"""
Template loader for file-based journal templates
"""

import os
from typing import Dict, Any
from app.templates.user_template import USER_TEMPLATE
from app.templates.models import JournalTemplate


class TemplateLoader:
    """Loads and manages journal templates from files"""
    
    def __init__(self):
        self._cached_template = None
    
    def get_user_template(self, user_id: str = None) -> Dict[str, Any]:
        """
        Get the user's template in agent-compatible format
        
        Args:
            user_id: User ID (for future multi-user support)
            
        Returns:
            Template in format expected by agent system
        """
        if self._cached_template is None:
            self._cached_template = USER_TEMPLATE.to_agent_format()
        
        return self._cached_template
    
    def reload_template(self):
        """Reload template from file (useful after editing)"""
        self._cached_template = None
        # This will force reload on next access
    
    def get_template_sections(self) -> Dict[str, str]:
        """Get just the section names and descriptions"""
        template = self.get_user_template()
        return {
            section_name: section_def["description"]
            for section_name, section_def in template["sections"].items()
        }
    
    def validate_section(self, section_name: str) -> bool:
        """Check if a section name is valid in the current template"""
        template = self.get_user_template()
        return section_name in template["sections"]


# Global template loader instance
template_loader = TemplateLoader()