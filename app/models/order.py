from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, Boolean, Index
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
    seller_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Product details
    product_name = Column(String(255), nullable=False)
    product_description = Column(Text)
    product_price = Column(Float, nullable=False)
    platform_fee = Column(Float, nullable=False)  # 1% of product price
    total_amount = Column(Float, nullable=False)  # product_price + platform_fee
    
    # Escrow
    escrow_status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_PAYMENT, nullable=False)
    escrow_release_date = Column(DateTime, nullable=True)  # Auto-release after 14 days
    escrow_held_at = Column(DateTime, nullable=True)
    
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