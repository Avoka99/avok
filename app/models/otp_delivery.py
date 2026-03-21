from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class OTPDelivery(Base):
    __tablename__ = "otp_deliveries"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    otp_code = Column(String(6), nullable=False)
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Security
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    expires_at = Column(DateTime, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order = relationship("Order", back_populates="otp_delivery")
    verified_by = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("ix_otp_deliveries_order", "order_id"),
        Index("ix_otp_deliveries_code", "otp_code"),
    )
    
    def is_expired(self) -> bool:
        """Check if OTP has expired."""
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f"<OTPDelivery {self.id}: Order {self.order_id} - Verified: {self.is_verified}>"