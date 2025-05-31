#!/usr/bin/env python3
"""Check what's actually in the database"""
import asyncio
import httpx
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

BASE_URL = "http://localhost:8000"

async def test_database_check():
    """Check database state after adding journal content"""
    
    print("🚀 Testing database state...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Login and create session
        login_response = await client.post(f"{BASE_URL}/api/v1/auth/login", json={
            "username": "user_123", "password": "1234"
        })
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        session_response = await client.post(f"{BASE_URL}/api/v1/sessions", 
            headers=headers, json={"conversation_type": "journaling"})
        session_id = session_response.json()["session_id"]
        print(f"✅ Session created: {session_id}")
        
        # 2. Add journal content
        content_response = await client.post(f"{BASE_URL}/api/v1/agent/chat/{session_id}",
            headers=headers,
            json={"text": "I am feeling sad because the market is down"}
        )
        
        content_data = content_response.json()
        print(f"✅ Content added")
        print(f"   Tool calls: {len(content_data.get('tool_calls', []))}")
        print(f"   Draft data returned: {content_data.get('updated_draft_data')}")
        
        # 3. Now check the database directly
        from app.database import init_db, get_db
        from app.repositories.session import JournalDraftRepository
        
        await init_db()
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        draft_repo = JournalDraftRepository()
        draft = await draft_repo.get_by_session_id(db, session_id)
        
        print(f"✅ Database check:")
        print(f"   Draft exists: {draft is not None}")
        if draft:
            print(f"   Draft data: {draft.draft_data}")
            print(f"   Is finalized: {draft.is_finalized}")
        
        await db_gen.aclose()
        
    print("🎉 Database check completed!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_database_check())
    if not success:
        sys.exit(1)