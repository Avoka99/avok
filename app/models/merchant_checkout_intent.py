from datetime import datetime

from sqlalchemy import func, Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class MerchantCheckoutIntent(Base):
    __tablename__ = "merchant_checkout_intents"

    id = Column(Integer, primary_key=True, index=True)
    intent_reference = Column(String(64), unique=True, index=True, nullable=False)
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    seller_id = Column(Integer, nullable=True)
    seller_display_name = Column(String(255), nullable=True)
    seller_contact = Column(String(255), nullable=True)
    payout_destination = Column(String(50), nullable=False, default="avok_account")
    payout_reference = Column(String(255), nullable=True)
    payout_account_name = Column(String(255), nullable=True)
    payout_bank_name = Column(String(255), nullable=True)
    product_name = Column(String(255), nullable=True)
    product_description = Column(Text, nullable=True)
    product_price = Column(Float, nullable=False)
    items = Column(JSON, nullable=True)
    delivery_method = Column(String(50), nullable=False, default="pickup")
    shipping_address = Column(Text, nullable=True)
    product_url = Column(Text, nullable=True)
    payment_source = Column(String(50), nullable=False, default="verified_account")
    merchant_name = Column(String(255), nullable=False)
    return_url = Column(Text, nullable=True)
    cancel_url = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_consumed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    merchant = relationship("Merchant")

    def __repr__(self):
        return f"<MerchantCheckoutIntent {self.intent_reference} merchant={self.merchant_id}>"
