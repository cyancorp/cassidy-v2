"""
Improved insights generation service that leverages Claude's 200k context window
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import json
import tiktoken

from ..models.session import JournalEntryDB
from ..models.user import UserDB


class InsightsServiceV2:
    """Service for generating insights using Claude's large context window"""
    
    def __init__(self):
        # Use cl100k_base encoding as approximation for Claude's tokenizer
        self.encoding = tiktoken.get_encoding("cl100k_base")
        # Reserve tokens for system prompt, user message, and response
        self.max_context_tokens = 150000  # Conservative limit, leaving room for response
        self.reserved_tokens = 10000  # For prompts and response
        
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        return len(self.encoding.encode(text))
    
    async def generate_insights_with_ai(
        self,
        user: UserDB,
        db: AsyncSession,
        days_back: int = 30,
        ai_agent = None  # Pass the AI agent for analysis
    ) -> Dict[str, Any]:
        """
        Generate insights by sending journal entries to Claude for analysis
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        # Get all entries in the period
        query = select(JournalEntryDB).where(
            and_(
                JournalEntryDB.user_id == user.id,
                JournalEntryDB.created_at >= start_date,
                JournalEntryDB.created_at <= end_date
            )
        ).order_by(JournalEntryDB.created_at.desc())
        
        result = await db.execute(query)
        entries = result.scalars().all()
        
        if not entries:
            return {
                "summary": {"message": "No journal entries found for this period"},
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": days_back
                }
            }
        
        # Prepare entries for AI analysis
        entries_for_analysis = []
        total_tokens = 0
        
        for entry in entries:
            # Format entry for analysis
            entry_text = f"""
Date: {entry.created_at.strftime('%Y-%m-%d %H:%M')}
Title: {entry.title or 'Untitled'}
Content: {entry.raw_text or ''}
"""
            
            # Add structured data if available
            if entry.structured_data:
                try:
                    structured = json.loads(entry.structured_data)
                    if structured:
                        entry_text += f"Structured Data: {json.dumps(structured, indent=2)}\n"
                except:
                    pass
            
            entry_text += "---\n"
            
            # Check if adding this entry would exceed token limit
            entry_tokens = self._estimate_tokens(entry_text)
            if total_tokens + entry_tokens > (self.max_context_tokens - self.reserved_tokens):
                # We've hit the limit, stop here
                break
            
            entries_for_analysis.append(entry_text)
            total_tokens += entry_tokens
        
        # If we have an AI agent, use it for deep analysis
        if ai_agent and entries_for_analysis:
            analysis_prompt = f"""
Analyze the following journal entries from the past {days_back} days and provide comprehensive insights.

Journal Entries:
{''.join(entries_for_analysis)}

Please provide:
1. Overall mood patterns and emotional trends
2. Key themes and topics that appear frequently
3. Notable behavioral patterns or habits
4. Correlations between activities and moods
5. Personal growth areas or achievements
6. Specific, actionable recommendations based on the patterns you observe
7. Any concerning patterns that might benefit from attention

Format your response as a structured report with clear sections.
"""
            
            # This would be called by the agent tool, not here directly
            return {
                "entries_analyzed": len(entries_for_analysis),
                "total_entries": len(entries),
                "tokens_used": total_tokens,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": days_back
                },
                "analysis_prompt": analysis_prompt
            }
        
        # Fallback to basic analysis if no AI agent
        return await self._basic_analysis(entries, start_date, end_date, days_back)
    
    async def _basic_analysis(
        self,
        entries: List[JournalEntryDB],
        start_date: datetime,
        end_date: datetime,
        days_back: int
    ) -> Dict[str, Any]:
        """Basic analysis without AI"""
        # Similar to original implementation but simpler
        moods = []
        activities = []
        
        for entry in entries:
            try:
                if entry.structured_data:
                    structured = json.loads(entry.structured_data)
                    if "mood" in structured and "current_mood" in structured["mood"]:
                        moods.append(structured["mood"]["current_mood"])
                    if "activities" in structured:
                        activities.extend(structured.get("activities", []))
            except:
                continue
        
        return {
            "summary": {
                "total_entries": len(entries),
                "average_entries_per_day": round(len(entries) / days_back, 2)
            },
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days_back
            },
            "basic_stats": {
                "moods_recorded": len(moods),
                "unique_moods": list(set(moods)),
                "activities_recorded": len(activities),
                "unique_activities": list(set(activities))
            }
        }