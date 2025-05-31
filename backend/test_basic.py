"""Basic test to verify the backend setup works"""
import asyncio
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_basic_setup():
    """Test basic database and authentication setup"""
    from app.database import init_db, close_db, async_session_maker
    from app.services.auth import AuthService
    from app.models.api import RegisterRequest, LoginRequest
    
    print("🚀 Testing backend setup...")
    
    # Initialize database
    print("1. Initializing database...")
    await init_db()
    print("✅ Database initialized")
    
    # Test user creation
    print("2. Testing user creation...")
    from app.database import get_db
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    try:
        auth_service = AuthService(db)
        
        # Register a test user
        register_request = RegisterRequest(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        try:
            register_response = await auth_service.register_user(register_request)
            print(f"✅ User created: {register_response.username} (ID: {register_response.user_id})")
        except ValueError as e:
            print(f"⚠️  User creation failed (might already exist): {e}")
        
        # Test login
        login_request = LoginRequest(
            username="testuser",
            password="testpass123"
        )
        
        try:
            login_response = await auth_service.login_user(login_request)
            print(f"✅ Login successful: Token expires in {login_response.expires_in} seconds")
        except ValueError as e:
            print(f"❌ Login failed: {e}")
            return False
            
    finally:
        await db_gen.aclose()
    
    # Cleanup
    await close_db()
    print("✅ Database connection closed")
    
    print("🎉 Basic setup test completed successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_basic_setup())
    if not success:
        sys.exit(1)