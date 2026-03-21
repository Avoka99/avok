from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

from app.models.order import OrderStatus, DeliveryMethod


class OrderCreate(BaseModel):
    seller_id: int
    product_name: str = Field(..., min_length=1, max_length=255)
    product_description: Optional[str] = None
    product_price: float = Field(..., gt=0)
    delivery_method: DeliveryMethod
    shipping_address: Optional[str] = None
    
    @validator('product_price')
    def validate_price(cls, v):
        if v < 1.0:
            raise ValueError('Product price must be at least 1.00 GHS')
        return v


class OrderResponse(BaseModel):
    id: int
    order_reference: str
    buyer_id: int
    seller_id: int
    product_name: str
    product_description: Optional[str]
    product_price: float
    platform_fee: float
    total_amount: float
    escrow_status: OrderStatus
    escrow_release_date: Optional[datetime]
    delivery_method: DeliveryMethod
    shipping_address: Optional[str]
    delivered_at: Optional[datetime]
    created_at: datetime
    
    days_until_release: Optional[int] = None
    
    class Config:
        from_attributes = True


class DeliveryConfirmation(BaseModel):
    order_reference: str
    otp: str = Field(..., min_length=6, max_length=6)
    
    @validator('otp')
    def validate_otp(cls, v):
        if not v.isdigit():
            raise ValueError('OTP must contain only digits')
        return v


class DeliveryOTPGenerate(BaseModel):
    order_reference: str