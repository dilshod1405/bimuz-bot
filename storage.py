"""Storage for user session data using Redis."""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json
import redis.asyncio as redis
from config import REDIS_URL
import logging

logger = logging.getLogger(__name__)


class UserStorage:
    """Redis-based storage for user sessions."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._redis_url = REDIS_URL
    
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self.redis_client is None:
            try:
                self.redis_client = await redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    encoding="utf-8"
                )
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                raise
        return self.redis_client
    
    def _get_key(self, user_id: int) -> str:
        """Get Redis key for user session."""
        return f"bot:session:{user_id}"
    
    async def set_user_data(self, user_id: int, access_token: str, refresh_token: str, employee_data: Dict[str, Any]):
        """Store user session data."""
        try:
            redis_client = await self._get_redis()
            key = self._get_key(user_id)
            
            session_data = {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'employee': json.dumps(employee_data, default=str),
                'last_activity': datetime.now().isoformat()
            }
            
            # Store with 7 days expiration (same as refresh token lifetime)
            await redis_client.hset(key, mapping=session_data)
            await redis_client.expire(key, 7 * 24 * 60 * 60)  # 7 days
        except Exception as e:
            logger.error(f"Error storing user data: {str(e)}")
            raise
    
    async def get_user_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user session data."""
        try:
            redis_client = await self._get_redis()
            key = self._get_key(user_id)
            
            data = await redis_client.hgetall(key)
            if not data:
                return None
            
            # Parse employee data
            if 'employee' in data:
                data['employee'] = json.loads(data['employee'])
            
            return data
        except Exception as e:
            logger.error(f"Error getting user data: {str(e)}")
            return None
    
    async def get_access_token(self, user_id: int) -> Optional[str]:
        """Get access token for user."""
        try:
            redis_client = await self._get_redis()
            key = self._get_key(user_id)
            return await redis_client.hget(key, 'access_token')
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            return None
    
    async def get_refresh_token(self, user_id: int) -> Optional[str]:
        """Get refresh token for user."""
        try:
            redis_client = await self._get_redis()
            key = self._get_key(user_id)
            return await redis_client.hget(key, 'refresh_token')
        except Exception as e:
            logger.error(f"Error getting refresh token: {str(e)}")
            return None
    
    async def get_employee(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get employee data for user."""
        try:
            redis_client = await self._get_redis()
            key = self._get_key(user_id)
            employee_json = await redis_client.hget(key, 'employee')
            if employee_json:
                return json.loads(employee_json)
            return None
        except Exception as e:
            logger.error(f"Error getting employee data: {str(e)}")
            return None
    
    async def update_access_token(self, user_id: int, access_token: str):
        """Update access token for user."""
        try:
            redis_client = await self._get_redis()
            key = self._get_key(user_id)
            
            await redis_client.hset(key, 'access_token', access_token)
            await redis_client.hset(key, 'last_activity', datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Error updating access token: {str(e)}")
    
    async def remove_user(self, user_id: int):
        """Remove user session."""
        try:
            redis_client = await self._get_redis()
            key = self._get_key(user_id)
            await redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error removing user: {str(e)}")
    
    async def is_authenticated(self, user_id: int) -> bool:
        """Check if user is authenticated."""
        try:
            access_token = await self.get_access_token(user_id)
            return access_token is not None
        except Exception as e:
            logger.error(f"Error checking authentication: {str(e)}")
            return False
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None


# Global storage instance
user_storage = UserStorage()
