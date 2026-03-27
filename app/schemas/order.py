from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum

from app.models.order import OrderStatus, DeliveryMethod


class OrderCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recipient_id: Optional[int] = Field(default=None, validation_alias=AliasChoices("recipient_id", "seller_id"))
    recipient_display_name: Optional[str] = Field(default=None, max_length=255, validation_alias=AliasChoices("recipient_display_name", "seller_display_name"))
    recipient_contact: Optional[str] = Field(default=None, max_length=255, validation_alias=AliasChoices("recipient_contact", "seller_contact"))
    payout_destination: str = Field(default="avok_account", pattern="^(avok_account|momo|bank)$")
    payout_reference: Optional[str] = None
    payout_account_name: Optional[str] = None
    payout_bank_name: Optional[str] = None
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    product_description: Optional[str] = None
    product_price: float = Field(..., gt=0)
    delivery_method: DeliveryMethod
    shipping_address: Optional[str] = None
    product_url: Optional[str] = None
    auto_import_product_details: bool = True
    payment_source: str = Field(default="verified_account", pattern="^(verified_account|momo|bank)$")

    @field_validator("product_price")
    @classmethod
    def validate_price(cls, v):
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
        if not self.product_name and not self.product_url:
            raise ValueError("Provide product_name or product_url")
        return self


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_reference: str
    session_reference: str
    payer_id: int
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
    merchant_name: Optional[str] = Field(default=None, max_length=255)
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None


class GuestCheckoutResponse(OrderResponse):
    guest_user_id: int
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
