from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware for audit logging."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.utcnow()
        
        # Get user info if authenticated
        user_id = None
        if hasattr(request.state, "user"):
            user_id = request.state.user.id
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Log audit entry
        audit_entry = {
            "timestamp": start_time.isoformat(),
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_ip": request.client.host if request.client else None,
            "user_id": user_id,
            "status_code": response.status_code,
            "duration_ms": duration * 1000,
            "user_agent": request.headers.get("user-agent")
        }
        
        # Log to file/database
        logger.info(json.dumps(audit_entry))
        
        # Store in database for critical actions
        if request.method in ["POST", "PUT", "DELETE"] and response.status_code < 400:
            await self._store_audit_log(audit_entry)
        
        return response
    
    async def _store_audit_log(self, entry: dict):
        """Store audit log in database."""
        # In production, store in a separate audit table
        pass