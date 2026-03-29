from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import ValidationError
import secrets
import hashlib
import hmac
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    
    return encoded_jwt


def create_guest_access_token(guest_session_id: int, order_reference: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived access token for a guest checkout session."""
    return create_access_token(
        {
            "sub": f"guest:{guest_session_id}",
            "role": "user",
            "subject_type": "guest_checkout",
            "guest_session_id": guest_session_id,
            "order_reference": order_reference,
        },
        expires_delta=expires_delta,
    )


def create_guest_refresh_token(guest_session_id: int, order_reference: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a refresh token for a guest checkout session."""
    to_encode = {
        "sub": f"guest:{guest_session_id}",
        "role": "user",
        "subject_type": "guest_checkout",
        "guest_session_id": guest_session_id,
        "order_reference": order_reference,
    }
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        logger.warning(f"Token decode error: {e}")
        return None


def generate_otp() -> str:
    """Generate a 6-digit OTP."""
    return ''.join(secrets.choice('0123456789') for _ in range(6))


def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(length)


def hash_phone_number(phone_number: str) -> str:
    """Hash phone number for privacy."""
    salt = settings.secret_key.encode()
    return hmac.new(salt, phone_number.encode(), hashlib.sha256).hexdigest()


def validate_ghana_phone(phone: str) -> bool:
    """
    Validate Ghanaian phone number.
    Format: 024XXXXXXX, 054XXXXXXX, 055XXXXXXX, 059XXXXXXX, etc.
    """
    import re
    pattern = r'^(0[2459]\d{8})$'
    return bool(re.match(pattern, phone))


def validate_ghana_card(card_number: str) -> bool:
    """
    Validate Ghana Card number format.
    Format: GHA-XXXXXXXXX-X or GHAXXXXXXXXXX
    """
    import re
    # Remove hyphens and spaces
    card_number = re.sub(r'[\s-]', '', card_number.upper())
    pattern = r'^GHA\d{9,10}$'
    return bool(re.match(pattern, card_number))
