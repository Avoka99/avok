from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

from app.models.user import UserRole, UserStatus, KYCStatus


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="Email is required for account verification")
    phone_number: str = Field(..., min_length=10, max_length=15)
    full_name: str = Field(..., min_length=2, max_length=255)
    role: UserRole = UserRole.USER


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    wants_avok_account: bool = True
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v
    
    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Full name is required")
        return v.strip()
    
    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Valid phone number is required")
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


class UserMeResponse(UserResponse):
    """Full user response for authenticated user."""
    last_login_at: Optional[datetime] = None
    fraud_score: Optional[int] = None
    is_flagged: bool = False


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
    document_type: str = Field(..., description="ID type: ghana_card, voter_id, driver_license, national_id")
    document_number: str = Field(..., min_length=5, description="ID document number")
    document_image: str = Field(..., description="Base64 or S3 URL of ID document")
    selfie_image: str = Field(..., description="Base64 or S3 URL of selfie")

class AdminRoleRequest(BaseModel):
    phone_number: str
