from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum

from app.models.order import OrderStatus, DeliveryMethod


class OrderItemCreate(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=255)
    item_description: Optional[str] = None
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(..., gt=0)
    product_url: Optional[str] = None

    @field_validator("unit_price")
    @classmethod
    def validate_unit_price(cls, v):
        if v < 1.0:
            raise ValueError("Item unit price must be at least 1.00 GHS")
        return v


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_name: str
    item_description: Optional[str]
    quantity: int
    unit_price: float
    line_total: float
    product_url: Optional[str]


class OrderCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recipient_id: Optional[int] = Field(default=None, validation_alias=AliasChoices("recipient_id", "seller_id"))
    recipient_display_name: Optional[str] = Field(default=None, max_length=255, validation_alias=AliasChoices("recipient_display_name", "seller_display_name"))
    recipient_contact: Optional[str] = Field(default=None, max_length=255, validation_alias=AliasChoices("recipient_contact", "seller_contact"))
    payout_destination: str = Field(default="avok_account", pattern="^(avok_account|momo|bank)$")
    payout_reference: Optional[str] = None
    payout_account_name: Optional[str] = None
    payout_bank_name: Optional[str] = None
    merchant_intent_reference: Optional[str] = None
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    product_description: Optional[str] = None
    product_price: Optional[float] = Field(default=None, gt=0)
    items: List[OrderItemCreate] = Field(default_factory=list)
    delivery_method: DeliveryMethod
    shipping_address: Optional[str] = None
    product_url: Optional[str] = None
    auto_import_product_details: bool = True
    payment_source: str = Field(default="verified_account", pattern="^(verified_account|momo|bank)$")

    @field_validator("product_price")
    @classmethod
    def validate_price(cls, v):
        if v is None:
            return v
        if v < 1.0:
            raise ValueError("Product price must be at least 1.00 GHS")
        return v

    @model_validator(mode="after")
    def validate_recipient_target(self):
        if self.recipient_id is None and not self.payout_reference:
            raise ValueError("Provide either recipient_id or payout_reference for payout")
        if self.recipient_id is None and not self.recipient_display_name:
            raise ValueError("recipient_display_name is required when recipient_id is not provided")
        return self

    @model_validator(mode="after")
    def validate_product_name(self):
        if not self.items and not self.product_name and not self.product_url:
            raise ValueError("Provide product_name, product_url, or items")
        if not self.items and self.product_price is None:
            raise ValueError("Provide product_price when items are not supplied")
        if self.items and self.product_price is not None:
            computed_total = sum(item.quantity * item.unit_price for item in self.items)
            if abs(computed_total - self.product_price) > 0.01:
                raise ValueError("product_price must match the sum of item totals when items are supplied")
        return self


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_reference: str
    session_reference: str
    payer_id: Optional[int]
    guest_checkout_session_id: Optional[int] = None
    guest_payer_name: Optional[str] = None
    guest_payer_phone_number: Optional[str] = None
    guest_payer_email: Optional[str] = None
    recipient_id: Optional[int]
    recipient_display_name: Optional[str]
    recipient_contact: Optional[str]
    payout_destination: str
    payout_reference: Optional[str]
    payout_account_name: Optional[str]
    payout_bank_name: Optional[str]
    product_name: str
    product_description: Optional[str]
    product_price: float
    items: List[OrderItemResponse] = Field(default_factory=list)
    item_count: int = 0
    platform_fee: float
    entry_fee: float
    release_fee: float
    total_amount: float
    payment_source: str
    product_url: Optional[str]
    source_site_name: Optional[str]
    imported_media: Optional[Dict]
    escrow_status: OrderStatus
    escrow_release_date: Optional[datetime]
    delivery_method: DeliveryMethod
    shipping_address: Optional[str]
    delivered_at: Optional[datetime]
    created_at: datetime
    escrow_account_active: bool
    is_guest_checkout: bool = False
    viewer_role: Optional[str] = None
    can_fund: bool = False
    can_confirm_delivery: bool = False
    can_generate_delivery_otp: bool = False
    can_submit_delivery_otp: bool = False
    can_open_dispute: bool = False
    is_read_only_monitor: bool = True
    
    days_until_release: Optional[int] = None
    
class DeliveryConfirmation(BaseModel):
    order_reference: str
    otp: str = Field(..., min_length=6, max_length=6)
    
    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v):
        if not v.isdigit():
            raise ValueError("OTP must contain only digits")
        return v
    
class DeliveryOTPGenerate(BaseModel):
    order_reference: str


class GuestCheckoutCreate(OrderCreate):
    guest_phone_number: str = Field(..., min_length=10, max_length=15)
    guest_full_name: str = Field(..., min_length=2, max_length=255)
    guest_email: Optional[str] = None


class GuestCheckoutResponse(OrderResponse):
    guest_session_id: int
    access_token: str
    refresh_token: str
    expires_at: datetime
    token_type: str = "bearer"


class PaginatedOrders(BaseModel):
    items: List[OrderResponse]
    total: int
    skip: int
    limit: int
    has_more: bool
