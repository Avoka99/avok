from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import AuthService


class KYCService:
    """Thin KYC-oriented wrapper around the auth service."""

    def __init__(self, db: AsyncSession):
        self.auth_service = AuthService(db)

    async def submit(self, user_id: int, ghana_card_number: str, ghana_card_image_url: str, selfie_image_url: str):
        return await self.auth_service.submit_kyc(
            user_id=user_id,
            ghana_card_number=ghana_card_number,
            ghana_card_image_url=ghana_card_image_url,
            selfie_image_url=selfie_image_url,
        )

    async def approve(self, user_id: int, admin_id: int):
        return await self.auth_service.approve_kyc(user_id=user_id, admin_id=admin_id)

    async def reject(self, user_id: int, admin_id: int, reason: str):
        return await self.auth_service.reject_kyc(user_id=user_id, admin_id=admin_id, reason=reason)
