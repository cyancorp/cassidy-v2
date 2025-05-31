# REMOVE debug lines
# import sys
# print("--- sys.path ---")
# for p in sys.path:
#     print(p)
# print("----------------")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# Import the settings instance
from app.core.config import settings

# Import the main v1 API router
from app.api.v1.api import api_router as api_v1_router
# Import the new agent router
from app.api.v1.endpoints.agent import router as agent_router

# Import the agent creation function
from app.agents.main import create_cassidy_agent

# Lifespan manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    print("Application startup...")
    # AGENT INITIALIZATION REMOVED FROM LIFESPAN
    # # Create the agent and get the instance
    # agent_instance_from_lifespan = await create_cassidy_agent()
    # 
    # # Store it on app.state if successfully created, for access in request handlers
    # if agent_instance_from_lifespan:
    #     app_instance.state.cassidy_agent = agent_instance_from_lifespan
    #     print("Cassidy Agent has been initialized and stored in app.state.") # This message will change or be removed
    # else:
    #     app_instance.state.cassidy_agent = None 
    #     print("ERROR: Cassidy Agent was NOT initialized successfully via lifespan.") # This message will change or be removed
    print("Lifespan: Agent initialization step bypassed. Agent will be created per-request.")
    yield
    print("Application shutdown...")

# Use settings in app initialization
app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan # Add the lifespan manager
    # You might add version, description etc. here later
)

# --- CORS Middleware Configuration ---
# List of allowed origins (e.g., your frontend development server)
# Use settings for this if needed later, for now hardcode common dev origins
origins = [
    "http://localhost",
    "http://localhost:5173", # Default Vite dev port
    "http://127.0.0.1:5173", # Vite might use this URL instead
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176", # Current Vite port
    "http://127.0.0.1:5176", # Using 127.0.0.1 equivalent
    "http://localhost:3000", # Common React dev port
    "http://127.0.0.1:3000", # React might use this URL
    # Add any other origins if necessary
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allow all methods (GET, POST, etc.)
    allow_headers=["*"], # Allow all headers
)

# --- PoC Endpoint (Keep for now, maybe move later) ---
class TextInput(BaseModel):
    text: str

@app.post("/api/poc/transcribe") # Keep simple path for PoC frontend
async def poc_transcribe(input_data: TextInput):
    print(f"Received text: {input_data.text}")
    # In a real scenario, this would involve structuring logic (TASK-004)
    # For PoC, return a fixed structure
    structured_data = {
        "summary": f"Processed: {input_data.text[:50]}...",
        "identified_keywords": ["dummy", "poc", "test"],
        "original_length": len(input_data.text)
    }
    return structured_data

# --- Root Endpoint --- 
@app.get("/")
async def read_root():
    # Display loaded settings (useful for debugging, consider removing in production)
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "debug_mode": settings.DEBUG,
        "data_directory": str(settings.DATA_DIR)
        # Avoid exposing sensitive keys like API keys here!
    }

# --- API Routers ---
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
app.include_router(agent_router, prefix=f"{settings.API_V1_STR}/agent", tags=["agent"])

# Allow running directly for development
if __name__ == "__main__":
    # Use settings for host/port if defined, otherwise default
    uvicorn.run(
        "app.main:app", 
        host=getattr(settings, 'HOST', '0.0.0.0'), 
        port=getattr(settings, 'PORT', 8000), 
        reload=settings.DEBUG # Use debug setting for reload
    )
