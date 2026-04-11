from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.guest_checkout import GuestCheckoutSession


class GuestCheckoutService:
    ACCESS_TOKEN_TTL = timedelta(hours=6)
    REFRESH_TOKEN_TTL = timedelta(hours=24)

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, phone_number: str, full_name: str, email: Optional[str] = None) -> GuestCheckoutSession:
        guest_session = GuestCheckoutSession(
            phone_number=phone_number,
            full_name=full_name,
            email=email,
            expires_at=datetime.now(timezone.utc) + self.REFRESH_TOKEN_TTL,
        )
        self.db.add(guest_session)
        await self.db.flush()
        return guest_session

    async def get_session(self, session_id: int) -> GuestCheckoutSession:
        result = await self.db.execute(
            select(GuestCheckoutSession).where(GuestCheckoutSession.id == session_id)
        )
        guest_session = result.scalar_one_or_none()
        if not guest_session:
            raise NotFoundError("Guest checkout session", session_id)
        return guest_session

    async def get_active_session(self, session_id: int) -> GuestCheckoutSession:
        guest_session = await self.get_session(session_id)
        if guest_session.is_expired:
            raise ValidationError("Guest checkout session has expired. Please create a new session or register to continue.")
        return guest_session

    async def convert_sessions_to_user(self, phone_number: str, user_id: int) -> None:
        result = await self.db.execute(
            select(GuestCheckoutSession)
            .options(selectinload(GuestCheckoutSession.orders))
            .where(
                GuestCheckoutSession.phone_number == phone_number,
                GuestCheckoutSession.converted_user_id.is_(None),
            )
        )
        for guest_session in result.scalars().all():
            guest_session.converted_user_id = user_id
            for order in guest_session.orders:
                if order.buyer_id is None:
                    order.buyer_id = user_id
