"""Task management API endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ....database import get_db
from ....core.deps import get_current_user
from ....models.user import UserDB
from ....models.task import TaskDB
from ....repositories.task import TaskRepository


router = APIRouter()


# Request/Response models
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[int] = None
    due_date: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_completed: Optional[bool] = None
    due_date: Optional[str] = None


class TaskReorder(BaseModel):
    task_id: str
    new_priority: int


class TaskReorderRequest(BaseModel):
    task_orders: List[TaskReorder]


class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    priority: int
    is_completed: bool
    completed_at: Optional[str]
    due_date: Optional[str]
    created_at: str
    updated_at: str
    source_session_id: Optional[str]


@router.get("", response_model=List[TaskResponse])
@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    include_completed: bool = Query(False, description="Include completed tasks"),
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's tasks"""
    task_repo = TaskRepository()
    
    if include_completed:
        tasks = await task_repo.get_by_user_id(db, current_user.id)
    else:
        tasks = await task_repo.get_pending_by_user_id(db, current_user.id)
    
    return [
        TaskResponse(
            id=str(task.id),
            title=task.title,
            description=task.description,
            priority=task.priority,
            is_completed=task.is_completed,
            completed_at=task.completed_at,
            due_date=task.due_date,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat(),
            source_session_id=str(task.source_session_id) if task.source_session_id else None
        )
        for task in tasks
    ]


@router.post("", response_model=TaskResponse)
@router.post("/", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new task"""
    task_repo = TaskRepository()
    
    task = await task_repo.create_task(
        db=db,
        user_id=current_user.id,
        title=task_data.title,
        description=task_data.description,
        priority=task_data.priority,
        due_date=task_data.due_date
    )
    
    return TaskResponse(
        id=str(task.id),
        title=task.title,
        description=task.description,
        priority=task.priority,
        is_completed=task.is_completed,
        completed_at=task.completed_at,
        due_date=task.due_date,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
        source_session_id=str(task.source_session_id) if task.source_session_id else None
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific task"""
    task_repo = TaskRepository()
    task = await task_repo.get_by_id(db, task_id)
    
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse(
        id=str(task.id),
        title=task.title,
        description=task.description,
        priority=task.priority,
        is_completed=task.is_completed,
        completed_at=task.completed_at,
        due_date=task.due_date,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
        source_session_id=str(task.source_session_id) if task.source_session_id else None
    )


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a task"""
    task_repo = TaskRepository()
    
    # Verify task belongs to user
    task = await task_repo.get_by_id(db, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Prepare completion timestamp if marking as completed
    completed_at = None
    if task_data.is_completed is True and not task.is_completed:
        from datetime import datetime
        completed_at = datetime.utcnow().isoformat()
    
    updated_task = await task_repo.update_task(
        db=db,
        task_id=task_id,
        title=task_data.title,
        description=task_data.description,
        is_completed=task_data.is_completed,
        completed_at=completed_at,
        due_date=task_data.due_date
    )
    
    if not updated_task:
        raise HTTPException(status_code=400, detail="No changes made")
    
    return TaskResponse(
        id=str(updated_task.id),
        title=updated_task.title,
        description=updated_task.description,
        priority=updated_task.priority,
        is_completed=updated_task.is_completed,
        completed_at=updated_task.completed_at,
        created_at=updated_task.created_at.isoformat(),
        updated_at=updated_task.updated_at.isoformat(),
        source_session_id=str(updated_task.source_session_id) if updated_task.source_session_id else None
    )


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a task"""
    task_repo = TaskRepository()
    
    success = await task_repo.delete_task(db, task_id, current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task deleted successfully"}


@router.post("/reorder")
async def reorder_tasks(
    reorder_data: TaskReorderRequest,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reorder tasks by updating their priorities"""
    task_repo = TaskRepository()
    
    # Convert to list of tuples for repository method
    task_priorities = [(item.task_id, item.new_priority) for item in reorder_data.task_orders]
    
    success = await task_repo.reorder_tasks(db, current_user.id, task_priorities)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reorder tasks")
    
    return {"message": "Tasks reordered successfully"}


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: str,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a task as completed"""
    task_repo = TaskRepository()
    
    # Verify task belongs to user
    task = await task_repo.get_by_id(db, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.is_completed:
        raise HTTPException(status_code=400, detail="Task is already completed")
    
    from datetime import datetime
    updated_task = await task_repo.update_task(
        db=db,
        task_id=task_id,
        is_completed=True,
        completed_at=datetime.utcnow().isoformat()
    )
    
    return TaskResponse(
        id=str(updated_task.id),
        title=updated_task.title,
        description=updated_task.description,
        priority=updated_task.priority,
        is_completed=updated_task.is_completed,
        completed_at=updated_task.completed_at,
        created_at=updated_task.created_at.isoformat(),
        updated_at=updated_task.updated_at.isoformat(),
        source_session_id=str(updated_task.source_session_id) if updated_task.source_session_id else None
    )