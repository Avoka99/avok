from datetime import datetime, timezone, timedelta

from sqlalchemy import func, Column, DateTime, ForeignKey, Integer, String, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class GuestCheckoutSession(Base):
    __tablename__ = "guest_checkout_sessions"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc) + timedelta(hours=24))
    converted_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    converted_user = relationship("User")
    orders = relationship("Order", back_populates="guest_checkout_session")
    notifications = relationship("Notification", back_populates="guest_checkout_session")

    __table_args__ = (
        Index("ix_guest_checkout_phone_expires", "phone_number", "expires_at"),
    )

    @property
    def is_expired(self) -> bool:
        if self.expires_at.tzinfo is None:
            return datetime.utcnow() >= self.expires_at
        return datetime.now(timezone.utc) >= self.expires_at
