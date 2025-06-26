"""
Custom Journal Template
Edit this file to customize your journal sections and categories.
"""

from app.templates.models import JournalTemplate, SectionDefinition

# Your custom journal template - edit as needed
USER_TEMPLATE = JournalTemplate(
    name="Personal & Trading Journal",
    description="Comprehensive template for personal life and market activities",
    sections={
         # GENERAL
        "Open Reflection": SectionDefinition(
            description="General thoughts, daily reflections, or free-form journaling content that doesn't fit other categories",
            aliases=["Daily Notes", "Journal", "Reflection", "General", "Miscellaneous"],
            examples=[
                "reflecting on work-life balance",
                "thinking about long-term goals",
                "random thoughts about the day"
            ]
        ),
        
        # PERSONAL SECTIONS
        "Things Done": SectionDefinition(
            description="Specific tasks completed, accomplishments, actions taken, or work already finished",
            aliases=["Completed", "Accomplishments", "Activities Completed", "Work Done", "Achievements", "Finished"],
            examples=[
                "completed quarterly report", 
                "bought groceries", 
                "called mom",
                "bought a container of abalone"
            ]
        ),
        
        "To Do": SectionDefinition(
            description="Future tasks, things to buy, errands to run, or actions that need to be taken",
            aliases=["Tasks", "Todo", "Need to do", "Shopping", "Errands", "Action Items"],
            examples=[
                "buy milk next week",
                "schedule dentist appointment", 
                "prepare presentation",
                "call insurance company"
            ]
        ),
        
        "Events": SectionDefinition(
            description="Important events, meetings, appointments, dates, deadlines, or scheduled activities with specific times",
            aliases=["Schedule", "Meetings", "Appointments", "Important Dates", "Calendar", "Deadlines"],
            examples=[
                "board meeting Friday at 2pm",
                "doctor appointment next Tuesday",
                "project deadline March 15th"
            ]
        ),
        
        "Emotional State": SectionDefinition(
            description="Emotional state, mood, thoughts, feelings, gratitude, concerns, or personal reflections",
            aliases=["Emotions", "Mood", "Feelings", "Thoughts", "Gratitude", "Concerns", "Worries", "Personal"],
            examples=[
                "feeling grateful for family support",
                "anxious about presentation", 
                "excited about vacation",
                "feeling lucky because my crypto Punk has sold"
            ]
        ),
        
        # MARKET & TRADING SECTIONS
        "Market Thoughts": SectionDefinition(
            description="Analysis, predictions, observations about financial markets, crypto, stocks, or economic trends",
            aliases=["Market Analysis", "Trading Ideas", "Economic Views", "Market Predictions", "Financial Outlook"],
            examples=[
                "think that the market is going to go down",
                "Bitcoin looks bullish this week",
                "Fed policy likely to impact rates",
                "crypto market showing strength"
            ]
        ),
        
        "Trading Activity": SectionDefinition(
            description="Actual trades made, positions opened/closed, crypto transactions, investment actions",
            aliases=["Trades", "Transactions", "Positions", "Investments", "Trading"],
            examples=[
                "bought 100 shares of AAPL",
                "sold Ethereum at $3200",
                "closed short position in gold",
                "added to crypto portfolio"
            ]
        ),
        
        "Portfolio Review": SectionDefinition(
            description="Review of portfolio performance, risk assessment, allocation changes, profit/loss analysis",
            aliases=["Performance", "P&L", "Risk Review", "Allocation", "Portfolio Analysis"],
            examples=[
                "portfolio up 3% this month",
                "need to rebalance crypto allocation", 
                "reducing tech exposure",
                "crypto profits covering losses in bonds"
            ]
        ),
        
        # GRATITUDE & REFLECTION
        "Things I'm Grateful For": SectionDefinition(
            description="Express gratitude for people, events, achievements, or circumstances in your life",
            aliases=["Gratitude", "Grateful", "Thankful", "Appreciation", "Blessings"],
            examples=[
                "grateful for family support",
                "thankful for good health",
                "appreciating the sunny weather today",
                "blessed to have supportive friends"
            ]
        ),
        
        # PERSONAL - OSCAR
        "Oscar": SectionDefinition(
            description="Memories, thoughts, feelings and plans relating to my son Oscar",
            aliases=["Oscar"],
            examples=[
                "Quality time with Oscar, observing his developmental progress",
                "Oscar doing well and his continued development",
                "oscar is almost walking"
            ]
        ),
    }
)