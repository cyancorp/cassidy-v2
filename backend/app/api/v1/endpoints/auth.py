from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.auth import AuthService
from app.models.api import (
    LoginRequest, LoginResponse, 
    RegisterRequest, RegisterResponse,
    UserProfileResponse
)
from app.core.deps import get_current_user
from app.models.user import UserDB

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    auth_service = AuthService(db)
    try:
        return await auth_service.register_user(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return access token"""
    auth_service = AuthService(db)
    
    # Extract user agent and IP
    user_agent = http_request.headers.get("user-agent")
    ip_address = http_request.client.host if http_request.client else None
    
    try:
        return await auth_service.login_user(request, user_agent, ip_address)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/logout")
async def logout(
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout current user"""
    # Note: In a real implementation, you'd extract the token from the request
    # and pass it to logout_user. This is simplified for now.
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: UserDB = Depends(get_current_user)
):
    """Get current user profile"""
    return UserProfileResponse(
        user_id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at
    )