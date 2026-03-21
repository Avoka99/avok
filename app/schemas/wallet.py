from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class WalletBalance(BaseModel):
    available_balance: float
    pending_balance: float
    escrow_balance: float
    total_balance: float


class TransactionResponse(BaseModel):
    id: int
    reference: str
    type: str
    status: str
    amount: float
    fee: float
    net_amount: float
    description: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class WithdrawalRequest(BaseModel):
    amount: float = Field(..., gt=0)
    momo_number: str = Field(..., min_length=10, max_length=12)
    momo_provider: str