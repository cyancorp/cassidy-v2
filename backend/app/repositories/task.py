from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload

from ..models.task import TaskDB
from .base import BaseRepository


class TaskRepository(BaseRepository[TaskDB]):
    """Repository for task operations"""
    
    def __init__(self):
        super().__init__(TaskDB)
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> List[TaskDB]:
        """Get all tasks for a user, ordered by priority"""
        result = await db.execute(
            select(TaskDB)
            .where(TaskDB.user_id == user_id)
            .order_by(TaskDB.priority)
        )
        return result.scalars().all()
    
    async def get_pending_by_user_id(self, db: AsyncSession, user_id: str) -> List[TaskDB]:
        """Get pending (non-completed) tasks for a user, ordered by priority"""
        result = await db.execute(
            select(TaskDB)
            .where(TaskDB.user_id == user_id, TaskDB.is_completed == False)
            .order_by(TaskDB.priority)
        )
        return result.scalars().all()
    
    async def get_completed_by_user_id(self, db: AsyncSession, user_id: str) -> List[TaskDB]:
        """Get completed tasks for a user, ordered by completion time"""
        result = await db.execute(
            select(TaskDB)
            .where(TaskDB.user_id == user_id, TaskDB.is_completed == True)
            .order_by(TaskDB.completed_at.desc())
        )
        return result.scalars().all()
    
    async def get_next_priority(self, db: AsyncSession, user_id: str) -> int:
        """Get the next available priority number for a user's tasks"""
        result = await db.execute(
            select(func.max(TaskDB.priority))
            .where(TaskDB.user_id == user_id)
        )
        max_priority = result.scalar()
        return (max_priority or 0) + 1
    
    async def create_task(
        self, 
        db: AsyncSession, 
        user_id: str, 
        title: str, 
        description: Optional[str] = None,
        priority: Optional[int] = None,
        due_date: Optional[str] = None,
        source_session_id: Optional[str] = None
    ) -> TaskDB:
        """Create a new task"""
        if priority is None:
            priority = await self.get_next_priority(db, user_id)
        
        task = TaskDB(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            source_session_id=source_session_id
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task
    
    async def update_task(
        self, 
        db: AsyncSession, 
        task_id: str, 
        title: Optional[str] = None,
        description: Optional[str] = None,
        is_completed: Optional[bool] = None,
        completed_at: Optional[str] = None,
        due_date: Optional[str] = None
    ) -> Optional[TaskDB]:
        """Update a task"""
        update_data = {}
        if title is not None:
            update_data['title'] = title
        if description is not None:
            update_data['description'] = description
        if is_completed is not None:
            update_data['is_completed'] = is_completed
        if completed_at is not None:
            update_data['completed_at'] = completed_at
        if due_date is not None:
            update_data['due_date'] = due_date
        
        if not update_data:
            return None
        
        await db.execute(
            update(TaskDB)
            .where(TaskDB.id == task_id)
            .values(**update_data)
        )
        await db.commit()
        
        # Return updated task
        result = await db.execute(select(TaskDB).where(TaskDB.id == task_id))
        return result.scalar_one_or_none()
    
    async def reorder_tasks(self, db: AsyncSession, user_id: str, task_priorities: List[tuple[str, int]]) -> bool:
        """Reorder tasks by updating their priorities
        
        Args:
            task_priorities: List of (task_id, new_priority) tuples
        """
        try:
            # First, get the max priority to use as offset for temporary values
            result = await db.execute(
                select(func.max(TaskDB.priority))
                .where(TaskDB.user_id == user_id)
            )
            max_priority = result.scalar() or 0
            offset = max_priority + 1000  # Use large offset to avoid conflicts
            
            # Step 1: Update all tasks to temporary priority values to avoid unique constraint conflicts
            for i, (task_id, new_priority) in enumerate(task_priorities):
                temp_priority = offset + i
                await db.execute(
                    update(TaskDB)
                    .where(TaskDB.id == task_id, TaskDB.user_id == user_id)
                    .values(priority=temp_priority)
                )
            
            # Flush to ensure temporary values are written to database
            await db.flush()
            
            # Step 2: Update all tasks to their final priority values
            for task_id, new_priority in task_priorities:
                await db.execute(
                    update(TaskDB)
                    .where(TaskDB.id == task_id, TaskDB.user_id == user_id)
                    .values(priority=new_priority)
                )
            
            await db.commit()
            return True
        except Exception as e:
            print(f"Error in reorder_tasks: {e}")
            await db.rollback()
            return False
    
    async def delete_task(self, db: AsyncSession, task_id: str, user_id: str) -> bool:
        """Delete a task (with user verification)"""
        result = await db.execute(
            delete(TaskDB)
            .where(TaskDB.id == task_id, TaskDB.user_id == user_id)
        )
        await db.commit()
        return result.rowcount > 0
    
    async def get_by_source_session(self, db: AsyncSession, session_id: str) -> List[TaskDB]:
        """Get tasks extracted from a specific session"""
        result = await db.execute(
            select(TaskDB)
            .where(TaskDB.source_session_id == session_id)
            .order_by(TaskDB.priority)
        )
        return result.scalars().all()