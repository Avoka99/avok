from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import List

from app.api.dependencies import get_db, get_current_user, get_current_admin
from app.schemas.dispute import DisputeCreate, DisputeResponse, DisputeResolution
from app.services.dispute import DisputeService
try:
    from app.services.storage import StorageService
except ImportError:
    StorageService = None
    print("StorageService not available")
from app.models.user import User, UserRole
from app.models.dispute import Dispute

router = APIRouter(prefix="/disputes", tags=["disputes"])


@router.get("/", response_model=List[DisputeResponse])
async def list_disputes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List disputes visible to the current user."""
    query = select(Dispute).options(selectinload(Dispute.order)).order_by(Dispute.created_at.desc())

    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        query = query.where(
            or_(
                Dispute.buyer_id == current_user.id,
                Dispute.seller_id == current_user.id,
            )
        )

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=DisputeResponse)
async def create_dispute(
    dispute_data: DisputeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new dispute for a checkout session (payer only)."""
    dispute_service = DisputeService(db)
    
    dispute = await dispute_service.create_dispute(
        order_reference=dispute_data.session_reference,
        buyer_id=current_user.id,
        dispute_type=dispute_data.dispute_type,
        description=dispute_data.description
    )
    
    return dispute


@router.post("/{dispute_id}/evidence")
async def upload_evidence(
    dispute_id: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload evidence for dispute."""
    dispute_service = DisputeService(db)
    storage_service = StorageService()
    
    # Upload files to S3
    uploaded_urls = []
    for file in files:
        url = await storage_service.upload_file(
            file=file,
            folder=f"disputes/{dispute_id}",
            user_id=current_user.id
        )
        uploaded_urls.append(url)
    
    # Add evidence to dispute
    dispute = await dispute_service.add_evidence(
        dispute_id=dispute_id,
        user_id=current_user.id,
        evidence_urls=uploaded_urls
    )
    
    return {"evidence_urls": uploaded_urls, "dispute": dispute}


@router.get("/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(
    dispute_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get dispute details."""
    dispute_service = DisputeService(db)
    dispute = await dispute_service._get_dispute(dispute_id)
    
    # Check permission
    if current_user.id not in [dispute.buyer_id, dispute.seller_id] and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    return dispute


@router.post("/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: int,
    resolution: DisputeResolution,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Resolve dispute (admin only)."""
    dispute_service = DisputeService(db)
    
    admin_action = await dispute_service.resolve_dispute(
        dispute_id=dispute_id,
        admin_id=current_user.id,
        resolution=resolution.action,
        notes=resolution.notes
    )
    
    return {
        "message": "Dispute resolution initiated",
        "admin_action_id": admin_action.id,
        "approvals_required": admin_action.approvals_required
    }


@router.post("/actions/{action_id}/approve")
async def approve_dispute_resolution(
    action_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve dispute resolution (admin)."""
    dispute_service = DisputeService(db)
    
    admin_action = await dispute_service.approve_dispute_resolution(
        admin_action_id=action_id,
        admin_id=current_user.id
    )
    
    if admin_action.status == "approved":
        return {"message": "Dispute resolution approved and executed"}
    else:
        return {
            "message": f"Dispute resolution approved ({admin_action.approvals_received}/{admin_action.approvals_required} approvals)",
            "remaining_approvals": admin_action.approvals_required - admin_action.approvals_received
        }
