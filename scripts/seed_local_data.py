import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import KYCStatus, User, UserRole, UserStatus
from app.models.wallet import Wallet, WalletType


USERS = [
    {
        "phone_number": "0241111111",
        "full_name": "Local Buyer",
        "email": "buyer@avok.local",
        "role": UserRole.BUYER,
    },
    {
        "phone_number": "0242222222",
        "full_name": "Local Seller",
        "email": "seller@avok.local",
        "role": UserRole.SELLER,
    },
    {
        "phone_number": "0243333333",
        "full_name": "Local Admin",
        "email": "admin@avok.local",
        "role": UserRole.ADMIN,
    },
]

DEFAULT_PASSWORD = "Password1"


async def main() -> None:
    async with SessionLocal() as session:
        created = 0
        for payload in USERS:
            existing = await session.execute(
                select(User).where(User.phone_number == payload["phone_number"])
            )
            user = existing.scalar_one_or_none()
            if user is None:
                user = User(
                    phone_number=payload["phone_number"],
                    full_name=payload["full_name"],
                    email=payload["email"],
                    role=payload["role"],
                    status=UserStatus.ACTIVE,
                    kyc_status=KYCStatus.VERIFIED,
                    is_phone_verified=True,
                    hashed_password=get_password_hash(DEFAULT_PASSWORD),
                )
                session.add(user)
                await session.flush()
                session.add(
                    Wallet(
                        user_id=user.id,
                        wallet_type=WalletType.MAIN,
                        available_balance=1000.0 if user.role == UserRole.BUYER else 0.0,
                        pending_balance=0.0,
                        escrow_balance=0.0,
                    )
                )
                created += 1
            else:
                user.status = UserStatus.ACTIVE
                user.kyc_status = KYCStatus.VERIFIED
                user.is_phone_verified = True

        await session.commit()
        print("Seed complete.")
        print(f"Created users: {created}")
        print(f"Default password for seeded accounts: {DEFAULT_PASSWORD}")
        for payload in USERS:
            print(f"{payload['role'].value}: {payload['phone_number']} / {payload['email']}")


if __name__ == "__main__":
    asyncio.run(main())
