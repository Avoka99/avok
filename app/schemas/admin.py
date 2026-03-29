from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.admin_action import AdminActionStatus, AdminActionType
from app.models.dispute import DisputeStatus, DisputeType
from app.models.user import KYCStatus, UserRole, UserStatus


class AdminDashboardResponse(BaseModel):
    total_users: int
    total_orders: int
    admin: str | None = None


class AdminUserActionResponse(BaseModel):
    message: str


class AdminDisputeQueueItem(BaseModel):
    dispute_id: int
    dispute_reference: str
    session_reference: Optional[str] = None
    order_reference: Optional[str] = None
    dispute_type: DisputeType
    dispute_status: DisputeStatus
    description: str
    evidence_count: int
    evidence_urls: list[str]
    created_at: datetime
    latest_action_id: Optional[int] = None
    latest_action_reference: Optional[str] = None
    latest_action_status: Optional[AdminActionStatus] = None
    latest_action_resolution: Optional[str] = None
    approvals_required: int = 0
    approvals_received: int = 0


class AdminActionQueueItem(BaseModel):
    id: int
    action_reference: str
    action_type: AdminActionType
    status: AdminActionStatus
    target_dispute_id: Optional[int] = None
    target_order_id: Optional[int] = None
    approvals_required: int
    approvals_received: int
    requested_by_id: int
    created_at: datetime
    reason: str
    resolution: Optional[str] = None


class AdminUserResponse(BaseModel):
    """Admin view of user - excludes sensitive fields."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    phone_number: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: UserRole
    status: UserStatus
    kyc_status: KYCStatus
    is_phone_verified: bool
    is_flagged: bool
    fraud_score: Optional[int] = None
    dispute_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
