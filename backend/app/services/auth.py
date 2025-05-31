from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user import UserRepository, AuthSessionRepository
from app.core.security import SecurityService
from app.models.api import LoginRequest, RegisterRequest, LoginResponse, RegisterResponse
from app.models.user import UserDB
from datetime import datetime, timedelta
from typing import Optional
import hashlib


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository()
        self.auth_session_repo = AuthSessionRepository()
        self.security = SecurityService()
    
    async def register_user(self, request: RegisterRequest) -> RegisterResponse:
        """Register a new user"""
        # Check if username already exists
        existing_user = await self.user_repo.get_by_username(self.db, request.username)
        if existing_user:
            raise ValueError("Username already exists")
        
        # Check if email already exists (if provided)
        if request.email:
            existing_email = await self.user_repo.get_by_email(self.db, request.email)
            if existing_email:
                raise ValueError("Email already exists")
        
        # Hash password and create user
        password_hash = self.security.hash_password(request.password)
        user = await self.user_repo.create_user(
            self.db, 
            username=request.username,
            email=request.email,
            password_hash=password_hash
        )
        
        return RegisterResponse(
            user_id=user.id,
            username=user.username
        )
    
    async def login_user(
        self, 
        request: LoginRequest, 
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> LoginResponse:
        """Authenticate user and create session"""
        # Find user by username
        user = await self.user_repo.get_by_username(self.db, request.username)
        if not user:
            raise ValueError("Invalid credentials")
        
        # Verify password
        if not self.security.verify_password(request.password, user.password_hash):
            raise ValueError("Invalid credentials")
        
        # Create access token
        expires_delta = timedelta(hours=24)
        access_token = self.security.create_access_token(
            user_id=str(user.id),
            username=user.username,
            expires_delta=expires_delta
        )
        
        # Create session record
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()
        expires_at = datetime.utcnow() + expires_delta
        
        await self.auth_session_repo.create_session(
            self.db,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address
        )
        
        return LoginResponse(
            access_token=access_token,
            expires_in=int(expires_delta.total_seconds()),
            user_id=user.id,
            username=user.username
        )
    
    async def logout_user(self, token: str) -> bool:
        """Logout user by revoking session"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return await self.auth_session_repo.revoke_session(self.db, token_hash)
    
    async def get_current_user(self, token: str) -> Optional[UserDB]:
        """Get current user from token"""
        # Decode token
        payload = self.security.decode_token(token)
        if not payload:
            return None
        
        # Check if session is valid
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session = await self.auth_session_repo.get_by_token_hash(self.db, token_hash)
        if not session:
            return None
        
        # Get user
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        return await self.user_repo.get_by_id(self.db, user_id)