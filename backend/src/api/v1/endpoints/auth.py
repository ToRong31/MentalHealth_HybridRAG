"""
Authentication endpoints.
"""
from fastapi import APIRouter, Depends, status, Response, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.db.db_models.user import User
from src.schemas.user import UserCreate, UserLogin, UserResponse
from src.schemas.auth import AuthResponse, TokenResponse
from src.services.auth_service import AuthService
from src.core.deps import get_current_user
from src.core.config import ACCESS_TOKEN_EXPIRE_MINUTES


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    auth_service = AuthService(db)
    auth_response = await auth_service.register(user_data)
    
    # Set refresh token in httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=auth_response.refresh_token,
        httponly=True,
        secure=True,  # Use HTTPS in production
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    return auth_response


@router.post("/login", response_model=AuthResponse)
async def login(
    credentials: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login user and return access token"""
    auth_service = AuthService(db)
    auth_response = await auth_service.login(credentials)
    
    # Set refresh token in httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=auth_response.refresh_token,
        httponly=True,
        secure=True,  # Use HTTPS in production
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    return auth_response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token from cookie"""
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found"
        )
    
    auth_service = AuthService(db)
    return await auth_service.refresh_access_token(refresh_token)


@router.get("/check")
async def check_token(
    current_user: User = Depends(get_current_user)
):
    """Check if current access token is valid"""
    return {
        "valid": True,
        "user_id": current_user.id,
        "email": current_user.email
    }


@router.post("/logout")
async def logout(response: Response):
    """Logout user by clearing refresh token cookie"""
    response.delete_cookie(key="refresh_token")
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user information"""
    return UserResponse.model_validate(current_user)
