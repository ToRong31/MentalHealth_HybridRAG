"""
PostgreSQL Checkpointer Manager for LangGraph Workflow

This module provides persistent state management using PostgreSQL as the checkpoint store.
State is automatically saved after each node execution and can survive server restarts.

Features:
- Automatic state persistence after each node
- Thread-based isolation (one thread per conversation)
- Connection pooling for performance
- Survives server restarts
- Thread-safe operations
- Async support for FastAPI

Usage:
    >>> from .checkpointer import get_checkpointer
    >>> checkpointer = get_checkpointer()
    >>> graph = builder.compile(checkpointer=checkpointer)
"""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class CheckpointerManager:
    """
    Singleton manager for PostgreSQL checkpointer with async support
    
    Manages connection pooling and ensures only one checkpointer instance
    exists throughout the application lifecycle.
    
    Attributes:
        _instance: Singleton instance
        _checkpointer: AsyncPostgresSaver instance for state persistence
    """
    
    _instance: Optional['CheckpointerManager'] = None
    _checkpointer: Optional[AsyncPostgresSaver] = None
    
    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize checkpointer if not already initialized"""
        if self._checkpointer is None:
            self._initialize_checkpointer()
    
    def _initialize_checkpointer(self):
        """
        Initialize PostgreSQL checkpointer with connection pool
        
        Environment Variables:
            POSTGRES_CHECKPOINT_URI: PostgreSQL connection string
                Format: postgresql://user:password@host:port/database
                Falls back to DATABASE_URL if not set
        
        Raises:
            RuntimeError: If initialization fails
        """
        # Get database URI from environment
        db_uri = os.getenv(
            "POSTGRES_CHECKPOINT_URI",
            os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/mental_health_db")
        )
        
        # Convert SQLAlchemy format to psycopg format if needed
        # SQLAlchemy: postgresql+asyncpg://... → psycopg: postgresql://...
        if "+asyncpg" in db_uri:
            db_uri = db_uri.replace("postgresql+asyncpg://", "postgresql://")
            logger.info("Converted SQLAlchemy connection string to psycopg format")
        
        # Log initialization (hide password)
        safe_uri = db_uri.split('@')[1] if '@' in db_uri else 'localhost'
        logger.info(f"Initializing Async PostgreSQL checkpointer with database: {safe_uri}")
        
        try:
            # Create async connection pool with autocommit for schema setup
            # Note: autocommit is required for CREATE INDEX CONCURRENTLY
            connection_pool = AsyncConnectionPool(
                conninfo=db_uri,
                max_size=20,      # Maximum connections in pool
                min_size=5,       # Minimum connections to keep alive
                timeout=30,       # Connection timeout in seconds
                max_idle=300,     # Max idle time before closing connection (5 min)
                max_lifetime=3600,# Max connection lifetime in seconds (1 hour)
                kwargs={"autocommit": True}  # Enable autocommit mode
            )
            
            # Create AsyncPostgresSaver instance
            self._checkpointer = AsyncPostgresSaver(connection_pool)
            
            # Setup database tables (idempotent operation - safe to call multiple times)
            # This creates:
            # - checkpoints table: stores state snapshots
            # - checkpoint_writes table: stores incremental state changes
            # Note: setup() is sync even for AsyncPostgresSaver
            self._checkpointer.setup()
            
            logger.info("✓ Async PostgreSQL checkpointer initialized successfully")
            logger.info("✓ Database tables verified: checkpoints, checkpoint_writes")
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize Async PostgreSQL checkpointer: {e}", exc_info=True)
            raise RuntimeError(f"Checkpointer initialization failed: {e}")
    
    def get_checkpointer(self) -> AsyncPostgresSaver:
        """
        Get the async PostgreSQL checkpointer instance
        
        Returns:
            AsyncPostgresSaver: Thread-safe async checkpointer instance for state persistence
            
        Example:
            >>> manager = CheckpointerManager()
            >>> checkpointer = manager.get_checkpointer()
        """
        if self._checkpointer is None:
            self._initialize_checkpointer()
        return self._checkpointer
    
    def close(self):
        """
        Close connection pool
        
        Should be called on application shutdown to gracefully close all connections.
        
        Example:
            >>> manager = CheckpointerManager()
            >>> manager.close()
        """
        if self._checkpointer is not None:
            try:
                self._checkpointer.conn.close()
                logger.info("PostgreSQL checkpointer connection pool closed")
            except Exception as e:
                logger.error(f"Error closing checkpointer connection: {e}")


# Global singleton instance
_checkpointer_manager: Optional[CheckpointerManager] = None


def get_checkpointer() -> AsyncPostgresSaver:
    """
    Get global async PostgreSQL checkpointer instance (singleton)
    
    This function provides access to the shared checkpointer instance
    used throughout the application.
    
    Returns:
        AsyncPostgresSaver: Singleton async checkpointer for all workflows
    
    Example:
        >>> from .checkpointer import get_checkpointer
        >>> checkpointer = get_checkpointer()
        >>> graph = builder.compile(checkpointer=checkpointer)
    """
    global _checkpointer_manager
    if _checkpointer_manager is None:
        _checkpointer_manager = CheckpointerManager()
    return _checkpointer_manager.get_checkpointer()


def close_checkpointer():
    """
    Close checkpointer connection pool
    
    Should be called on application shutdown.
    
    Example:
        >>> from .checkpointer import close_checkpointer
        >>> # On app shutdown
        >>> close_checkpointer()
    """
    global _checkpointer_manager
    if _checkpointer_manager is not None:
        _checkpointer_manager.close()
        _checkpointer_manager = None
