"""
Authentication service for user registration and login.
"""
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from src.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token
from src.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from src.db.repositories.user_repository import UserRepository
from src.db.db_models.user import User
from src.schemas.user import UserCreate, UserLogin
from src.schemas.auth import AuthResponse, UserResponse, TokenResponse


class AuthService:
    """Service for authentication operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
    
    async def register(self, user_data: UserCreate) -> AuthResponse:
        """Register a new user"""
        # Check if email already exists
        existing_user = await self.user_repo.get_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Check if username already exists
        existing_username = await self.user_repo.get_by_username(user_data.username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Create new user
        hashed_password = get_password_hash(user_data.password)
        new_user = await self.user_repo.create(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password
        )
        
        await self.db.commit()
        await self.db.refresh(new_user)
        
        # Create access and refresh tokens
        access_token = create_access_token(data={"sub": str(new_user.id)})
        refresh_token = create_refresh_token(data={"sub": str(new_user.id)})
        
        return AuthResponse(
            user=UserResponse.model_validate(new_user),
            token=TokenResponse(
                access_token=access_token,
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
            ),
            refresh_token=refresh_token
        )
    
    async def login(self, credentials: UserLogin) -> AuthResponse:
        """Login user and return access token"""
        user = await self.authenticate_user(credentials.email, credentials.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access and refresh tokens
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        return AuthResponse(
            user=UserResponse.model_validate(user),
            token=TokenResponse(
                access_token=access_token,
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
            ),
            refresh_token=refresh_token
        )
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user with email and password"""
        user = await self.user_repo.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Generate new access token from refresh token"""
        try:
            payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            token_type: str = payload.get("type")
            
            if user_id is None or token_type != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            # Verify user still exists
            user = await self.user_repo.get_by_id(int(user_id))
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
            
            # Create new access token
            access_token = create_access_token(data={"sub": str(user_id)})
            
            return TokenResponse(
                access_token=access_token,
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
            )
            
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
