from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class WalletBalance(BaseModel):
    available_balance: float
    pending_balance: float
    escrow_balance: float
    total_balance: float
    is_verified_account: bool


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    type: str = Field(validation_alias="transaction_type")
    status: str = Field(validation_alias="status")
    amount: float
    fee: float = Field(validation_alias="fee_amount")
    net_amount: float
    description: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    @field_validator("type", mode="before")
    @classmethod
    def convert_type_enum(cls, v):
        if hasattr(v, "value"):
            return v.value
        return str(v) if v else v

    @field_validator("status", mode="before")
    @classmethod
    def convert_status_enum(cls, v):
        if hasattr(v, "value"):
            return v.value
        return str(v) if v else v


class WithdrawalRequest(BaseModel):
    amount: float = Field(..., gt=0)
    destination_type: str = Field(..., pattern="^(momo|bank)$")
    destination_reference: str = Field(..., min_length=3, max_length=255)
    momo_provider: Optional[str] = None
    bank_name: Optional[str] = None


class DepositRequest(BaseModel):
    amount: float = Field(..., gt=0)
    source_type: str = Field(..., pattern="^(momo|bank)$")
    source_reference: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="MoMo number or bank account identifier the inbound transfer comes from.",
    )

    @field_validator("source_reference", mode="before")
    @classmethod
    def strip_source_reference(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v
