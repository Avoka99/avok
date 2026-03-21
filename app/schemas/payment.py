from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from enum import Enum


class MobileMoneyProvider(str, Enum):
    MTN = "mtn"
    VODAFONE = "vodafone"
    AIRTEL_TIGO = "airtel_tigo"


class PaymentInitiate(BaseModel):
    order_reference: str
    momo_provider: MobileMoneyProvider
    momo_number: str = Field(..., min_length=10, max_length=12)
    
    @validator('momo_number')
    def validate_ghana_phone(cls, v):
        import re
        if not re.match(r'^0[2459]\d{8}$', v):
            raise ValueError('Invalid Ghanaian phone number format')
        return v


class PaymentResponse(BaseModel):
    transaction_reference: str
    order_reference: str
    amount: float
    platform_fee: float
    total_amount: float
    momo_provider: MobileMoneyProvider
    momo_number: str
    payment_url: Optional[str] = None
    instructions: Optional[str] = None
    status: str


class PaymentCallback(BaseModel):
    transaction_reference: str
    momo_transaction_id: str
    status: Literal['success', 'failed']
    approval_code: Optional[str] = None
    message: Optional[str] = None