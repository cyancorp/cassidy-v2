#!/usr/bin/env python3
"""
Setup User for Journal Import
Creates the jg2950 user if it doesn't exist
"""

import os
import asyncio
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, init_db
from app.models.user import UserDB
from app.core.security import SecurityService
from sqlalchemy import select


async def setup_user():
    """Create user jg2950 if it doesn't exist"""
    
    print("👤 SETTING UP USER FOR IMPORT")
    print("=" * 40)
    
    await init_db()
    
    async for db in get_db():
        # Check if user exists
        result = await db.execute(select(UserDB).where(UserDB.username == "jg2950"))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"✅ User jg2950 already exists (ID: {existing_user.id[:8]}...)")
            print(f"   Email: {existing_user.email}")
            print(f"   Created: {existing_user.created_at}")
            return
            
        # Create new user
        print("👤 Creating user jg2950...")
        
        security_service = SecurityService()
        
        user = UserDB(
            username="jg2950",
            email="jg2950@example.com",
            hashed_password=security_service.hash_password("3qwerty")
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        print(f"✅ User created successfully!")
        print(f"   ID: {user.id}")
        print(f"   Username: {user.username}")
        print(f"   Password: 3qwerty")
        print(f"   Created: {user.created_at}")
        
        break


if __name__ == "__main__":
    asyncio.run(setup_user())