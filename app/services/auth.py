from datetime import datetime, timedelta
from typing import Optional
import logging
import secrets
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash, verify_password, generate_otp
from app.core.exceptions import ValidationError, UnauthorizedError, NotFoundError
from app.models.user import User, UserStatus, KYCStatus, UserRole
from app.models.wallet import Wallet, WalletType
from app.schemas.user import UserCreate
from app.services.notification import NotificationService
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and user management service."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_service = NotificationService(db)
    
    async def register(self, user_data: UserCreate) -> User:
        """Register a new user."""
        # Validate phone number
        if not self._validate_ghana_phone(user_data.phone_number):
            raise ValidationError("Invalid Ghanaian phone number format")
        
        # Check if user exists
        existing_user = await self._get_user_by_phone(user_data.phone_number)
        if existing_user:
            raise ValidationError("User with this phone number already exists")
        
        if user_data.email:
            existing_email = await self._get_user_by_email(user_data.email)
            if existing_email:
                raise ValidationError("User with this email already exists")
        
        # Create user
        user = User(
            email=user_data.email,
            phone_number=user_data.phone_number,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
            status=UserStatus.PENDING
        )
        
        self.db.add(user)
        await self.db.flush()
        
        # Create wallet for user
        main_wallet = Wallet(
            user_id=user.id,
            wallet_type=WalletType.MAIN,
            available_balance=0.0,
            pending_balance=0.0,
            escrow_balance=0.0
        )
        
        self.db.add(main_wallet)
        await self.db.commit()
        
        # Send verification SMS
        await self.send_phone_verification(user_data.phone_number)
        
        logger.info(f"New user registered: {user.phone_number}")
        return user
    
    async def authenticate(self, phone_number: str, password: str) -> Optional[User]:
        """Authenticate user with phone and password."""
        user = await self._get_user_by_phone(phone_number)
        
        if not user:
            return None
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise UnauthorizedError(f"Account locked until {user.locked_until}")
        
        # Verify password
        if not verify_password(password, user.hashed_password):
            user.login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
            
            await self.db.commit()
            return None
        
        # Reset login attempts on success
        user.login_attempts = 0
        user.last_login_at = datetime.utcnow()
        user.locked_until = None
        
        await self.db.commit()
        
        logger.info(f"User authenticated: {user.phone_number}")
        return user
    
    async def send_phone_verification(self, phone_number: str) -> str:
        """Send OTP for phone verification."""
        user = await self._get_user_by_phone(phone_number)
        if not user:
            raise NotFoundError("User", phone_number)
        
        if user.is_phone_verified:
            raise ValidationError("Phone number already verified")
        
        # Generate OTP
        otp = generate_otp()
        
        # Store OTP (in production, use Redis with TTL)
        # For now, we'll simulate with a simple in-memory store
        # In production, implement Redis storage
        await self._store_otp(phone_number, otp)
        
        # Send SMS
        message = f"Your Avok verification code is: {otp}. Valid for 10 minutes."
        await self.notification_service.send_sms(phone_number, message)
        
        logger.info(f"Verification code sent to {phone_number}")
        return otp
    
    async def verify_phone(self, phone_number: str, otp: str) -> bool:
        """Verify phone number with OTP."""
        user = await self._get_user_by_phone(phone_number)
        if not user:
            raise NotFoundError("User", phone_number)
        
        if user.is_phone_verified:
            raise ValidationError("Phone number already verified")
        
        # Verify OTP
        stored_otp = await self._get_stored_otp(phone_number)
        if not stored_otp or stored_otp != otp:
            raise ValidationError("Invalid or expired OTP")
        
        # Update user
        user.is_phone_verified = True
        user.phone_verified_at = datetime.utcnow()
        user.status = UserStatus.ACTIVE
        
        await self.db.commit()
        
        # Clear OTP
        await self._clear_otp(phone_number)
        
        logger.info(f"Phone verified for user {user.id}")
        return True
    
    async def submit_kyc(
        self,
        user_id: int,
        ghana_card_number: str,
        ghana_card_image_url: str,
        selfie_image_url: str
    ) -> User:
        """Submit KYC documents."""
        user = await self._get_user(user_id)
        
        if not user:
            raise NotFoundError("User", user_id)
        
        # Validate Ghana Card number
        if not self._validate_ghana_card(ghana_card_number):
            raise ValidationError("Invalid Ghana Card number format")
        
        # Check if card already used
        existing = await self._get_user_by_ghana_card(ghana_card_number)
        if existing and existing.id != user_id:
            raise ValidationError("Ghana Card number already registered")
        
        user.ghana_card_number = ghana_card_number
        user.ghana_card_image_url = ghana_card_image_url
        user.selfie_image_url = selfie_image_url
        user.kyc_status = KYCStatus.PENDING
        
        await self.db.commit()
        
        # Notify admins for review
        await self._notify_admins_kyc_pending(user)
        
        logger.info(f"KYC submitted for user {user_id}")
        return user
    
    async def approve_kyc(self, user_id: int, admin_id: int) -> User:
        """Approve KYC verification."""
        user = await self._get_user(user_id)
        
        if user.kyc_status != KYCStatus.PENDING:
            raise ValidationError("KYC not pending approval")
        
        user.kyc_status = KYCStatus.VERIFIED
        
        # Update user status if still pending
        if user.status == UserStatus.PENDING and user.is_phone_verified:
            user.status = UserStatus.ACTIVE
        
        await self.db.commit()
        
        # Send notification
        await self.notification_service.send_kyc_approved(user.phone_number)
        
        logger.info(f"KYC approved for user {user_id} by admin {admin_id}")
        return user
    
    async def reject_kyc(self, user_id: int, admin_id: int, reason: str) -> User:
        """Reject KYC verification."""
        user = await self._get_user(user_id)
        
        if user.kyc_status != KYCStatus.PENDING:
            raise ValidationError("KYC not pending approval")
        
        user.kyc_status = KYCStatus.REJECTED
        
        await self.db.commit()
        
        # Send notification with reason
        await self.notification_service.send_kyc_rejected(user.phone_number, reason)
        
        logger.info(f"KYC rejected for user {user_id} by admin {admin_id}")
        return user
    
    async def _get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_phone(self, phone_number: str) -> Optional[User]:
        """Get user by phone number."""
        result = await self.db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_ghana_card(self, card_number: str) -> Optional[User]:
        """Get user by Ghana Card number."""
        result = await self.db.execute(
            select(User).where(User.ghana_card_number == card_number)
        )
        return result.scalar_one_or_none()
    
    async def _store_otp(self, phone_number: str, otp: str):
        """Store OTP (placeholder - use Redis in production)."""
        # In production, implement Redis with TTL of 10 minutes
        pass
    
    async def _get_stored_otp(self, phone_number: str) -> Optional[str]:
        """Get stored OTP (placeholder)."""
        # In production, retrieve from Redis
        return None
    
    async def _clear_otp(self, phone_number: str):
        """Clear OTP (placeholder)."""
        # In production, delete from Redis
        pass
    
    async def _notify_admins_kyc_pending(self, user: User):
        """Notify admins about pending KYC."""
        # In production, send to admin notification queue
        pass
    
    @staticmethod
    def _validate_ghana_phone(phone: str) -> bool:
        """Validate Ghanaian phone number."""
        pattern = r'^(0[2459]\d{8})$'
        return bool(re.match(pattern, phone))
    
    @staticmethod
    def _validate_ghana_card(card_number: str) -> bool:
        """Validate Ghana Card number."""
        card_number = re.sub(r'[\s-]', '', card_number.upper())
        pattern = r'^GHA\d{9,10}$'
        return bool(re.match(pattern, card_number))