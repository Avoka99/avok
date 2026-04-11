from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional, Literal
from enum import Enum


class MobileMoneyProvider(str, Enum):
    MTN = "mtn"
    TELECEL = "telecel"
    AIRTEL_TIGO = "airtel_tigo"


class FundingSource(str, Enum):
    VERIFIED_ACCOUNT = "verified_account"
    MOMO = "momo"
    BANK = "bank"


class PaymentInitiate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_reference: Optional[str] = Field(default=None, validation_alias=AliasChoices("session_reference", "order_reference"))
    funding_source: FundingSource = FundingSource.VERIFIED_ACCOUNT
    payout_destination: str = Field(default="avok_account", description="avok_account, momo, or bank")
    momo_provider: Optional[MobileMoneyProvider] = None
    momo_number: Optional[str] = Field(default=None, min_length=10, max_length=12)
    bank_reference: Optional[str] = None
    
    @field_validator("momo_number")
    @classmethod
    def validate_ghana_phone(cls, v):
        if not v:
            return v
        import re

        if not re.match(r"^0[2459]\d{8}$", v):
            raise ValueError("Invalid Ghanaian phone number format")
        return v

    @model_validator(mode="after")
    def validate_payment_channel(self):
        if self.funding_source == FundingSource.MOMO and not self.momo_provider:
            raise ValueError("momo_provider is required for mobile money payments")
        return self


class PaymentResponse(BaseModel):
    transaction_reference: str
    order_reference: str
    session_reference: str
    amount: float
    platform_fee: float
    total_amount: float
    entry_fee: float
    release_fee: float
    funding_source: str
    payout_destination: str
    momo_provider: Optional[MobileMoneyProvider] = None
    momo_number: Optional[str] = None
    payment_url: Optional[str] = None
    instructions: Optional[str] = None
    status: str


class PaymentCallback(BaseModel):
    transaction_reference: str
    momo_transaction_id: str
    status: Literal['success', 'failed']
    approval_code: Optional[str] = None
    message: Optional[str] = None
