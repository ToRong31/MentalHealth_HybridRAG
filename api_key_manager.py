"""
API Key Manager for rotating Google Generative AI API keys
Handles key rotation, rate limiting, and error management
"""
import time
from typing import List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


def load_api_keys_from_file(file_path: str) -> List[str]:
    """
    Load all API keys from file (one key per line)
    
    Args:
        file_path: Path to API key file
    
    Returns:
        List of API keys
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        keys = [line.strip() for line in f if line.strip()]
    return keys


def load_api_keys_by_lines(file_path: str, line_spec: str) -> List[str]:
    """
    Load API keys from specific lines in file
    
    Args:
        file_path: Path to API key file
        line_spec: Line specification like "1-10,15,20-25"
    
    Returns:
        List of API keys from specified lines
    """
    all_keys = load_api_keys_from_file(file_path)
    
    indices = set()
    parts = line_spec.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            # Range like "1-10"
            start, end = part.split('-')
            indices.update(range(int(start) - 1, int(end)))  # Convert to 0-indexed
        else:
            # Single line
            indices.add(int(part) - 1)  # Convert to 0-indexed
    
    selected_keys = [all_keys[i] for i in sorted(indices) if i < len(all_keys)]
    return selected_keys


@dataclass
class APIKeyStatus:
    """Track status of individual API key"""
    key: str
    is_active: bool = True
    total_calls: int = 0
    error_count: int = 0
    last_used: float = 0.0
    ban_reason: Optional[str] = None


class APIKeyManager:
    """
    Manages multiple API keys with rotation and error handling
    """
    
    def __init__(self, api_keys: List[str], min_delay_between_calls: float = 1.0):
        """
        Initialize API Key Manager
        
        Args:
            api_keys: List of API keys to manage
            min_delay_between_calls: Minimum seconds between API calls
        """
        self.keys = [APIKeyStatus(key=key) for key in api_keys]
        self.current_index = 0
        self.min_delay = min_delay_between_calls
        self.banned_keys = set()
        
        if not self.keys:
            raise ValueError("No API keys provided")
        
        logger.info(f"Initialized API Key Manager with {len(self.keys)} keys")
    
    def get_next_key(self) -> str:
        """
        Get next available API key with automatic rotation
        
        Key rotation happens BEFORE returning the key, so every call
        to this method automatically moves to the next key regardless
        of success or failure of the previous call.
        
        Returns:
            API key string
        
        Raises:
            RuntimeError: If no active keys available
        """
        attempts = 0
        max_attempts = len(self.keys)
        
        while attempts < max_attempts:
            # Get current key (but will rotate immediately after)
            key_status = self.keys[self.current_index]
            current_key_index = self.current_index
            
            # ALWAYS rotate to next key (happens regardless of success/failure)
            # This ensures we never use the same key twice in a row
            self.current_index = (self.current_index + 1) % len(self.keys)
            attempts += 1
            
            # Check if the key we got is active
            if key_status.is_active:
                # Enforce minimum delay since last use
                time_since_last_use = time.time() - key_status.last_used
                if time_since_last_use < self.min_delay:
                    sleep_time = self.min_delay - time_since_last_use
                    logger.debug(f"Sleeping {sleep_time:.2f}s for rate limiting")
                    time.sleep(sleep_time)
                
                key_status.last_used = time.time()
                key_status.total_calls += 1
                
                # Log rotation
                logger.debug(
                    f"Using key #{current_key_index + 1} "
                    f"(call #{key_status.total_calls}), "
                    f"next will be key #{self.current_index + 1}"
                )
                
                return key_status.key
            else:
                # Key is banned/inactive, continue to next key
                logger.debug(f"Skipping banned key #{current_key_index + 1}, trying next")
        
        # No active keys available
        raise RuntimeError(
            f"No active API keys available. "
            f"Banned: {len(self.banned_keys)}/{len(self.keys)}"
        )
    
    def handle_error(self, api_key: str, status_code: int, error_message: str = ""):
        """
        Handle API errors and update key status
        
        Args:
            api_key: The API key that encountered an error
            status_code: HTTP status code
            error_message: Error message details
        """
        key_status = self._find_key_status(api_key)
        if not key_status:
            logger.warning(f"API key not found in manager: {api_key[:10]}...")
            return
        
        key_status.error_count += 1
        
        if status_code == 429:
            # Rate limit - temporary, don't ban
            logger.warning(
                f"Rate limit (429) hit for key {api_key[:10]}... "
                f"(call #{key_status.total_calls})"
            )
        elif status_code in [401, 403]:
            # Authentication/Authorization error - ban the key
            key_status.is_active = False
            key_status.ban_reason = f"HTTP {status_code}: {error_message}"
            self.banned_keys.add(api_key)
            logger.error(
                f"Key {api_key[:10]}... BANNED due to {status_code} error. "
                f"Reason: {error_message}"
            )
        else:
            # Other errors
            logger.error(
                f"Error {status_code} for key {api_key[:10]}...: {error_message}"
            )
    
    def mark_success(self, api_key: str):
        """
        Mark a successful API call
        
        Args:
            api_key: The API key that succeeded
        """
        key_status = self._find_key_status(api_key)
        if key_status:
            # Reset error count on success
            key_status.error_count = 0
    
    def _find_key_status(self, api_key: str) -> Optional[APIKeyStatus]:
        """Find key status by API key"""
        for key_status in self.keys:
            if key_status.key == api_key:
                return key_status
        return None
    
    def get_active_keys_count(self) -> int:
        """Get count of active (non-banned) keys"""
        return sum(1 for k in self.keys if k.is_active)
    
    def get_stats(self) -> dict:
        """Get statistics about API key usage"""
        active_keys = [k for k in self.keys if k.is_active]
        
        stats = {
            "total_keys": len(self.keys),
            "active_keys": len(active_keys),
            "banned_keys": len(self.banned_keys),
            "total_calls": sum(k.total_calls for k in self.keys),
            "total_errors": sum(k.error_count for k in self.keys),
        }
        
        if active_keys:
            stats["avg_calls_per_key"] = stats["total_calls"] / len(active_keys)
        
        return stats
    
    def print_summary(self):
        """Print summary of API key usage"""
        stats = self.get_stats()
        logger.info("=" * 60)
        logger.info("API Key Manager Summary")
        logger.info("=" * 60)
        logger.info(f"Total Keys: {stats['total_keys']}")
        logger.info(f"Active Keys: {stats['active_keys']}")
        logger.info(f"Banned Keys: {stats['banned_keys']}")
        logger.info(f"Total API Calls: {stats['total_calls']}")
        logger.info(f"Total Errors: {stats['total_errors']}")
        if "avg_calls_per_key" in stats:
            logger.info(f"Avg Calls/Key: {stats['avg_calls_per_key']:.1f}")
        logger.info("=" * 60)

