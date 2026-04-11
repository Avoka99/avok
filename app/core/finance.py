from typing import Optional, TypedDict

from app.core.config import settings
from app.models.user import KYCStatus, User, UserStatus


class PaymentSecurityRequirements(TypedDict):
    tier: str
    requires_phone_verification: bool
    requires_kyc: bool
    can_proceed: bool
    user_message: str


def calculate_capped_fee(amount: float, percent: float = 1.0, cap_amount: float = 30.0) -> float:
    """Calculate a percentage fee with a tiered upper cap."""
    numeric_amount = max(float(amount or 0), 0.0)
    fee = numeric_amount * (percent / 100)
    effective_cap = float(cap_amount or 0.0)
    if numeric_amount >= 1_000_000:
        effective_cap = max(effective_cap, 500.0)
    elif numeric_amount >= 100_000:
        effective_cap = max(effective_cap, 100.0)
    elif numeric_amount >= 10_000:
        effective_cap = max(effective_cap, 50.0)
    return min(fee, effective_cap)


def is_verified_account(user: User) -> bool:
    """A verified Avok account requires active status, verified phone, and approved KYC."""
    return bool(
        user
        and user.status == UserStatus.ACTIVE
        and user.is_phone_verified
        and user.kyc_status == KYCStatus.VERIFIED
    )


def is_phone_verified_account(user: Optional[User]) -> bool:
    """A phone-verified account can access medium-risk checkout flows without full KYC."""
    return bool(
        user
        and user.status == UserStatus.ACTIVE
        and user.is_phone_verified
    )


def get_payment_security_requirements(
    amount: float,
    funding_source: str,
    *,
    user: Optional[User] = None,
    is_guest: bool = False,
) -> PaymentSecurityRequirements:
    """Return the minimum verification level required for a checkout funding attempt."""
    numeric_amount = max(float(amount or 0), 0.0)
    medium_risk_limit = settings.fraud_high_value_threshold
    high_risk_limit = settings.fraud_high_value_threshold * 3

    if funding_source == "verified_account":
        can_proceed = is_verified_account(user)
        return {
            "tier": "wallet",
            "requires_phone_verification": True,
            "requires_kyc": True,
            "can_proceed": can_proceed,
            "user_message": (
                "Complete phone verification and KYC before paying from your Avok balance."
                if not can_proceed
                else "Verified balance payment approved."
            ),
        }

    if numeric_amount <= medium_risk_limit:
        return {
            "tier": "low",
            "requires_phone_verification": False,
            "requires_kyc": False,
            "can_proceed": True,
            "user_message": "Low-risk checkout approved with standard payment checks.",
        }

    if numeric_amount <= high_risk_limit:
        if is_guest:
            return {
                "tier": "medium_guest",
                "requires_phone_verification": False,
                "requires_kyc": False,
                "can_proceed": True,
                "user_message": (
                    "Medium-risk guest checkout approved. Keep your phone reachable and provide email so Avok can send security updates."
                ),
            }

        can_proceed = is_phone_verified_account(user)
        return {
            "tier": "medium_registered",
            "requires_phone_verification": True,
            "requires_kyc": False,
            "can_proceed": can_proceed,
            "user_message": (
                "Verify your phone number before paying amounts above GHS 1,000."
                if not can_proceed
                else "Phone verification requirement satisfied."
            ),
        }

    if is_guest:
        return {
            "tier": "high_guest",
            "requires_phone_verification": False,
            "requires_kyc": False,
            "can_proceed": True,
            "user_message": (
                "Higher-value guest checkout approved. Avok may keep a closer watch on payment confirmations and ask you to register later for faster future approvals."
            ),
        }

    can_proceed = is_verified_account(user)
    return {
        "tier": "high_registered",
        "requires_phone_verification": True,
        "requires_kyc": True,
        "can_proceed": can_proceed,
        "user_message": (
            "Complete phone verification and KYC before paying amounts above GHS 3,000."
            if not can_proceed
            else "High-risk verification requirement satisfied."
        ),
    }
