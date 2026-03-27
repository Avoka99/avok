from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db, get_current_admin
from app.schemas.admin import AdminActionQueueItem, AdminDisputeQueueItem
from app.models.admin_action import AdminAction
from app.models.dispute import Dispute
from app.models.user import User, UserStatus

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)."""
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return {"users": users, "count": len(users)}


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get user details (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/dashboard")
async def admin_dashboard(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin dashboard statistics."""
    from app.models.order import Order
    
    # Get user count
    user_count_result = await db.execute(select(func.count()).select_from(User))
    total_users = user_count_result.scalar()
    
    # Get order count
    order_count_result = await db.execute(select(func.count()).select_from(Order))
    total_orders = order_count_result.scalar()
    
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "admin": current_user.email
    }


@router.get("/disputes/queue", response_model=List[AdminDisputeQueueItem])
async def get_dispute_queue(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Return disputes with their latest admin-action state for admin review."""
    result = await db.execute(
        select(Dispute)
        .options(selectinload(Dispute.order))
        .order_by(Dispute.created_at.desc())
    )
    disputes = result.scalars().all()

    queue_items: List[AdminDisputeQueueItem] = []
    for dispute in disputes:
        latest_action_result = await db.execute(
            select(AdminAction)
            .where(AdminAction.target_dispute_id == dispute.id)
            .order_by(AdminAction.created_at.desc())
            .limit(1)
        )
        latest_action = latest_action_result.scalar_one_or_none()
        queue_items.append(
            AdminDisputeQueueItem(
                dispute_id=dispute.id,
                dispute_reference=dispute.dispute_reference,
                session_reference=dispute.session_reference,
                order_reference=dispute.order_reference,
                dispute_type=dispute.dispute_type,
                dispute_status=dispute.status,
                description=dispute.description,
                evidence_count=len(dispute.evidence_urls or []),
                evidence_urls=dispute.evidence_urls or [],
                created_at=dispute.created_at,
                latest_action_id=latest_action.id if latest_action else None,
                latest_action_reference=latest_action.action_reference if latest_action else None,
                latest_action_status=latest_action.status if latest_action else None,
                latest_action_resolution=(latest_action.action_data or {}).get("resolution") if latest_action else None,
                approvals_required=latest_action.approvals_required if latest_action else 0,
                approvals_received=latest_action.approvals_received if latest_action else 0,
            )
        )

    return queue_items


@router.get("/actions", response_model=List[AdminActionQueueItem])
async def list_admin_actions(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List admin actions so approval queues can be surfaced in the UI."""
    result = await db.execute(
        select(AdminAction).order_by(AdminAction.created_at.desc())
    )
    actions = result.scalars().all()
    return [
        AdminActionQueueItem(
            id=action.id,
            action_reference=action.action_reference,
            action_type=action.action_type,
            status=action.status,
            target_dispute_id=action.target_dispute_id,
            target_order_id=action.target_order_id,
            approvals_required=action.approvals_required,
            approvals_received=action.approvals_received,
            requested_by_id=action.requested_by_id,
            created_at=action.created_at,
            reason=action.reason,
            resolution=(action.action_data or {}).get("resolution"),
        )
        for action in actions
    ]


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend a user (admin only)."""
    from sqlalchemy import select, update
    from app.models.user import User
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.status = UserStatus.SUSPENDED
    await db.commit()
    
    return {"message": f"User {user_id} suspended"}
