from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

from app.models.user import UserRole, UserStatus, KYCStatus


class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: str = Field(..., min_length=10, max_length=15)
    full_name: str = Field(..., min_length=2, max_length=255)
    role: UserRole = UserRole.BUYER


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    wants_avok_account: bool = False
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


class UserLogin(BaseModel):
    phone_number: str
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    national_id_number: Optional[str] = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    avok_account_number: Optional[str] = None
    status: UserStatus
    kyc_status: KYCStatus
    is_phone_verified: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[UserRole] = None


class PhoneVerificationRequest(BaseModel):
    phone_number: str
    otp: str


class PhoneVerificationSend(BaseModel):
    phone_number: str


class KYCSubmission(BaseModel):
    document_type: str
    document_number: str
    document_image: str  # Base64 or S3 URL
    selfie_image: str  # Base64 or S3 URL
class AdminRoleRequest(BaseModel):
    phone_number: str
