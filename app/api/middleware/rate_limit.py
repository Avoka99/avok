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
    
    MAX_FALLBACK_KEYS = 10000
    
    def __init__(self):
        self.redis_client = None
        self._fallback_requests = defaultdict(list)
        self._fallback_cleanup_counter = 0
    
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
        
        # Periodic cleanup to prevent unbounded growth
        self._fallback_cleanup_counter += 1
        if self._fallback_cleanup_counter >= 1000:
            self._fallback_cleanup_counter = 0
            self._cleanup_fallback()
        
        return True
    
    def _cleanup_fallback(self):
        """Remove expired keys and cap total keys to prevent memory exhaustion."""
        now = time.time()
        window_start = now - settings.rate_limit_period
        
        # Remove empty keys
        empty_keys = [k for k, v in self._fallback_requests.items() if not v]
        for k in empty_keys:
            del self._fallback_requests[k]
        
        # If still too many keys, remove oldest
        if len(self._fallback_requests) > self.MAX_FALLBACK_KEYS:
            sorted_keys = sorted(
                self._fallback_requests.keys(),
                key=lambda k: max(self._fallback_requests[k], default=0)
            )
            for k in sorted_keys[:len(sorted_keys) // 4]:
                del self._fallback_requests[k]
            logger.warning(f"Fallback rate limiter cleanup: removed {len(sorted_keys) // 4} oldest keys")
    
    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed using Redis sliding window."""
        redis = self._get_redis()
        
        if redis is None:
            logger.warning("Redis unavailable - using fallback rate limiter")
            return self._fallback_rate_limit(key)
        
        now = time.time()
        window_start = now - settings.rate_limit_period
        redis_key = f"rate_limit:{key}"
        
        try:
            await redis.zremrangebyscore(redis_key, 0, window_start)
            request_count = await redis.zcard(redis_key)
            await redis.zadd(redis_key, {str(now): now})
            await redis.expire(redis_key, settings.rate_limit_period)
            
            if request_count >= settings.rate_limit_requests:
                await redis.zrem(redis_key, str(now))
                logger.warning(f"Rate limit exceeded for key: {key}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}, falling back to in-memory")
            return self._fallback_rate_limit(key)


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    # Known trusted proxy IPs (configure via env in production)
    TRUSTED_PROXIES = {"127.0.0.1", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"}
    
    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)
        
        # Priority 1: Authenticated User ID
        client_id = None
        actor = getattr(request.state, "actor", None) or getattr(request.state, "user", None)
        if actor:
            client_id = getattr(actor, "rate_limit_key", None)
            if not client_id and getattr(actor, "id", None) is not None:
                client_id = f"user_{actor.id}"
        
        # Priority 2: X-Forwarded-For (only from trusted proxies)
        if not client_id:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded and self._is_trusted_proxy(request.client.host if request.client else ""):
                # Use the leftmost (original client) IP
                client_id = f"ip_{forwarded.split(',')[0].strip()}"
            elif forwarded:
                logger.debug(f"Ignoring X-Forwarded-For from untrusted IP: {request.client.host if request.client else 'unknown'}")
        
        # Priority 3: Direct IP
        if not client_id:
            client_id = f"ip_{request.client.host if request.client else 'unknown'}"
        
        if not await rate_limiter.is_allowed(client_id):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {settings.rate_limit_requests} requests per {settings.rate_limit_period} seconds."
            )
        
        return await call_next(request)
    
    def _is_trusted_proxy(self, ip: str) -> bool:
        """Check if the IP is from a trusted proxy range."""
        import ipaddress
        if not ip:
            return False
        try:
            client_ip = ipaddress.ip_address(ip)
            for cidr in self.TRUSTED_PROXIES:
                if "/" in cidr:
                    if client_ip in ipaddress.ip_network(cidr):
                        return True
                elif ip == cidr:
                    return True
        except ValueError:
            pass
        return False
