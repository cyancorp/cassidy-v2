# Cassidy Backend API

Base URL: `https://tq68ditf6b.execute-api.us-east-1.amazonaws.com/prod/api/v1`

## Authentication

All endpoints except `/auth/login` and `/auth/register` require Bearer token authentication:
```
Authorization: Bearer <token>
```

## Auth Endpoints

### Register
```
POST /auth/register
```
Request:
```json
{
  "username": "user_123",
  "email": "user@example.com",
  "password": "securepassword"
}
```
Response:
```json
{
  "user_id": "df6f0fb0-3039-4e73-8852-8ced8e1d88b1",
  "username": "user_123",
  "message": "User created successfully"
}
```

### Login
```
POST /auth/login
```
Request:
```json
{
  "username": "user_123",
  "password": "securepassword"
}
```
Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user_id": "df6f0fb0-3039-4e73-8852-8ced8e1d88b1",
  "username": "user_123"
}
```

### Get Current User
```
GET /auth/me
```
Response:
```json
{
  "user_id": "df6f0fb0-3039-4e73-8852-8ced8e1d88b1",
  "username": "user_123",
  "email": "user@example.com",
  "is_verified": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

## Session Endpoints

### Create Session
```
POST /sessions
```
Request:
```json
{
  "conversation_type": "journaling"
}
```
Response:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "conversation_type": "journaling",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### List Sessions
```
GET /sessions
```
Response:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "df6f0fb0-3039-4e73-8852-8ced8e1d88b1",
    "conversation_type": "journaling",
    "is_active": true,
    "metadata": {},
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

## Chat Endpoints

### Send Message
```
POST /agent/chat/{session_id}
```
Request:
```json
{
  "text": "I completed my morning workout",
  "metadata": {
    "timestamp": "2024-01-01T10:00:00Z"
  }
}
```
Response:
```json
{
  "text": "Great job completing your morning workout! I've created a task to track this achievement.",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "tool_calls": [
    {
      "tool": "create_task_agent_tool",
      "result": {"task_id": "abc123", "title": "Morning workout"}
    }
  ],
  "metadata": {}
}
```

### Stream Message
```
POST /agent/chat/{session_id}/stream
```
Same request as above, but returns Server-Sent Events:
```
data: {"type": "text_delta", "content": "Great job", "session_id": "550e8400..."}
data: {"type": "text_delta", "content": " completing your", "session_id": "550e8400..."}
data: {"type": "tool_calls", "tool_calls": [...], "session_id": "550e8400..."}
data: {"type": "completion", "full_text": "Great job completing...", "session_id": "550e8400..."}
```
Note: The completion event includes the full assembled text in the `full_text` field.

## Task Endpoints

### List Tasks
```
GET /tasks?include_completed=true
```
Response:
```json
[
  {
    "id": "abc123",
    "title": "Morning workout",
    "description": "30 minutes cardio",
    "priority": 1,
    "is_completed": false,
    "completed_at": null,
    "due_date": null,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00",
    "source_session_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  {
    "id": "def456",
    "title": "Read book",
    "description": null,
    "priority": 2,
    "is_completed": true,
    "completed_at": "2024-01-01T20:00:00",
    "due_date": null,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T20:00:00",
    "source_session_id": null
  }
]
```

### Create Task
```
POST /tasks
```
Request:
```json
{
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "priority": 1,
  "due_date": "2024-01-02"
}
```
Response: (Same structure as task object above)

### Update Task
```
PUT /tasks/{task_id}
```
Request:
```json
{
  "title": "Buy groceries and supplies",
  "is_completed": false
}
```
Response: (Updated task object)

### Complete Task
```
POST /tasks/{task_id}/complete
```
Response: (Task object with is_completed: true and completed_at set)

### Delete Task
```
DELETE /tasks/{task_id}
```
Response:
```json
{
  "message": "Task deleted successfully"
}
```

### Reorder Tasks
```
POST /tasks/reorder
```
Request:
```json
{
  "task_orders": [
    {"task_id": "abc123", "new_priority": 1},
    {"task_id": "def456", "new_priority": 2},
    {"task_id": "ghi789", "new_priority": 3}
  ]
}
```
Response:
```json
{
  "message": "Tasks reordered successfully"
}
```
Note: Must include ALL incomplete tasks with their new priorities (1-based)

## Journal Endpoints

### List Journal Entries
```
GET /journal-entries
```
Response:
```json
[
  {
    "id": "journal123",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2024-01-01T08:00:00Z",
    "raw_text": "Today I woke up feeling energized...",
    "structured_data": {
      "title": "Morning Reflection",
      "content": "Today I woke up feeling energized and grateful for a good night's sleep.",
      "mood": "positive",
      "tags": ["gratitude", "morning", "energy"],
      "key_insights": ["Good sleep improves mood", "Morning routines matter"]
    },
    "metadata": {
      "word_count": 150,
      "sentiment_score": 0.8
    }
  }
]
```

### Get Journal Entry
```
GET /journal-entries/{entry_id}
```
Response: (Same structure as journal entry object above)

## Error Responses

All errors follow this format:
```json
{
  "detail": "Error message here"
}
```

Common status codes:
- 400: Bad Request (validation error)
- 401: Unauthorized (missing/invalid token)
- 404: Not Found
- 500: Internal Server Error