from typing import Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

from app.models.dispute import DisputeType, DisputeStatus


class DisputeCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_reference: str = Field(validation_alias=AliasChoices("session_reference", "order_reference"))
    dispute_type: DisputeType
    description: str = Field(..., min_length=10, max_length=1000)
    
    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("Description must be at least 10 characters")
        return v


class EvidenceUpload(BaseModel):
    dispute_id: int
    evidence_urls: List[str] = Field(..., min_length=1, max_length=10)


class DisputeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dispute_reference: str
    order_reference: str
    session_reference: str
    dispute_type: DisputeType
    description: str
    status: DisputeStatus
    evidence_urls: List[str] = []
    created_at: datetime
    updated_at: datetime
    
class DisputeResolution(BaseModel):
    dispute_id: int
    action: Literal['payer_wins', 'recipient_wins', 'refund', 'buyer_wins', 'seller_wins']
    notes: Optional[str] = None
