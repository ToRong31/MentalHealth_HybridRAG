"""
Dependencies for FastAPI routes.
Provides database sessions and current user authentication.
"""
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from src.db.session import get_db
from src.db.db_models.user import User
from src.db.repositories.user_repository import UserRepository
from src.schemas.auth import TokenData
from .config import SECRET_KEY, ALGORITHM


logger = logging.getLogger(__name__)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.
    Use as a dependency in protected routes.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode token with verify_sub=False to handle legacy tokens where sub might be int
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_sub": False}
        )
        
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            logger.error("[AUTH] No 'sub' field in token payload")
            raise credentials_exception
            
        # Handle both string and int subjects
        user_id = int(str(user_id_raw))
        token_data = TokenData(user_id=user_id)
        
    except JWTError as e:
        logger.error(f"[AUTH] JWT decode error: {e}")
        raise credentials_exception
    except ValueError:
        logger.error("[AUTH] Invalid user ID format in token")
        raise credentials_exception
    
    # Use repository to get user
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(token_data.user_id)
    
    if user is None:
        logger.error(f"[AUTH] User not found for ID: {token_data.user_id}")
        raise credentials_exception
    
    logger.info(f"[AUTH] User authenticated: {user.username}")
    return user
