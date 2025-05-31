from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from app.models.base import TimestampedModel
from datetime import datetime

T = TypeVar('T', bound=TimestampedModel)


class BaseRepository(Generic[T]):
    def __init__(self, model_class: Type[T]):
        self.model_class = model_class
    
    async def create(self, db: AsyncSession, **kwargs) -> T:
        """Create a new record"""
        db_obj = self.model_class(**kwargs)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get_by_id(self, db: AsyncSession, id: str) -> Optional[T]:
        """Get record by ID"""
        result = await db.execute(select(self.model_class).where(self.model_class.id == id))
        return result.scalar_one_or_none()
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> List[T]:
        """Get all records for a user"""
        result = await db.execute(
            select(self.model_class).where(self.model_class.user_id == user_id)
        )
        return result.scalars().all()
    
    async def update(self, db: AsyncSession, id: str, **kwargs) -> Optional[T]:
        """Update a record"""
        kwargs['updated_at'] = datetime.utcnow()
        await db.execute(
            update(self.model_class).where(self.model_class.id == id).values(**kwargs)
        )
        await db.commit()
        return await self.get_by_id(db, id)
    
    async def delete(self, db: AsyncSession, id: str) -> bool:
        """Delete a record"""
        result = await db.execute(
            delete(self.model_class).where(self.model_class.id == id)
        )
        await db.commit()
        return result.rowcount > 0
    
    async def list_all(self, db: AsyncSession, limit: int = 100, offset: int = 0) -> List[T]:
        """List all records with pagination"""
        result = await db.execute(
            select(self.model_class).limit(limit).offset(offset)
        )
        return result.scalars().all()