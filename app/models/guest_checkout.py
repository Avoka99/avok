from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class GuestCheckoutSession(Base):
    __tablename__ = "guest_checkout_sessions"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=24))
    converted_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    converted_user = relationship("User")
    orders = relationship("Order", back_populates="guest_checkout_session")
    notifications = relationship("Notification", back_populates="guest_checkout_session")

    __table_args__ = (
        Index("ix_guest_checkout_phone_expires", "phone_number", "expires_at"),
    )

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at
