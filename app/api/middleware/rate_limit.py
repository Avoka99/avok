from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging
from collections import defaultdict

from app.core.config import settings
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-based rate limiter using sliding window algorithm with fallback."""
    
    def __init__(self):
        self.redis_client = None
        self._fallback_requests = defaultdict(list)
    
    def _get_redis(self):
        """Get or create Redis client."""
        if self.redis_client is None:
            try:
                self.redis_client = get_redis_client()
            except Exception as e:
                logger.error(f"Failed to get Redis client: {e}")
                return None
        return self.redis_client
    
    def _fallback_rate_limit(self, key: str) -> bool:
        """Fallback in-memory rate limiter when Redis unavailable."""
        now = time.time()
        window_start = now - settings.rate_limit_period
        
        self._fallback_requests[key] = [
            req_time for req_time in self._fallback_requests[key]
            if req_time > window_start
        ]
        
        if len(self._fallback_requests[key]) >= settings.rate_limit_requests:
            logger.warning(f"Fallback rate limit exceeded for key: {key}")
            return False
        
        self._fallback_requests[key].append(now)
        return True
    
    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed using Redis sliding window."""
        redis = self._get_redis()
        
        if redis is None:
            logger.warning("Redis unavailable - using fallback rate limiter")
            return self._fallback_rate_limit(key)
        
        now = time.time()
        window_start = now - settings.rate_limit_period
        redis_key = f"rate_limit:{key}"
        
        try:
            pipe = redis.pipeline()
            
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, settings.rate_limit_period)
            
            results = pipe.execute()
            request_count = results[1]
            
            if request_count >= settings.rate_limit_requests:
                redis.zrem(redis_key, str(now))
                logger.warning(f"Rate limit exceeded for key: {key}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}, falling back to in-memory")
            return self._fallback_rate_limit(key)


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)
        
        # Priority 1: Authenticated User ID
        client_id = None
        if hasattr(request.state, "user") and request.state.user:
            client_id = f"user_{request.state.user.id}"
        
        # Priority 2: X-Forwarded-For (Proxies)
        if not client_id:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                client_id = f"ip_{forwarded.split(',')[0].strip()}"
        
        # Priority 3: Direct IP
        if not client_id:
            client_id = f"ip_{request.client.host if request.client else 'unknown'}"
        
        if not rate_limiter.is_allowed(client_id):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {settings.rate_limit_requests} requests per {settings.rate_limit_period} seconds."
            )
        
        return await call_next(request)
