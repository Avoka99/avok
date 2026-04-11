from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

MONEY_ACTION_TYPES = {
    "escrow_funding",
    "escrow_release_confirmed",
    "wallet_withdrawal",
    "wallet_deposit",
    "dispute_opened",
    "dispute_resolved",
    "escrow_cancelled",
    "admin_action",
}


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware for audit logging with money-action tracking."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now(timezone.utc)
        path = request.url.path
        method = request.method
        
        actor = getattr(request.state, "actor", None) or getattr(request.state, "user", None)
        actor_id = None
        actor_type = None
        if actor:
            if getattr(actor, "is_guest", False):
                actor_id = getattr(actor, "guest_session_id", None)
                actor_type = "guest_checkout"
            else:
                actor_id = getattr(actor, "id", None)
                actor_type = "user"
        
        response = await call_next(request)
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        event_type = self._classify_event(path, method)
        
        audit_entry = {
            "timestamp": start_time.isoformat(),
            "event_type": event_type,
            "method": method,
            "path": path,
            "client_ip": request.client.host if request.client else None,
            "forwarded_for": request.headers.get("X-Forwarded-For"),
            "user_id": actor_id,
            "actor_type": actor_type,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "user_agent": request.headers.get("user-agent")
        }
        
        if event_type in MONEY_ACTION_TYPES or response.status_code >= 400:
            logger.info(f"Audit Log: {json.dumps(audit_entry)}")
            await self._store_audit_log(audit_entry)
        
        return response
    
    def _classify_event(self, path: str, method: str) -> str:
        if method not in {"POST", "PUT", "DELETE", "PATCH"}:
            return "api_request"
        
        if "/fund" in path:
            return "escrow_funding"
        if "/confirm" in path and "/delivery/" not in path:
            return "escrow_release_confirmed"
        if "/delivery/confirm" in path:
            return "escrow_release_confirmed"
        if "/withdraw" in path:
            return "wallet_withdrawal"
        if "/deposit" in path:
            return "wallet_deposit"
        if "/disputes" in path and method == "POST" and "/resolve" not in path and "/evidence" not in path:
            return "dispute_opened"
        if "/disputes" in path and "/resolve" in path:
            return "dispute_resolved"
        if "/cancel" in path:
            return "escrow_cancelled"
        if "/admin" in path:
            return "admin_action"
        
        return "api_request"
    
    async def _store_audit_log(self, entry: dict):
        """Store audit log in Redis for background processing."""
        try:
            from app.core.redis_client import get_redis_client
            redis = get_redis_client()
            if redis:
                import asyncio
                asyncio.create_task(self._async_store_audit_log(entry))
        except Exception as e:
            logger.error(f"Failed to store audit log: {e}")
    
    async def _async_store_audit_log(self, entry: dict):
        """Async store audit log."""
        try:
            from app.core.redis_client import get_redis_client
            redis = get_redis_client()
            if redis:
                await redis.lpush("audit_logs:pending", json.dumps(entry))
                await redis.ltrim("audit_logs:pending", 0, 9999)
        except Exception as e:
            logger.error(f"Failed to async store audit log: {e}")
