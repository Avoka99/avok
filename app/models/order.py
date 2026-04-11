from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, Boolean, Index, JSON, func
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
    PENDING_REVIEW = "pending_review"
    REFUNDED = "refunded"


class DeliveryMethod(str, enum.Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"
    SHIPPING = "shipping"


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_reference = Column(String(50), unique=True, nullable=False, index=True)
    
    buyer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    guest_checkout_session_id = Column(Integer, ForeignKey("guest_checkout_sessions.id", ondelete="SET NULL"), nullable=True)
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
    escrow_release_date = Column(DateTime(timezone=True), nullable=True)  # Auto-release after 14 days
    escrow_held_at = Column(DateTime(timezone=True), nullable=True)
    escrow_account_active = Column(Boolean, default=True, nullable=False)
    escrow_closed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Delivery
    delivery_method = Column(Enum(DeliveryMethod), nullable=False)
    shipping_address = Column(Text, nullable=True)
    tracking_number = Column(String(255), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    # OTP confirmation
    delivery_otp = Column(String(6), nullable=True)
    otp_verified_at = Column(DateTime(timezone=True), nullable=True)
    otp_attempts = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="orders_as_buyer")
    guest_checkout_session = relationship("GuestCheckoutSession", back_populates="orders")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="orders_as_seller")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="order")
    dispute = relationship("Dispute", back_populates="order", uselist=False)
    otp_delivery = relationship("OTPDelivery", back_populates="order", uselist=False)
    
    # Indexes
    __table_args__ = (
        Index("ix_orders_buyer_status", "buyer_id", "escrow_status"),
        Index("ix_orders_seller_status", "seller_id", "escrow_status"),
        Index("ix_orders_escrow_release", "escrow_release_date"),
    )

    @staticmethod
    def _ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    
    def can_auto_release(self) -> bool:
        """Check if order is eligible for auto-release."""
        release_date = self._ensure_utc(self.escrow_release_date)
        if not self.escrow_account_active or not release_date:
            return False
        if self.escrow_status not in {OrderStatus.SHIPPED, OrderStatus.DELIVERED}:
            return False
        return datetime.now(timezone.utc) >= release_date

    def start_auto_release_window(self, release_days: int) -> datetime:
        """Start or refresh the escrow auto-release countdown from the delivery phase."""
        self.escrow_release_date = datetime.now(timezone.utc) + timedelta(days=release_days)
        return self.escrow_release_date
    
    def days_until_auto_release(self) -> Optional[int]:
        """Get days remaining until auto-release."""
        release_date = self._ensure_utc(self.escrow_release_date)
        if not release_date:
            return None
        remaining = (release_date - datetime.now(timezone.utc)).days
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
    def guest_payer_name(self) -> Optional[str]:
        return self.guest_checkout_session.full_name if self.guest_checkout_session else None

    @property
    def guest_payer_phone_number(self) -> Optional[str]:
        return self.guest_checkout_session.phone_number if self.guest_checkout_session else None

    @property
    def guest_payer_email(self) -> Optional[str]:
        return self.guest_checkout_session.email if self.guest_checkout_session else None

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

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items) if self.items else 0
