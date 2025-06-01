# Journal Template Customization

Your journal template is now file-based and fully customizable! 🎉

## Template Location

Your template is defined in: `/app/templates/user_template.py`

## Current Template Sections

Your template now includes **10 sections** optimized for personal life and trading/market activities:

### Personal Sections
- **Things Done** - Completed tasks and accomplishments
- **To Do** - Future tasks, shopping lists, errands
- **Events** - Scheduled meetings, appointments with dates
- **Daily Events** - Things that happened today
- **Thoughts & Feelings** - Emotions, mood, gratitude, personal concerns

### Market & Trading Sections
- **Market Thoughts** - Market analysis, predictions, economic views
- **Trading Activity** - Actual trades, positions, investment actions
- **Market Events** - Fed meetings, earnings, economic announcements
- **Portfolio Review** - Performance analysis, P&L, allocation changes

### General
- **General Reflection** - Broad thoughts that don't fit elsewhere

## How to Customize Your Template

### 1. Edit the Template File

Open `/app/templates/user_template.py` and modify the `USER_TEMPLATE` object:

```python
"New Section Name": SectionDefinition(
    description="What this section is for",
    aliases=["Alternative", "Names", "For", "Section"],
    examples=[
        "example content 1",
        "example content 2"
    ]
),
```

### 2. Section Properties

Each section has:
- **description**: Clear explanation of what belongs in this section
- **aliases**: Alternative names the LLM should recognize
- **examples**: Sample content to help the LLM understand

### 3. Example: Adding a New Section

```python
"Health & Fitness": SectionDefinition(
    description="Exercise activities, health goals, nutrition tracking, medical appointments",
    aliases=["Exercise", "Workout", "Health", "Fitness", "Nutrition"],
    examples=[
        "went for a 5km run",
        "scheduled dentist appointment",
        "meal prep for the week"
    ]
),
```

### 4. Restart the Server

After editing the template, restart the backend server to load your changes:

```bash
# Stop the current server (Ctrl+C)
# Then restart:
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Template Performance

Your new template is working excellently:

✅ **Perfect categorization** of your journal entry:
- `"bought a container of abalone"` → **Things Done**
- `"buy milk next week"` → **To Do** 
- `"feeling lucky because my crypto Punk has sold"` → **Thoughts & Feelings**
- `"think that the market is going to go down"` → **Market Thoughts**

✅ **All market sections** are being recognized and used properly by Sonnet 4

## Benefits of File-Based Templates

1. **Easy Editing** - Modify sections without database changes
2. **Version Control** - Track template changes in git
3. **Backup & Restore** - Simple file-based backup
4. **Custom Sections** - Add unlimited specialized sections
5. **Rich Documentation** - Comments and examples in the code

## Tips for Good Template Design

1. **Clear Descriptions** - Make it obvious what belongs in each section
2. **Good Aliases** - Include common alternative names
3. **Specific Examples** - Help the LLM understand with concrete examples
4. **Logical Organization** - Group related concepts together
5. **Avoid Overlap** - Make sections distinct to prevent confusion

## Template Management Through Conversation

You can now manage your template through natural conversation with the journal:

### Available Commands:
- **"Show me my template info"** - View current template details
- **"What template sections are available?"** - List all sections  
- **"I want to add a section for [topic]"** - Request new sections
- **"Reload my template"** - Refresh template after file edits

### Example Requests:
```
"I want to add a Health section for tracking workouts and doctor visits"
"Can you show me what journal sections I have available?"  
"I'd like a separate section for book notes and reading progress"
```

All template management requests are handled through the **update preferences tool**, making it easy to modify your journaling system through conversation.

Your template is now a powerful, customizable system that adapts to your specific journaling and trading needs!