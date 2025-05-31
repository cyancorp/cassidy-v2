from fastapi import APIRouter

from app.api.v1.endpoints import session
from app.api.v1.endpoints import user
from app.api.v1.endpoints import agent

api_router = APIRouter()

# Include session endpoints under /session prefix
api_router.include_router(session.router, prefix="/session", tags=["session"])

# Include user endpoints under /user prefix
api_router.include_router(user.router, prefix="/user", tags=["user"])

# Include agent endpoints under /agent prefix
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])

# Add other endpoint routers here later (e.g., insights) 