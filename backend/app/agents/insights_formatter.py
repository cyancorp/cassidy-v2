"""
Formatter for presenting insights to users in a readable format
"""

from typing import Dict, Any, List
from datetime import datetime


class InsightsFormatter:
    """Format insights data into human-readable text"""
    
    @staticmethod
    def format_insights(insights: Dict[str, Any]) -> str:
        """Format insights into a markdown-style report"""
        lines = []
        
        # Header
        lines.append("# 📊 Your Journal Insights\n")
        
        # Period information
        period = insights.get("period", {})
        if period:
            start_date = datetime.fromisoformat(period["start"]).strftime("%B %d, %Y")
            end_date = datetime.fromisoformat(period["end"]).strftime("%B %d, %Y")
            lines.append(f"**Analysis Period**: {start_date} to {end_date} ({period['days']} days)\n")
        
        # Summary section
        summary = insights.get("summary", {})
        if summary:
            lines.append("## 📈 Summary\n")
            
            if "message" in summary:
                lines.append(f"{summary['message']}\n")
            else:
                if "total_entries" in summary:
                    lines.append(f"- **Total entries**: {summary['total_entries']}")
                if "average_entries_per_day" in summary:
                    lines.append(f"- **Average entries per day**: {summary['average_entries_per_day']}")
                if "average_entry_length" in summary:
                    lines.append(f"- **Average entry length**: {int(summary['average_entry_length'])} words")
                if "longest_entry" in summary:
                    lines.append(f"- **Longest entry**: {summary['longest_entry']} words")
                lines.append("")
        
        # Patterns section
        patterns = insights.get("patterns", {})
        if patterns:
            lines.append("## 🔍 Patterns Discovered\n")
            
            # Mood distribution
            if "mood_distribution" in patterns:
                lines.append("### Mood Distribution")
                lines.append("How you've been feeling:")
                moods = patterns["mood_distribution"]
                total_moods = sum(moods.values())
                for mood, count in sorted(moods.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_moods * 100) if total_moods > 0 else 0
                    emoji = InsightsFormatter._get_mood_emoji(mood)
                    lines.append(f"- {emoji} **{mood.capitalize()}**: {count} times ({percentage:.1f}%)")
                
                if "dominant_mood" in patterns:
                    lines.append(f"\nYour dominant mood has been **{patterns['dominant_mood']}**")
                lines.append("")
            
            # Top activities
            if "top_activities" in patterns:
                lines.append("### Top Activities")
                lines.append("What you've been doing:")
                for activity, count in sorted(patterns["top_activities"].items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"- **{activity}**: {count} times")
                lines.append("")
            
            # Common themes
            if "common_themes" in patterns:
                lines.append("### Common Themes")
                lines.append("Topics you write about most:")
                for theme, count in sorted(patterns["common_themes"].items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"- **{theme}**: {count} mentions")
                lines.append("")
        
        # Trends section
        trends = insights.get("trends", {})
        if trends:
            lines.append("## 📊 Trends\n")
            
            if "mood_trend" in trends and trends["mood_trend"]:
                lines.append("### Recent Mood Trend")
                lines.append("Your mood over the last 7 days (1-5 scale):")
                for entry in trends["mood_trend"]:
                    date = datetime.fromisoformat(entry["date"]).strftime("%a %b %d")
                    score = entry["score"]
                    bar = "█" * int(score) + "░" * (5 - int(score))
                    lines.append(f"- {date}: {bar} ({score})")
                lines.append("")
        
        # Recommendations section
        recommendations = insights.get("recommendations", [])
        if recommendations:
            lines.append("## 💡 Personalized Recommendations\n")
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")
        
        # Footer
        lines.append("\n---")
        lines.append("*Keep journaling to discover more insights about yourself!*")
        
        return "\n".join(lines)
    
    @staticmethod
    def _get_mood_emoji(mood: str) -> str:
        """Get emoji for mood"""
        mood_emojis = {
            "happy": "😊",
            "excited": "🎉",
            "grateful": "🙏",
            "content": "😌",
            "calm": "😇",
            "peaceful": "☮️",
            "neutral": "😐",
            "okay": "🙂",
            "tired": "😴",
            "stressed": "😰",
            "anxious": "😟",
            "sad": "😢",
            "angry": "😠",
            "frustrated": "😤"
        }
        return mood_emojis.get(mood.lower(), "🔵")