from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.security import decode_token, is_token_revoked
from app.models.guest_checkout import GuestCheckoutSession
from app.models.user import User, UserRole, UserStatus
from app.services.auth import AuthService
from app.services.guest_checkout import GuestCheckoutService

security = HTTPBearer()


@dataclass
class GuestCheckoutActor:
    id: None
    role: str
    guest_session_id: int
    phone_number: str
    full_name: str
    email: str | None
    is_guest: bool = True


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user."""
    token = credentials.credentials
    if await is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    auth_service = AuthService(db)
    user = await auth_service._get_user(int(user_id))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended",
        )
    
    if user.status == UserStatus.BANNED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account banned",
        )
    
    return user


async def get_current_checkout_actor(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Get either a permanent user or a temporary guest checkout actor."""
    token = credentials.credentials
    if await is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("subject_type") == "guest_checkout":
        guest_session_id = payload.get("guest_session_id")
        if not guest_session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid guest token payload",
            )

        guest_service = GuestCheckoutService(db)
        guest_session = await guest_service.get_active_session(int(guest_session_id))
        return GuestCheckoutActor(
            id=None,
            role="user",
            guest_session_id=guest_session.id,
            phone_number=guest_session.phone_number,
            full_name=guest_session.full_name,
            email=guest_session.email,
        )

    return await get_current_user(credentials=credentials, db=db)


async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current admin user."""
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_payment_sandbox_enabled() -> None:
    """Reject sandbox simulate-payment endpoints unless explicitly enabled (e.g. local / staging)."""
    if not settings.enable_payment_sandbox:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sandbox payment simulation is disabled",
        )

async def get_current_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current super admin user."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin privileges strictly required",
        )
    return current_user
