# Cassidy Backend V2

AI-powered journaling assistant backend built with FastAPI, SQLAlchemy, and Pydantic-AI.

## Overview

Cassidy Backend V2 is a complete rebuild focused on:
- **Database-backed persistence** (SQLite for development, PostgreSQL for production)
- **Multi-user support** with JWT authentication
- **AI agent integration** with Anthropic Claude via Pydantic-AI
- **Scalable architecture** ready for AWS Lambda deployment
- **Frontend API compatibility** with existing React frontend

## Features

- 🔐 **JWT Authentication** - Secure user registration and login
- 🤖 **AI Journaling Assistant** - Intelligent content structuring with Anthropic Claude
- 📊 **Flexible Templates** - Customizable journal sections (trading, emotions, goals, etc.)
- 💾 **Persistent Storage** - SQLite for development, PostgreSQL-ready for production
- 🔧 **Developer Friendly** - Hot reload, comprehensive logging, easy testing

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Anthropic API key

### Installation

1. **Clone and navigate to backend**
   ```bash
   cd backend
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your Anthropic API key
   ```

4. **Run the development server**
   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Test the setup**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"healthy","version":"2.0.0"}
   ```

### Sample User

A sample user is automatically created for testing:
- **Username:** `user_123`
- **Password:** `1234`
- **Email:** `user123@example.com`

## Environment Configuration

Create a `.env` file in the backend directory:

```env
# Anthropic API (Required)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_DEFAULT_MODEL=claude-3-7-sonnet-latest

# Database
DATABASE_URL=sqlite+aiosqlite:///./cassidy.db

# JWT Authentication
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_HOURS=24

# Application
DEBUG=true
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/auth/me` - Get current user profile

### Sessions
- `POST /api/v1/sessions` - Create new chat session
- `GET /api/v1/sessions` - List user's sessions
- `GET /api/v1/sessions/{session_id}` - Get specific session

### User Management
- `GET /api/v1/user/preferences` - Get user preferences
- `POST /api/v1/user/preferences` - Update user preferences
- `GET /api/v1/user/template` - Get user's journal template
- `POST /api/v1/user/template` - Update journal template

### AI Agent
- `POST /api/v1/agent/chat/{session_id}` - Chat with AI agent

### Health Check
- `GET /health` - Service health status

## Testing

### Run Complete Test Suite
```bash
# Run all tests (recommended)
uv run pytest

# Run with verbose output
uv run pytest -v

# Run with coverage report
uv run pytest --cov=app --cov-report=html

# Quick test to verify setup
uv run pytest tests/test_agents_tools.py::TestSaveJournalTool::test_save_with_confirmation_true -v
```

### Test Categories

**Unit Tests**
```bash
# Test agent tools (LLM-based structuring, saving, preferences)
uv run pytest tests/test_agents_tools.py -v

# Test agent service functionality
uv run pytest tests/test_agent_service.py -v
```

**Integration Tests**
```bash
# Test complete agent workflows
uv run pytest tests/test_agent_integration.py -v

# Test API endpoints with authentication
uv run pytest tests/test_agent_api.py -v
```

**Manual Integration Tests**
```bash
# Basic setup verification
uv run python test_basic.py

# Agent system test
uv run python test_agent_simple.py

# Full workflow test (requires running server)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
uv run python test_agent_flow.py
```

### Test Coverage

The test suite covers:
- **LLM-based content structuring** with various input types (strings, arrays, mixed)
- **Content merging** across multiple conversation turns
- **Error handling** for LLM failures, JSON parsing errors, database issues
- **Message history** formatting and agent context preservation
- **Authentication** and authorization flows
- **Complete workflows** from journal creation to saving
- **API endpoints** with proper mocking and error scenarios

## Example Usage

### 1. Login and Get Token
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user_123", "password": "1234"}'
```

### 2. Create Journal Session
```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"conversation_type": "journaling"}'
```

### 3. Chat with AI Agent
```bash
curl -X POST http://localhost:8000/api/v1/agent/chat/SESSION_ID \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "I had a great trading day today. Made $500 profit on AAPL calls."}'
```

## AI Agent Features

The AI agent automatically:
- **Structures content** into your journal template sections
- **Identifies patterns** (trading activity, emotions, market thoughts)
- **Asks follow-up questions** to help you reflect deeper
- **Saves entries** when you're ready
- **Learns preferences** to provide better assistance

### Journal Template Sections

Default sections include:
- **General Reflection** - Daily thoughts and free-form content
- **Things Done** - Tasks completed, accomplishments, and work done
- **Events** - Important events, meetings, appointments with specific dates/times
- **Daily Events** - Significant activities and experiences from the day
- **Thoughts & Feelings** - Emotional state, mood, and internal experiences
- **Trading Journal** - Specific trades, positions, P&L (if using trading template)
- **Market Thoughts** - Market analysis and outlook (if using trading template)
- **Strategy Considerations** - High-level planning (if using trading template)
- **Goals for Next Week** - Objectives and plans (if using trading template)
- **Things I'm Grateful For** - Gratitude expressions (if using trading template)

## Database Schema

### Core Tables
- `users` - User accounts and authentication
- `auth_sessions` - JWT session management
- `user_preferences` - Personal settings and preferences
- `user_templates` - Custom journal templates
- `chat_sessions` - Conversation sessions
- `chat_messages` - Message history
- `journal_drafts` - Work-in-progress entries
- `journal_entries` - Finalized journal entries

## Database Viewer

Several tools are available to view and explore the SQLite database (`cassidy.db`):

### 1. GUI Tool - DB Browser for SQLite (Recommended)

**Install** (macOS with Homebrew):
```bash
brew install --cask db-browser-for-sqlite
```

**Open Database**:
```bash
# From backend directory
open -a "DB Browser for SQLite" cassidy.db
```

**Features**:
- Visual table browser
- SQL query editor
- Schema viewer
- Data editing capabilities
- Export functionality

### 2. Command Line - sqlite3

**Interactive Shell**:
```bash
# From backend directory
sqlite3 cassidy.db

# Useful commands in sqlite3:
.tables                    # List all tables
.schema users             # Show table schema
.mode column              # Format output in columns
.headers on               # Show column headers
SELECT * FROM users;      # Query data
.quit                     # Exit
```

**Quick Queries**:
```bash
# List all tables
sqlite3 cassidy.db ".tables"

# Show table schema
sqlite3 cassidy.db ".schema users"

# Count records
sqlite3 cassidy.db "SELECT COUNT(*) FROM journal_entries;"

# View recent journal entries
sqlite3 cassidy.db "SELECT title, created_at FROM journal_entries ORDER BY created_at DESC LIMIT 5;"
```

### 3. Python Script - view_db.py

**Run the Database Viewer**:
```bash
# From backend directory
uv run --with pandas view_db.py
```

**Features**:
- Shows all tables and record counts
- Displays sample data from each table
- Easy to modify for custom analysis
- Useful for data exploration and debugging

**Example Output**:
```
📊 Available tables:
  • users
  • auth_sessions
  • user_preferences
  • user_templates
  • chat_sessions
  • chat_messages
  • journal_drafts
  • journal_entries

🔍 Sample data from 'users':
   Total rows: 2
   [sample data shown...]
```

### 4. Custom Analysis

**Create custom scripts** for specific data analysis:
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('cassidy.db')

# Analyze journal entry patterns
entries_df = pd.read_sql_query("""
    SELECT 
        DATE(created_at) as date,
        COUNT(*) as entry_count
    FROM journal_entries 
    GROUP BY DATE(created_at)
    ORDER BY date DESC
""", conn)

print(entries_df)
```

## Development

### Project Structure
```
backend/
├── app/
│   ├── agents/              # AI agent system
│   │   ├── factory.py       # Agent creation and management
│   │   ├── service.py       # Agent business logic
│   │   ├── tools.py         # Pydantic-AI tools
│   │   └── models.py        # Agent data models
│   ├── api/v1/              # API endpoints
│   │   └── endpoints/       # Route handlers
│   ├── core/                # Configuration and security
│   ├── models/              # Database and API models
│   ├── repositories/        # Data access layer
│   └── services/            # Business logic services
├── tests/                   # Test files
├── .env                     # Environment variables
├── pyproject.toml           # Dependencies and config
└── README.md                # This file
```

### Running with Different Databases

**SQLite (Development - Default)**
```env
DATABASE_URL=sqlite+aiosqlite:///./cassidy.db
```

**PostgreSQL (Production)**
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/cassidy
```

### Adding New Features

1. **New API Endpoints**: Add to `app/api/v1/endpoints/`
2. **Database Models**: Add to `app/models/`
3. **Business Logic**: Add to `app/services/`
4. **AI Tools**: Add to `app/agents/tools.py`

## Deployment

### AWS Lambda (Production)

The backend is designed for serverless deployment:

1. **Configure for Lambda**
   ```python
   # lambda_function.py
   from mangum import Mangum
   from app.main import app
   
   handler = Mangum(app, lifespan="off")
   ```

2. **Environment Variables**
   - Use AWS Parameter Store for secrets
   - Configure PostgreSQL RDS connection
   - Set appropriate CORS origins

3. **Database**
   - Use AWS RDS PostgreSQL
   - Configure connection pooling
   - Set up VPC security groups

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Make sure you're in the backend directory
cd backend
uv sync
```

**Database Issues**
```bash
# Delete and recreate database
rm cassidy.db
uv run python test_basic.py
```

**Agent API Errors**
- Verify `ANTHROPIC_API_KEY` in `.env`
- Check API key permissions
- Monitor rate limits

**Port Already in Use**
```bash
# Kill existing uvicorn processes
pkill -f uvicorn
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is proprietary software for Cassidy AI Journaling Assistant.

---

For questions or support, please check the troubleshooting section or create an issue.