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
        "https://d2b6nthvtvfv18.cloudfront.net",  # Current frontend CloudFront URL
        "https://d210qplqjgsgxr.cloudfront.net",  # Previous CloudFront URL for compatibility
        "https://donx85isqomd0.cloudfront.net",  # Previous CloudFront URL for compatibility
        "http://cassidy-frontend-538881967423.s3-website-us-east-1.amazonaws.com",  # S3 direct URL
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

# Internet connectivity test endpoint
@app.get("/test-internet")
async def test_internet():
    import httpx
    import time
    
    results = {
        "timestamp": time.time(),
        "tests": {}
    }
    
    # Test basic HTTP connectivity
    try:
        start_time = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://httpbin.org/get")
            duration = time.time() - start_time
            results["tests"]["httpbin_http"] = {
                "status": "success",
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            }
    except Exception as e:
        duration = time.time() - start_time
        results["tests"]["httpbin_http"] = {
            "status": "failed",
            "error": str(e),
            "duration_ms": round(duration * 1000, 2)
        }
    
    # Test HTTPS connectivity
    try:
        start_time = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://httpbin.org/get")
            duration = time.time() - start_time
            results["tests"]["httpbin_https"] = {
                "status": "success", 
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            }
    except Exception as e:
        duration = time.time() - start_time
        results["tests"]["httpbin_https"] = {
            "status": "failed",
            "error": str(e),
            "duration_ms": round(duration * 1000, 2)
        }
    
    # Test Anthropic API connectivity
    try:
        start_time = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.anthropic.com/")
            duration = time.time() - start_time
            results["tests"]["anthropic_api"] = {
                "status": "success",
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            }
    except Exception as e:
        duration = time.time() - start_time
        results["tests"]["anthropic_api"] = {
            "status": "failed",
            "error": str(e),
            "duration_ms": round(duration * 1000, 2)
        }
    
    # Test Google DNS
    try:
        start_time = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://8.8.8.8")
            duration = time.time() - start_time
            results["tests"]["google_dns"] = {
                "status": "success",
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            }
    except Exception as e:
        duration = time.time() - start_time
        results["tests"]["google_dns"] = {
            "status": "failed",
            "error": str(e),
            "duration_ms": round(duration * 1000, 2)
        }
    
    return results




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