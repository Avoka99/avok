from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, Boolean, Index, JSON
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class OrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class DeliveryMethod(str, enum.Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"
    SHIPPING = "shipping"


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_reference = Column(String(50), unique=True, nullable=False, index=True)
    
    buyer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # External / guest seller payout details
    seller_display_name = Column(String(255), nullable=True)
    seller_contact = Column(String(255), nullable=True)
    payout_destination = Column(String(50), default="avok_account", nullable=False)
    payout_reference = Column(String(255), nullable=True)
    payout_account_name = Column(String(255), nullable=True)
    payout_bank_name = Column(String(255), nullable=True)
    payout_metadata = Column(JSON, nullable=True)
    
    # Product details
    product_name = Column(String(255), nullable=False)
    product_description = Column(Text)
    product_price = Column(Float, nullable=False)
    platform_fee = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    entry_fee = Column(Float, default=0.0, nullable=False)
    release_fee = Column(Float, default=0.0, nullable=False)
    payment_source = Column(String(50), default="verified_account", nullable=False)

    # Imported product/source details
    product_url = Column(Text, nullable=True)
    source_site_name = Column(String(255), nullable=True)
    imported_media = Column(JSON, nullable=True)
    import_snapshot = Column(JSON, nullable=True)
    
    # Escrow
    escrow_status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_PAYMENT, nullable=False)
    escrow_release_date = Column(DateTime, nullable=True)  # Auto-release after 14 days
    escrow_held_at = Column(DateTime, nullable=True)
    escrow_account_active = Column(Boolean, default=True, nullable=False)
    escrow_closed_at = Column(DateTime, nullable=True)
    
    # Delivery
    delivery_method = Column(Enum(DeliveryMethod), nullable=False)
    shipping_address = Column(Text, nullable=True)
    tracking_number = Column(String(255), nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    
    # OTP confirmation
    delivery_otp = Column(String(6), nullable=True)
    otp_verified_at = Column(DateTime, nullable=True)
    otp_attempts = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="orders_as_buyer")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="orders_as_seller")
    transactions = relationship("Transaction", back_populates="order")
    dispute = relationship("Dispute", back_populates="order", uselist=False)
    otp_delivery = relationship("OTPDelivery", back_populates="order", uselist=False)
    
    # Indexes
    __table_args__ = (
        Index("ix_orders_buyer_status", "buyer_id", "escrow_status"),
        Index("ix_orders_seller_status", "seller_id", "escrow_status"),
        Index("ix_orders_escrow_release", "escrow_release_date"),
    )
    
    def can_auto_release(self) -> bool:
        """Check if order is eligible for auto-release."""
        if not self.escrow_release_date:
            return False
        return datetime.utcnow() >= self.escrow_release_date
    
    def days_until_auto_release(self) -> Optional[int]:
        """Get days remaining until auto-release."""
        if not self.escrow_release_date:
            return None
        remaining = (self.escrow_release_date - datetime.utcnow()).days
        return max(0, remaining)
    
    def __repr__(self):
        return f"<Order {self.order_reference}: {self.product_name} - {self.escrow_status}>"

    @property
    def session_reference(self) -> str:
        return self.order_reference

    @property
    def payer_id(self) -> int:
        return self.buyer_id

    @property
    def recipient_id(self) -> Optional[int]:
        return self.seller_id

    @property
    def recipient_display_name(self) -> Optional[str]:
        return self.seller_display_name

    @property
    def recipient_contact(self) -> Optional[str]:
        return self.seller_contact

    @property
    def is_guest_checkout(self) -> bool:
        return bool((self.payout_metadata or {}).get("guest_checkout", False))
