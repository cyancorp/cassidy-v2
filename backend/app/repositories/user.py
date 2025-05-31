from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
import hashlib

from .base import BaseRepository
from app.models.user import UserDB, AuthSessionDB, UserPreferencesDB, UserTemplateDB
from app.core.security import SecurityService


class UserRepository(BaseRepository[UserDB]):
    def __init__(self):
        super().__init__(UserDB)
    
    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[UserDB]:
        """Get user by username"""
        result = await db.execute(
            select(UserDB).where(UserDB.username == username, UserDB.is_active == True)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[UserDB]:
        """Get user by email"""
        result = await db.execute(
            select(UserDB).where(UserDB.email == email, UserDB.is_active == True)
        )
        return result.scalar_one_or_none()
    
    async def create_user(
        self, 
        db: AsyncSession, 
        username: str, 
        email: Optional[str], 
        password_hash: str
    ) -> UserDB:
        """Create a new user"""
        user = UserDB(
            username=username,
            email=email,
            password_hash=password_hash
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


class AuthSessionRepository(BaseRepository[AuthSessionDB]):
    def __init__(self):
        super().__init__(AuthSessionDB)
    
    async def get_by_token_hash(self, db: AsyncSession, token_hash: str) -> Optional[AuthSessionDB]:
        """Get session by token hash"""
        result = await db.execute(
            select(AuthSessionDB)
            .where(
                AuthSessionDB.token_hash == token_hash,
                AuthSessionDB.expires_at > datetime.utcnow(),
                AuthSessionDB.is_revoked == False
            )
        )
        return result.scalar_one_or_none()
    
    async def create_session(
        self, 
        db: AsyncSession, 
        user_id: str, 
        token_hash: str, 
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AuthSessionDB:
        """Create new authentication session"""
        session = AuthSessionDB(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session
    
    async def revoke_session(self, db: AsyncSession, token_hash: str) -> bool:
        """Revoke a session"""
        result = await db.execute(
            update(AuthSessionDB)
            .where(AuthSessionDB.token_hash == token_hash)
            .values(is_revoked=True)
        )
        await db.commit()
        return result.rowcount > 0
    
    async def revoke_all_user_sessions(self, db: AsyncSession, user_id: str) -> int:
        """Revoke all sessions for a user"""
        result = await db.execute(
            update(AuthSessionDB)
            .where(AuthSessionDB.user_id == user_id, AuthSessionDB.is_revoked == False)
            .values(is_revoked=True)
        )
        await db.commit()
        return result.rowcount


class UserPreferencesRepository(BaseRepository[UserPreferencesDB]):
    def __init__(self):
        super().__init__(UserPreferencesDB)
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> Optional[UserPreferencesDB]:
        """Get preferences by user ID"""
        result = await db.execute(
            select(UserPreferencesDB).where(UserPreferencesDB.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_by_user_id(self, db: AsyncSession, user_id: str, **kwargs) -> Optional[UserPreferencesDB]:
        """Update preferences by user ID"""
        kwargs['updated_at'] = datetime.utcnow()
        await db.execute(
            update(UserPreferencesDB)
            .where(UserPreferencesDB.user_id == user_id)
            .values(**kwargs)
        )
        await db.commit()
        return await self.get_by_user_id(db, user_id)


class UserTemplateRepository(BaseRepository[UserTemplateDB]):
    def __init__(self):
        super().__init__(UserTemplateDB)
    
    async def get_active_by_user_id(self, db: AsyncSession, user_id: str) -> Optional[UserTemplateDB]:
        """Get active template for user"""
        result = await db.execute(
            select(UserTemplateDB)
            .where(UserTemplateDB.user_id == user_id, UserTemplateDB.is_active == True)
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_by_user_and_name(self, db: AsyncSession, user_id: str, name: str) -> Optional[UserTemplateDB]:
        """Get template by user and name"""
        result = await db.execute(
            select(UserTemplateDB)
            .where(UserTemplateDB.user_id == user_id, UserTemplateDB.name == name)
        )
        return result.scalar_one_or_none()