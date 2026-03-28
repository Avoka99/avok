from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.api.dependencies import get_db, get_current_user, get_current_super_admin
from app.schemas.user import (
    UserCreate, UserLogin, UserResponse, Token, 
    PhoneVerificationSend, PhoneVerificationRequest, KYCSubmission, AdminRoleRequest
)
from app.services.auth import AuthService
from app.core.security import create_access_token, create_refresh_token
from app.core.exceptions import ValidationError, UnauthorizedError

router = APIRouter(prefix="/auth", tags=["authentication"])


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
    """Dismiss an Admin. Only Super Admins can do this."""
    auth_service = AuthService(db)
    user = await auth_service.dismiss_admin(payload.phone_number)
    return user
