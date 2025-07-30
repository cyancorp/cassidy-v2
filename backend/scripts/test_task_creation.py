#!/usr/bin/env python3
"""Test task creation directly"""

import asyncio
import sys
sys.path.append('..')

from app.agents.task_tools import create_task_tool
from app.database import init_db


async def test_create_task():
    """Test creating a task directly"""
    print("Testing task creation...")
    
    await init_db()
    
    # Use the jg2950 user ID we know exists
    user_id = "df6f0fb0-3039-4e73-8852-8ced8e1d88b1"
    
    result = await create_task_tool(
        user_id=user_id,
        title="Test task from script",
        description="Testing if task creation works"
    )
    
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(test_create_task())