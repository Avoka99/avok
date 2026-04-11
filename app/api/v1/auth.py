from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.api.dependencies import get_db, get_current_user, get_current_super_admin, get_current_admin
from app.schemas.user import (
    UserCreate, UserLogin, UserResponse, Token, 
    PhoneVerificationSend, PhoneVerificationRequest, KYCSubmission, AdminRoleRequest,
    UserMeResponse, RefreshTokenRequest
)
from app.services.auth import AuthService
from app.services.guest_checkout import GuestCheckoutService
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_guest_access_token,
    create_guest_refresh_token,
    decode_token,
    is_token_revoked,
    revoke_token,
)
from app.core.exceptions import ValidationError, UnauthorizedError

router = APIRouter(prefix="/auth", tags=["authentication"])
auth_security = HTTPBearer(auto_error=False)


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user."""
    auth_service = AuthService(db)
    try:
        user = await auth_service.register(user_data)
        return user
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login with phone number and password."""
    auth_service = AuthService(db)
    user = await auth_service.authenticate(login_data.phone_number, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password"
        )
    
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return {"access_token": access_token, "refresh_token": refresh_token}


@router.post("/refresh", response_model=Token)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Rotate a refresh token and issue a new access token pair."""
    if await is_token_revoked(payload.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    token_payload = decode_token(payload.refresh_token)
    if not token_payload or token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if token_payload.get("subject_type") == "guest_checkout":
        guest_session_id = token_payload.get("guest_session_id")
        order_reference = token_payload.get("order_reference")
        if not guest_session_id or not order_reference:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid guest refresh token payload",
            )

        guest_service = GuestCheckoutService(db)
        await guest_service.get_active_session(int(guest_session_id))
        access_token = create_guest_access_token(int(guest_session_id), order_reference)
        new_refresh_token = create_guest_refresh_token(int(guest_session_id), order_reference)
    else:
        user_id = token_payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token payload",
            )

        auth_service = AuthService(db)
        user = await auth_service._get_user(int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
        new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    await revoke_token(payload.refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    payload: RefreshTokenRequest | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_security),
):
    """Revoke the caller's current access token and optional refresh token."""
    revoked_any = False

    if credentials and credentials.credentials:
        await revoke_token(credentials.credentials)
        revoked_any = True

    if payload and payload.refresh_token:
        await revoke_token(payload.refresh_token)
        revoked_any = True

    if not revoked_any:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No token provided for logout",
        )

    return {"message": "Logged out successfully"}


@router.post("/password-reset/request")
async def request_password_reset(
    phone_number: str,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset OTP."""
    auth_service = AuthService(db)
    try:
        await auth_service.request_password_reset(phone_number)
        return {"message": "Password reset code sent to your phone"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    phone_number: str,
    otp: str,
    new_password: str,
    db: AsyncSession = Depends(get_db)
):
    """Confirm password reset with OTP."""
    auth_service = AuthService(db)
    try:
        await auth_service.confirm_password_reset(phone_number, otp, new_password)
        return {"message": "Password reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me", response_model=UserMeResponse)
async def get_current_user_info(
    current_user = Depends(get_current_user)
):
    """Get current authenticated user's profile."""
    return current_user


@router.post("/verify/phone/send")
async def send_verification(
    request: PhoneVerificationSend,
    db: AsyncSession = Depends(get_db)
):
    """Send OTP for phone verification."""
    auth_service = AuthService(db)
    await auth_service.send_phone_verification(request.phone_number)
    return {"message": "Verification code sent"}


@router.post("/verify/phone")
async def verify_phone(
    request: PhoneVerificationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify phone number with OTP."""
    auth_service = AuthService(db)
    await auth_service.verify_phone(request.phone_number, request.otp)
    return {"message": "Phone number verified successfully"}


@router.post("/kyc", response_model=UserResponse)
async def submit_kyc(
    payload: KYCSubmission,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit KYC details for verified account activation."""
    auth_service = AuthService(db)
    user = await auth_service.submit_kyc(
        user_id=current_user.id,
        document_type=payload.document_type,
        document_number=payload.document_number,
        document_image_url=payload.document_image,
        selfie_image_url=payload.selfie_image,
    )
    return user

@router.post("/allocate-account", response_model=UserResponse)
async def allocate_account(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Allocate an Avok account number to user."""
    auth_service = AuthService(db)
    try:
        user = await auth_service.allocate_avok_account(current_user.id)
        return user
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.post("/roles/appoint-admin", response_model=UserResponse)
async def appoint_admin(
    payload: AdminRoleRequest,
    current_super_admin=Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Appoint a new Admin. Only Super Admins can do this."""
    auth_service = AuthService(db)
    user = await auth_service.appoint_admin(payload.phone_number)
    return user

@router.post("/roles/dismiss-admin", response_model=UserResponse)
async def dismiss_admin(
    payload: AdminRoleRequest,
    current_super_admin=Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Dismiss an admin. Only Super Admins can do this."""
    auth_service = AuthService(db)
    user = await auth_service.dismiss_admin(payload.phone_number)
    return user


@router.post("/kyc/approve/{user_id}")
async def approve_kyc(
    user_id: int,
    current_admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin approves a user's KYC submission."""
    auth_service = AuthService(db)
    try:
        user = await auth_service.approve_kyc(user_id, current_admin.id)
        return {"message": "KYC approved", "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/kyc/reject/{user_id}")
async def reject_kyc(
    user_id: int,
    payload: dict,
    current_admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin rejects a user's KYC submission with reason."""
    reason = payload.get("reason", "No reason provided")
    auth_service = AuthService(db)
    try:
        user = await auth_service.reject_kyc(user_id, current_admin.id, reason)
        return {"message": "KYC rejected", "user_id": user_id, "reason": reason}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
