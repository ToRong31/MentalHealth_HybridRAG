"""
Authentication endpoints.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.db.db_models.user import User
from src.schemas.user import UserCreate, UserLogin, UserResponse
from src.schemas.auth import AuthResponse
from src.services.auth_service import AuthService
from src.core.deps import get_current_user


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    auth_service = AuthService(db)
    return await auth_service.register(user_data)


@router.post("/login", response_model=AuthResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login user and return access token"""
    auth_service = AuthService(db)
    return await auth_service.login(credentials)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user information"""
    return UserResponse.model_validate(current_user)
