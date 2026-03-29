from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.order import DeliveryMethod
from app.schemas.order import OrderItemCreate


class MerchantCreate(BaseModel):
    id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=2, max_length=255)
    secret_key: str = Field(..., min_length=16, max_length=255)
    allowed_return_urls: List[str] = Field(default_factory=list)
    allowed_cancel_urls: List[str] = Field(default_factory=list)


class MerchantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    is_active: bool
    created_at: datetime


class MerchantIntentCreate(BaseModel):
    seller_id: Optional[int] = None
    seller_display_name: Optional[str] = Field(default=None, max_length=255)
    seller_contact: Optional[str] = Field(default=None, max_length=255)
    payout_destination: str = Field(default="avok_account", pattern="^(avok_account|momo|bank)$")
    payout_reference: Optional[str] = None
    payout_account_name: Optional[str] = None
    payout_bank_name: Optional[str] = None
    product_name: Optional[str] = Field(default=None, max_length=255)
    product_description: Optional[str] = None
    product_price: Optional[float] = Field(default=None, gt=0)
    items: List[OrderItemCreate] = Field(default_factory=list)
    delivery_method: DeliveryMethod = DeliveryMethod.PICKUP
    shipping_address: Optional[str] = None
    product_url: Optional[str] = None
    payment_source: str = Field(default="verified_account", pattern="^(verified_account|momo|bank)$")
    merchant_name: Optional[str] = Field(default=None, max_length=255)
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    expires_in_minutes: int = Field(default=30, ge=5, le=1440)

    @field_validator("product_price")
    @classmethod
    def validate_price(cls, value):
        if value is None:
            return value
        if value < 1.0:
            raise ValueError("Product price must be at least 1.00 GHS")
        return value


class MerchantIntentResponse(BaseModel):
    intent_reference: str
    checkout_url: str
    expires_at: datetime


class MerchantIntentPayload(BaseModel):
    intent_reference: str
    merchant_id: str
    merchant_name: str
    seller_id: Optional[int] = None
    seller_display_name: Optional[str] = None
    seller_contact: Optional[str] = None
    payout_destination: str
    payout_reference: Optional[str] = None
    payout_account_name: Optional[str] = None
    payout_bank_name: Optional[str] = None
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    product_price: float
    items: List[OrderItemCreate] = Field(default_factory=list)
    delivery_method: DeliveryMethod
    shipping_address: Optional[str] = None
    product_url: Optional[str] = None
    payment_source: str
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None
    expires_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
