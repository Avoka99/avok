from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

AUDIT_LOG_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
AUDIT_LOG_STATUS_CODES = {200, 201, 204, 400, 401, 403, 404, 500}


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware for audit logging."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.utcnow()
        path = request.url.path
        method = request.method
        
        # User ID resolved by AuthStateMiddleware
        user_id = getattr(request.state, "user", None)
        if user_id:
            user_id = getattr(user_id, "id", None)
        
        response = await call_next(request)
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Determine event type for critical actions
        event_type = "api_request"
        if "/fund" in path and method == "POST":
            event_type = "escrow_funding"
        elif "/confirm" in path and method == "POST":
            event_type = "escrow_release_confirmed"
        elif "/withdraw" in path and method == "POST":
            event_type = "wallet_withdrawal"
        elif "/deposit" in path and method == "POST":
            event_type = "wallet_deposit"
        elif "/disputes" in path and method == "POST":
            event_type = "dispute_opened"
        elif "/disputes" in path and "/resolve" in path:
            event_type = "dispute_resolved"
        elif "/cancel" in path and method == "POST":
            event_type = "escrow_cancelled"
        elif "/admin" in path and method in {"POST", "PUT", "DELETE", "PATCH"}:
            event_type = "admin_action"
        
        audit_entry = {
            "timestamp": start_time.isoformat(),
            "event_type": event_type,
            "method": method,
            "path": path,
            "client_ip": request.client.host if request.client else None,
            "forwarded_for": request.headers.get("X-Forwarded-For"),
            "user_id": user_id,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "user_agent": request.headers.get("user-agent")
        }
        
        if event_type != "api_request" or response.status_code >= 400:
            logger.info(f"Audit Log: {json.dumps(audit_entry)}")
            await self._store_audit_log(audit_entry)
        
        return response
    
    async def _store_audit_log(self, entry: dict):
        """Store audit log in database."""
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
                import json
                await redis.lpush("audit_logs:pending", json.dumps(entry))
                await redis.ltrim("audit_logs:pending", 0, 9999)
        except Exception as e:
            logger.error(f"Failed to async store audit log: {e}")