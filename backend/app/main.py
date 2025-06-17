from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.database import init_db, close_db, create_sample_user
from app.core.config import settings
from app.api.v1.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await init_db()
        print("Database initialized successfully")
        # Create sample user for development
        if settings.DEBUG:
            await create_sample_user()
    except Exception as e:
        print(f"Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        # For Lambda, we'll skip database init if it fails and initialize per request
        pass
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    debug=settings.DEBUG
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://donx85isqomd0.cloudfront.net",  # New frontend CloudFront URL
        "http://cassidy-frontend-538881967423.s3-website-us-east-1.amazonaws.com",  # New S3 direct URL
        "http://cassidy-frontend-1748872354.s3-website-us-east-1.amazonaws.com",  # Old URL for compatibility
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://localhost:5174"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}




@app.get("/")
async def root():
    try:
        return {"message": f"Welcome to {settings.APP_NAME}"}
    except Exception as e:
        print(f"Root endpoint error: {e}")
        return {"message": "Welcome to Cassidy AI Journaling Assistant"}



# Lambda handler for AWS deployment  
from mangum import Mangum
lambda_handler = Mangum(app, lifespan="on")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)