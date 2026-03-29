from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.security import decode_token
import logging

logger = logging.getLogger(__name__)

class AuthStateMiddleware(BaseHTTPMiddleware):
    """
    Middleware to attach user identity from JWT to request state.
    This runs before rate limiting and audit logging to ensure they are user-aware.
    """
    async def dispatch(self, request: Request, call_next):
        # Default to None
        request.state.user = None
        
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = decode_token(token)
                if payload and payload.get("type") == "access":
                    sub = payload.get("sub")
                    if sub:
                        # Extract numeric ID for consistency
                        user_id = sub
                        if isinstance(sub, str) and ":" in sub:
                            # Handle 'guest:123' or similar formats
                            user_id = sub.split(":")[1]
                        
                        try:
                            user_id = int(user_id)
                        except (ValueError, TypeError):
                            pass
                            
                        # Create a lightweight user object for middleware consumption
                        # This avoids a database hit on every request
                        class RequestUser:
                            def __init__(self, uid):
                                self.id = uid
                                
                        request.state.user = RequestUser(user_id)
            except Exception as e:
                # Middleware should not fail the request; 
                # authentication is strictly enforced by dependencies later.
                logger.debug(f"Auth middleware token decode failed: {e}")
                
        return await call_next(request)
