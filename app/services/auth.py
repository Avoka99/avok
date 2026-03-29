from app.services.kyc_provider import ExternalKYCProvider
from datetime import datetime, timedelta
from typing import Optional
import logging
import secrets
import random
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash, verify_password, generate_otp
from app.core.redis_client import cache_delete, cache_get, cache_set
from app.core.exceptions import ValidationError, UnauthorizedError, NotFoundError
from app.models.user import User, UserStatus, KYCStatus, UserRole
from app.models.wallet import Wallet, WalletType
from app.schemas.user import UserCreate
from app.services.guest_checkout import GuestCheckoutService
from app.services.notification import NotificationService
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and user management service."""

    OTP_TTL_SECONDS = 10 * 60
    
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
            status=UserStatus.PENDING,
            avok_account_number=self._generate_account_number() if getattr(user_data, 'wants_avok_account', False) else None
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
        guest_checkout_service = GuestCheckoutService(self.db)
        await guest_checkout_service.convert_sessions_to_user(user.phone_number, user.id)
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
        message = (
            f"Your Avok verification code is: {otp}. Valid for 10 minutes. "
            f"Phone verification unlocks checkout up to GHS {settings.fraud_high_value_threshold:,.0f} without full KYC."
        )
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
        document_type: str,
        document_number: str,
        document_image_url: str,
        selfie_image_url: str
    ) -> User:
        """Submit KYC documents with dynamic checks."""
        user = await self._get_user(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        
        # Check historical reuse excluding DEACTIVATED
        existing_matches = await self.db.execute(
            select(User).where(User.national_id_number == document_number)
        )
        for existing in existing_matches.scalars().all():
            if existing.id != user_id and existing.status != UserStatus.DEACTIVATED:
                raise ValidationError("Document already registered to an active or banned account")
        
        # Abstract verification
        external_result = await ExternalKYCProvider.verify_document_and_background(
            document_type, document_number, document_image_url, selfie_image_url
        )
        
        user.national_id_type = document_type
        user.national_id_number = document_number
        user.national_id_image_url = document_image_url
        user.selfie_image_url = selfie_image_url
        user.kyc_approvals = [] # Wipe old approvals
        
        if external_result["status"] == "flagged":
            user.is_flagged = True
            user.kyc_status = KYCStatus.PENDING # Keep pending so 2 admins can override
            logger.warning(f"User {user_id} flagged during external KYC: {external_result['reasons']}")
        else:
            user.is_flagged = False
            user.kyc_status = KYCStatus.PENDING
            
        await self.db.commit()
        await self._notify_admins_kyc_pending(user)
        return user
    
    async def approve_kyc(self, user_id: int, admin_id: int) -> User:
        """Approve KYC dynamically (1 for clean, 2 for flagged)."""
        user = await self._get_user(user_id)
        
        if user.kyc_status != KYCStatus.PENDING:
            raise ValidationError("KYC not pending approval")
            
        approvals = list(user.kyc_approvals or [])
        if admin_id not in approvals:
            approvals.append(admin_id)
            user.kyc_approvals = approvals
            
        required_approvals = 2 if user.is_flagged else 1
        
        if len(set(approvals)) >= required_approvals:
            user.kyc_status = KYCStatus.VERIFIED
            if user.status == UserStatus.PENDING and user.is_phone_verified:
                user.status = UserStatus.ACTIVE
            
            await self.notification_service.send_sms(
                user.phone_number,
                (
                    "KYC approved. You can now use your Avok balance directly and clear higher-value checkout reviews faster."
                ),
            )
            logger.info(f"KYC completely approved for user {user_id} by {len(set(approvals))} admins.")
        else:
            logger.info(f"KYC partially approved for user {user_id} by admin {admin_id}. Needs {required_approvals}")
            
        await self.db.commit()
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
        await cache_set(f"otp:{phone_number}", {"otp": otp}, ttl_seconds=self.OTP_TTL_SECONDS)
    
    async def _get_stored_otp(self, phone_number: str) -> Optional[str]:
        """Get stored OTP (placeholder)."""
        data = await cache_get(f"otp:{phone_number}")
        if not data:
            return None
        return data.get("otp")
    
    async def _clear_otp(self, phone_number: str):
        """Clear OTP (placeholder)."""
        await cache_delete(f"otp:{phone_number}")
    
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

    def _generate_account_number(self) -> str:
        return "".join([str(random.randint(0,9)) for _ in range(10)])
        
    async def allocate_avok_account(self, user_id: int) -> User:
        user = await self._get_user(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        if user.avok_account_number:
            raise ValidationError("User already has an Avok account number")
            
        while True:
            acct = self._generate_account_number()
            existing = await self.db.execute(select(User).where(User.avok_account_number == acct))
            if not existing.scalar_one_or_none():
                user.avok_account_number = acct
                break
                
        await self.db.commit()
        return user

    async def appoint_admin(self, phone_number: str) -> User:
        user = await self._get_user_by_phone(phone_number)
        if not user:
            raise NotFoundError("User", phone_number)
        if user.role == UserRole.SUPER_ADMIN:
            raise ValidationError("Cannot downgrade a Super Admin to standard Admin")
            
        user.role = UserRole.ADMIN
        await self.db.commit()
        return user

    async def dismiss_admin(self, phone_number: str) -> User:
        user = await self._get_user_by_phone(phone_number)
        if not user:
            raise NotFoundError("User", phone_number)
        if user.role == UserRole.SUPER_ADMIN:
            raise ValidationError("Cannot dismiss a Super Admin")
            
        user.role = UserRole.USER
        await self.db.commit()
        return user
