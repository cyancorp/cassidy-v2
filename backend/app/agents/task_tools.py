"""Task management tools for the agent"""
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ..models.task import TaskDB
from ..repositories.task import TaskRepository
from .. import database


async def create_task_tool(
    user_id: str,
    title: str,
    description: Optional[str] = None,
    priority: Optional[int] = None,
    due_date: Optional[str] = None,
    source_session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new task for the user
    
    Args:
        user_id: ID of the user creating the task
        title: Title/summary of the task
        description: Optional detailed description
        priority: Optional priority (if not provided, goes to bottom)
        due_date: Optional due date in ISO format (YYYY-MM-DD)
        source_session_id: Optional session ID if task was extracted from journal
    
    Returns:
        Dictionary with task details or error information
    """
    try:
        # Ensure database is initialized
        if database.async_session_maker is None:
            await database.init_db()
        
        async with database.async_session_maker() as db:
            task_repo = TaskRepository()
            
            task = await task_repo.create_task(
                db=db,
                user_id=user_id,
                title=title,
                description=description,
                priority=priority,
                due_date=due_date,
                source_session_id=source_session_id
            )
            
            return {
                "success": True,
                "task": {
                    "id": str(task.id),
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority,
                    "is_completed": task.is_completed,
                    "due_date": task.due_date,
                    "created_at": task.created_at.isoformat()
                },
                "message": f"Task '{title}' created successfully"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to create task"
        }


async def list_tasks_tool(user_id: str, include_completed: bool = False) -> Dict[str, Any]:
    """List user's tasks
    
    Args:
        user_id: ID of the user
        include_completed: Whether to include completed tasks
    
    Returns:
        Dictionary with list of tasks or error information
    """
    try:
        # Ensure database is initialized
        if database.async_session_maker is None:
            await database.init_db()
        
        async with database.async_session_maker() as db:
            task_repo = TaskRepository()
            
            if include_completed:
                tasks = await task_repo.get_by_user_id(db, user_id)
            else:
                tasks = await task_repo.get_pending_by_user_id(db, user_id)
            
            task_list = []
            for task in tasks:
                task_list.append({
                    "id": str(task.id),
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority,
                    "is_completed": task.is_completed,
                    "completed_at": task.completed_at,
                    "due_date": task.due_date,
                    "created_at": task.created_at.isoformat(),
                    "source_session_id": str(task.source_session_id) if task.source_session_id else None
                })
            
            return {
                "success": True,
                "tasks": task_list,
                "count": len(task_list),
                "message": f"Found {len(task_list)} {'task' if len(task_list) == 1 else 'tasks'}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to retrieve tasks"
        }


async def complete_task_tool(user_id: str, task_id: str) -> Dict[str, Any]:
    """Mark a task as completed
    
    Args:
        user_id: ID of the user
        task_id: ID of the task to complete
    
    Returns:
        Dictionary with result or error information
    """
    try:
        # Ensure database is initialized
        if database.async_session_maker is None:
            await database.init_db()
        
        async with database.async_session_maker() as db:
            task_repo = TaskRepository()
            
            # Verify task belongs to user
            task = await task_repo.get_by_id(db, task_id)
            if not task or task.user_id != user_id:
                return {
                    "success": False,
                    "message": "Task not found or access denied"
                }
            
            if task.is_completed:
                return {
                    "success": True,
                    "message": f"Task '{task.title}' is already completed"
                }
            
            # Mark as completed
            updated_task = await task_repo.update_task(
                db=db,
                task_id=task_id,
                is_completed=True,
                completed_at=datetime.utcnow().isoformat()
            )
            
            return {
                "success": True,
                "task": {
                    "id": str(updated_task.id),
                    "title": updated_task.title,
                    "is_completed": updated_task.is_completed,
                    "completed_at": updated_task.completed_at
                },
                "message": f"Task '{updated_task.title}' marked as completed"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to complete task"
        }


async def delete_task_tool(user_id: str, task_id: str) -> Dict[str, Any]:
    """Delete a task
    
    Args:
        user_id: ID of the user
        task_id: ID of the task to delete
    
    Returns:
        Dictionary with result or error information
    """
    try:
        # Ensure database is initialized
        if database.async_session_maker is None:
            await database.init_db()
        
        async with database.async_session_maker() as db:
            task_repo = TaskRepository()
            
            # Get task title before deletion for confirmation message
            task = await task_repo.get_by_id(db, task_id)
            if not task or task.user_id != user_id:
                return {
                    "success": False,
                    "message": "Task not found or access denied"
                }
            
            task_title = task.title
            success = await task_repo.delete_task(db, task_id, user_id)
            
            if success:
                return {
                    "success": True,
                    "message": f"Task '{task_title}' deleted successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to delete task"
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to delete task"
        }


async def update_task_tool(
    user_id: str,
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Update a task's title or description
    
    Args:
        user_id: ID of the user
        task_id: ID of the task to update
        title: New title (optional)
        description: New description (optional)
    
    Returns:
        Dictionary with updated task or error information
    """
    try:
        # Ensure database is initialized
        if database.async_session_maker is None:
            await database.init_db()
        
        async with database.async_session_maker() as db:
            task_repo = TaskRepository()
            
            # Verify task belongs to user
            task = await task_repo.get_by_id(db, task_id)
            if not task or task.user_id != user_id:
                return {
                    "success": False,
                    "message": "Task not found or access denied"
                }
            
            updated_task = await task_repo.update_task(
                db=db,
                task_id=task_id,
                title=title,
                description=description
            )
            
            if updated_task:
                return {
                    "success": True,
                    "task": {
                        "id": str(updated_task.id),
                        "title": updated_task.title,
                        "description": updated_task.description,
                        "priority": updated_task.priority,
                        "is_completed": updated_task.is_completed
                    },
                    "message": f"Task '{updated_task.title}' updated successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "No changes made to task"
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to update task"
        }


async def extract_tasks_from_text(text: str, user_id: str, source_session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract tasks from user text using AI analysis
    
    Args:
        text: Text to analyze for tasks
        user_id: ID of the user
        source_session_id: Optional session ID where tasks were mentioned
    
    Returns:
        List of created tasks
    """
    try:
        # Use LLM to intelligently extract tasks from text
        import json
        import os
        from pydantic_ai import Agent
        from pydantic_ai.models.anthropic import AnthropicModel
        from app.core.config import settings, get_anthropic_api_key
        
        # Set API key from settings
        api_key = get_anthropic_api_key()
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        model = AnthropicModel(settings.ANTHROPIC_STRUCTURING_MODEL)
        
        # Create agent for task extraction
        task_extraction_agent = Agent(model=model)
        
        extraction_prompt = f"""Analyze the following text and extract any tasks, action items, or things the person needs to do.

INSTRUCTIONS:
1. Look for explicit task language: "need to", "have to", "should", "must", "remember to", "going to"
2. Look for implicit tasks: deadlines, appointments, goals, commitments
3. Extract due dates if mentioned (convert to YYYY-MM-DD format)
4. Create clear, actionable task titles
5. Only extract genuine tasks, not general reflections or observations
6. Return a JSON array of tasks

EXAMPLES:
Input: "I need to call the doctor tomorrow and schedule my dentist appointment for next week. Also should finish the report by Friday."
Output: [
  {{"title": "Call the doctor", "due_date": null}},
  {{"title": "Schedule dentist appointment", "due_date": null}},
  {{"title": "Finish the report", "due_date": null}}
]

Input: "I'm feeling good about my progress. Had a great workout today."
Output: []

Text to analyze:
---
{text}
---

JSON Output (return empty array [] if no tasks found):"""

        # Run the extraction
        result = await task_extraction_agent.run(extraction_prompt)
        analysis_output = result.output.strip()
        
        # Extract JSON from the response
        if analysis_output.startswith("```json"):
            analysis_output = analysis_output[7:]
        if analysis_output.endswith("```"):
            analysis_output = analysis_output[:-3]
        analysis_output = analysis_output.strip()
        
        # Parse the extracted tasks
        try:
            task_data = json.loads(analysis_output)
        except json.JSONDecodeError:
            print(f"Failed to parse task extraction JSON: {analysis_output}")
            return []
        
        # Create tasks from the extracted data
        extracted_tasks = []
        if isinstance(task_data, list):
            for task_item in task_data:
                if isinstance(task_item, dict) and "title" in task_item:
                    try:
                        task_result = await create_task_tool(
                            user_id=user_id,
                            title=task_item["title"],
                            description=task_item.get("description"),
                            due_date=task_item.get("due_date"),
                            source_session_id=source_session_id
                        )
                        if task_result.get("success"):
                            extracted_tasks.append(task_result["task"])
                    except Exception as e:
                        print(f"Failed to create task: {e}")
        
        return extracted_tasks
        
    except Exception as e:
        print(f"Error in AI task extraction: {e}")
        # Fallback to simple pattern matching
        return await _simple_task_extraction(text, user_id, source_session_id)


async def _simple_task_extraction(text: str, user_id: str, source_session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fallback simple task extraction when AI fails"""
    task_indicators = [
        "need to", "have to", "should", "must", "remember to",
        "task:", "todo:", "action item:", "follow up on"
    ]
    
    extracted_tasks = []
    text_lower = text.lower()
    
    # Look for explicit task patterns
    for indicator in task_indicators:
        if indicator in text_lower:
            # Simple extraction
            lines = text.split('\n')
            for line in lines:
                if indicator in line.lower():
                    # Clean up the task title
                    task_title = line.strip()
                    if len(task_title) > 10:  # Only create meaningful tasks
                        try:
                            task_result = await create_task_tool(
                                user_id=user_id,
                                title=task_title,
                                source_session_id=source_session_id
                            )
                            if task_result.get("success"):
                                extracted_tasks.append(task_result["task"])
                        except Exception:
                            pass
                        break
    
    return extracted_tasks


# Tool definitions for the agent system
TASK_TOOLS = [
    {
        "name": "create_task",
        "description": "Create a new task for the user",
        "function": create_task_tool,
        "parameters": {
            "user_id": {"type": "string", "required": True},
            "title": {"type": "string", "required": True},
            "description": {"type": "string", "required": False},
            "priority": {"type": "integer", "required": False},
            "source_session_id": {"type": "string", "required": False}
        }
    },
    {
        "name": "list_tasks",
        "description": "List user's tasks",
        "function": list_tasks_tool,
        "parameters": {
            "user_id": {"type": "string", "required": True},
            "include_completed": {"type": "boolean", "required": False}
        }
    },
    {
        "name": "complete_task",
        "description": "Mark a task as completed",
        "function": complete_task_tool,
        "parameters": {
            "user_id": {"type": "string", "required": True},
            "task_id": {"type": "string", "required": True}
        }
    },
    {
        "name": "delete_task",
        "description": "Delete a task",
        "function": delete_task_tool,
        "parameters": {
            "user_id": {"type": "string", "required": True},
            "task_id": {"type": "string", "required": True}
        }
    },
    {
        "name": "update_task",
        "description": "Update a task's title or description",
        "function": update_task_tool,
        "parameters": {
            "user_id": {"type": "string", "required": True},
            "task_id": {"type": "string", "required": True},
            "title": {"type": "string", "required": False},
            "description": {"type": "string", "required": False}
        }
    }
]