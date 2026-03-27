from app.models.user import KYCStatus, User, UserStatus


def calculate_capped_fee(amount: float, percent: float = 1.0, cap_amount: float = 30.0) -> float:
    """Calculate a percentage fee with an upper cap."""
    numeric_amount = max(float(amount or 0), 0.0)
    fee = numeric_amount * (percent / 100)
    return min(fee, cap_amount)


def is_verified_account(user: User) -> bool:
    """A verified Avok account requires active status, verified phone, and approved KYC."""
    return bool(
        user
        and user.status == UserStatus.ACTIVE
        and user.is_phone_verified
        and user.kyc_status == KYCStatus.VERIFIED
    )
