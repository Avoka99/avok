from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.admin_action import AdminActionStatus, AdminActionType
from app.models.dispute import DisputeStatus, DisputeType


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
