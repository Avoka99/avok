from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

from app.models.dispute import DisputeType, DisputeStatus


class DisputeCreate(BaseModel):
    order_reference: str
    dispute_type: DisputeType
    description: str = Field(..., min_length=10, max_length=1000)
    
    @validator('description')
    def validate_description(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('Description must be at least 10 characters')
        return v


class EvidenceUpload(BaseModel):
    dispute_id: int
    evidence_urls: List[str] = Field(..., min_items=1, max_items=10)


class DisputeResponse(BaseModel):
    id: int
    dispute_reference: str
    order_reference: str
    dispute_type: DisputeType
    description: str
    status: DisputeStatus
    evidence_urls: List[str] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DisputeResolution(BaseModel):
    dispute_id: int
    action: Literal['buyer_wins', 'seller_wins', 'refund']
    notes: Optional[str] = None