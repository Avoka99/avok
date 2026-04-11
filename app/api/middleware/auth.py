from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.security import decode_token, is_token_revoked
import logging

logger = logging.getLogger(__name__)

class RequestActor:
    def __init__(self, *, actor_id, role, is_guest=False, guest_session_id=None):
        self.id = actor_id
        self.role = role
        self.is_guest = is_guest
        self.guest_session_id = guest_session_id

    @property
    def rate_limit_key(self):
        if self.is_guest and self.guest_session_id is not None:
            return f"guest_{self.guest_session_id}"
        return f"user_{self.id}"

class AuthStateMiddleware(BaseHTTPMiddleware):
    """
    Middleware to attach user identity from JWT to request state.
    This runs before rate limiting and audit logging to ensure they are user-aware.
    """
    async def dispatch(self, request: Request, call_next):
        # Default to None
        request.state.user = None
        request.state.actor = None
        
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                if await is_token_revoked(token):
                    return await call_next(request)
                payload = decode_token(token)
                if payload and payload.get("type") == "access":
                    if payload.get("subject_type") == "guest_checkout":
                        guest_session_id = payload.get("guest_session_id")
                        if guest_session_id is not None:
                            actor = RequestActor(
                                actor_id=None,
                                role="user",
                                is_guest=True,
                                guest_session_id=int(guest_session_id),
                            )
                            request.state.actor = actor
                            request.state.user = actor
                    else:
                        sub = payload.get("sub")
                        if sub:
                            user_id = sub
                            if isinstance(sub, str) and ":" in sub:
                                user_id = sub.split(":")[1]

                            try:
                                user_id = int(user_id)
                            except (ValueError, TypeError):
                                pass

                            actor = RequestActor(
                                actor_id=user_id,
                                role=payload.get("role", "user"),
                            )
                            request.state.actor = actor
                            request.state.user = actor
            except Exception as e:
                # Middleware should not fail the request; 
                # authentication is strictly enforced by dependencies later.
                logger.debug(f"Auth middleware token decode failed: {e}")
                
        return await call_next(request)
