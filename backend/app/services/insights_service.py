"""
Insights generation service for analyzing journal entries
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import json
from collections import Counter, defaultdict

from ..models.session import JournalEntryDB
from ..models.user import UserDB


class InsightsService:
    """Service for generating insights from journal entries"""
    
    def __init__(self):
        self.chunk_size = 10  # Process entries in chunks to handle large datasets
        
    async def generate_insights(
        self,
        user: UserDB,
        db: AsyncSession,
        days_back: int = 30,
        chunk_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate insights from user's journal entries
        Processes entries in chunks to handle large datasets
        """
        chunk_size = chunk_size or self.chunk_size
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        # Initialize insights data
        insights = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days_back
            },
            "summary": {},
            "patterns": {},
            "trends": {},
            "recommendations": []
        }
        
        # Get total count of entries
        count_query = select(func.count(JournalEntryDB.id)).where(
            and_(
                JournalEntryDB.user_id == user.id,
                JournalEntryDB.created_at >= start_date,
                JournalEntryDB.created_at <= end_date
            )
        )
        total_entries = await db.scalar(count_query)
        
        if total_entries == 0:
            insights["summary"]["message"] = "No journal entries found for this period"
            return insights
        
        insights["summary"]["total_entries"] = total_entries
        
        # Process entries in chunks
        offset = 0
        all_moods = []
        all_activities = []
        all_tags = []
        entry_lengths = []
        entries_by_date = defaultdict(int)
        mood_by_date = defaultdict(list)
        
        while offset < total_entries:
            # Get chunk of entries
            query = select(JournalEntryDB).where(
                and_(
                    JournalEntryDB.user_id == user.id,
                    JournalEntryDB.created_at >= start_date,
                    JournalEntryDB.created_at <= end_date
                )
            ).order_by(JournalEntryDB.created_at).offset(offset).limit(chunk_size)
            
            result = await db.execute(query)
            entries = result.scalars().all()
            
            if not entries:
                break
                
            # Process this chunk
            for entry in entries:
                # Extract structured data
                try:
                    structured = json.loads(entry.structured_data) if entry.structured_data else {}
                except:
                    structured = {}
                
                # Collect moods
                if "mood" in structured:
                    mood = structured["mood"]
                    if isinstance(mood, dict) and "current_mood" in mood:
                        all_moods.append(mood["current_mood"])
                        date_key = entry.created_at.date().isoformat()
                        mood_by_date[date_key].append(mood["current_mood"])
                
                # Collect activities
                if "activities" in structured:
                    activities = structured["activities"]
                    if isinstance(activities, list):
                        all_activities.extend(activities)
                
                # Collect tags
                if "tags" in structured:
                    tags = structured["tags"]
                    if isinstance(tags, list):
                        all_tags.extend(tags)
                
                # Track entry length
                if entry.raw_text:
                    entry_lengths.append(len(entry.raw_text.split()))
                
                # Track entries by date
                date_key = entry.created_at.date().isoformat()
                entries_by_date[date_key] += 1
            
            offset += chunk_size
        
        # Analyze collected data
        
        # Mood analysis
        if all_moods:
            mood_counts = Counter(all_moods)
            insights["patterns"]["mood_distribution"] = dict(mood_counts.most_common())
            insights["patterns"]["dominant_mood"] = mood_counts.most_common(1)[0][0]
            
            # Mood trends
            mood_trend = []
            for date in sorted(mood_by_date.keys())[-7:]:  # Last 7 days
                moods = mood_by_date[date]
                if moods:
                    # Simple mood to score mapping
                    mood_scores = {
                        "happy": 5, "excited": 5, "grateful": 5,
                        "content": 4, "calm": 4, "peaceful": 4,
                        "neutral": 3, "okay": 3,
                        "tired": 2, "stressed": 2, "anxious": 2,
                        "sad": 1, "angry": 1, "frustrated": 1
                    }
                    avg_score = sum(mood_scores.get(m.lower(), 3) for m in moods) / len(moods)
                    mood_trend.append({"date": date, "score": round(avg_score, 2)})
            
            insights["trends"]["mood_trend"] = mood_trend
        
        # Activity analysis
        if all_activities:
            activity_counts = Counter(all_activities)
            insights["patterns"]["top_activities"] = dict(activity_counts.most_common(5))
        
        # Tag analysis
        if all_tags:
            tag_counts = Counter(all_tags)
            insights["patterns"]["common_themes"] = dict(tag_counts.most_common(5))
        
        # Entry frequency analysis
        insights["patterns"]["entries_by_date"] = dict(entries_by_date)
        insights["summary"]["average_entries_per_day"] = round(total_entries / days_back, 2)
        
        # Entry length analysis
        if entry_lengths:
            insights["summary"]["average_entry_length"] = round(sum(entry_lengths) / len(entry_lengths), 0)
            insights["summary"]["longest_entry"] = max(entry_lengths)
            insights["summary"]["shortest_entry"] = min(entry_lengths)
        
        # Generate recommendations based on patterns
        recommendations = self._generate_recommendations(insights)
        insights["recommendations"] = recommendations
        
        return insights
    
    def _generate_recommendations(self, insights: Dict[str, Any]) -> List[str]:
        """Generate personalized recommendations based on insights"""
        recommendations = []
        
        # Based on mood patterns
        if "mood_distribution" in insights.get("patterns", {}):
            moods = insights["patterns"]["mood_distribution"]
            negative_moods = ["sad", "angry", "frustrated", "anxious", "stressed"]
            negative_count = sum(moods.get(mood, 0) for mood in negative_moods)
            total_count = sum(moods.values())
            
            if total_count > 0 and negative_count / total_count > 0.3:
                recommendations.append(
                    "You've experienced challenging emotions frequently. Consider exploring stress management techniques or talking to someone you trust."
                )
        
        # Based on entry frequency
        avg_entries = insights.get("summary", {}).get("average_entries_per_day", 0)
        if avg_entries < 0.5:
            recommendations.append(
                "Try to journal more regularly. Even a few sentences daily can help track patterns and improve self-awareness."
            )
        elif avg_entries > 2:
            recommendations.append(
                "Great job maintaining a consistent journaling practice! You're building valuable self-awareness."
            )
        
        # Based on entry length
        avg_length = insights.get("summary", {}).get("average_entry_length", 0)
        if avg_length < 50:
            recommendations.append(
                "Consider writing more detailed entries to better capture your thoughts and feelings."
            )
        
        # Based on activities
        if "top_activities" in insights.get("patterns", {}):
            activities = insights["patterns"]["top_activities"]
            if "exercise" in activities or "workout" in activities:
                recommendations.append(
                    "Keep up the physical activity! Exercise appears frequently in your entries, which is great for mental health."
                )
        
        return recommendations
    
    async def get_mood_summary(
        self,
        user: UserDB,
        db: AsyncSession,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get a quick mood summary for the specified period"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        query = select(JournalEntryDB).where(
            and_(
                JournalEntryDB.user_id == user.id,
                JournalEntryDB.created_at >= start_date,
                JournalEntryDB.created_at <= end_date
            )
        ).order_by(JournalEntryDB.created_at.desc())
        
        result = await db.execute(query)
        entries = result.scalars().all()
        
        moods = []
        for entry in entries:
            try:
                structured = json.loads(entry.structured_data) if entry.structured_data else {}
                if "mood" in structured and "current_mood" in structured["mood"]:
                    moods.append({
                        "date": entry.created_at.isoformat(),
                        "mood": structured["mood"]["current_mood"]
                    })
            except:
                continue
        
        return {
            "period_days": days,
            "mood_entries": moods,
            "total_entries": len(entries)
        }