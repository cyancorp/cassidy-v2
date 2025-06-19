from fastapi import APIRouter

from app.api.v1.endpoints import auth, sessions, users, agent, tasks

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(sessions.router, prefix="", tags=["sessions"])  # No prefix for sessions
api_router.include_router(users.router, prefix="/user", tags=["users"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])