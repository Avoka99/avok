from datetime import datetime
from typing import Optional, List, Dict
import logging
import uuid
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.exceptions import DisputeError, NotFoundError, PermissionDeniedError
from app.core.config import settings
from app.models.dispute import Dispute, DisputeStatus, DisputeType
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.models.admin_action import AdminAction, AdminActionType, AdminActionStatus
from app.services.escrow import EscrowService
from app.services.notification import NotificationService
from app.services.fraud_detection import FraudDetectionService

logger = logging.getLogger(__name__)


class DisputeService:
    """Dispute management service."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.escrow_service = EscrowService(db)
        self.notification_service = NotificationService(db)
        self.fraud_service = FraudDetectionService(db)
    
    async def create_dispute(
        self,
        order_reference: str,
        buyer_id: int,
        dispute_type: DisputeType,
        description: str,
        evidence_urls: List[str] = None
    ) -> Dispute:
        """Create a new dispute."""
        order = await self._get_order_by_reference(order_reference)
        
        if order.buyer_id != buyer_id:
            raise PermissionDeniedError("Only the payer can open a dispute")
        
        if order.escrow_status not in [OrderStatus.PAYMENT_CONFIRMED, OrderStatus.SHIPPED]:
            raise DisputeError(f"Cannot open dispute for checkout session in status: {order.escrow_status}")
        
        # Check if dispute already exists
        existing = await self._get_dispute_by_order(order.id)
        if existing:
            raise DisputeError("Dispute already exists for this checkout session")
        
        # Update order status
        order.escrow_status = OrderStatus.DISPUTED
        
        # Create dispute
        dispute = Dispute(
            dispute_reference=f"DSP-{uuid.uuid4().hex[:8].upper()}",
            order_id=order.id,
            buyer_id=order.buyer_id,
            seller_id=order.seller_id,
            dispute_type=dispute_type,
            description=description,
            status=DisputeStatus.PENDING,
            evidence_urls=evidence_urls or []
        )
        
        self.db.add(dispute)
        await self.db.commit()
        
        # Run fraud detection
        fraud_result = await self.fraud_service.analyze_dispute(dispute)
        if fraud_result.get("is_fraudulent"):
            dispute.ai_analysis_result = fraud_result
            await self.db.commit()
            logger.warning(f"Potential fraud detected in dispute {dispute.dispute_reference}")
        
        # Notify seller and admins
        await self.notification_service.send_dispute_created(dispute)
        await self._notify_admins_new_dispute(dispute)
        
        logger.info(f"Dispute created: {dispute.dispute_reference} for checkout session {order_reference}")
        
        return dispute
    
    async def add_evidence(
        self,
        dispute_id: int,
        user_id: int,
        evidence_urls: List[str]
    ) -> Dispute:
        """Add evidence to dispute."""
        dispute = await self._get_dispute(dispute_id)
        
        if dispute.status not in [DisputeStatus.PENDING, DisputeStatus.UNDER_REVIEW]:
            raise DisputeError("Cannot add evidence to closed dispute")
        
        # Verify user is involved in dispute
        if user_id not in [dispute.buyer_id, dispute.seller_id]:
            raise PermissionDeniedError("Only dispute parties can add evidence")
        
        # Add evidence
        current_evidence = dispute.evidence_urls or []
        dispute.evidence_urls = current_evidence + evidence_urls
        
        # Update status to under review if it was pending
        if dispute.status == DisputeStatus.PENDING:
            dispute.status = DisputeStatus.UNDER_REVIEW
        
        await self.db.commit()
        
        # Re-run fraud detection with new evidence
        fraud_result = await self.fraud_service.analyze_dispute(dispute)
        if fraud_result.get("is_fraudulent"):
            dispute.ai_analysis_result = fraud_result
            await self.db.commit()
        
        logger.info(f"Evidence added to dispute {dispute.dispute_reference}")
        
        return dispute
    
    async def resolve_dispute(
        self,
        dispute_id: int,
        admin_id: int,
        resolution: str,
        notes: str = None
    ) -> AdminAction:
        """Resolve dispute (requires admin approval)."""
        dispute = await self._get_dispute(dispute_id)
        admin = await self._get_user(admin_id)
        
        if admin.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise PermissionDeniedError("Only admins can resolve disputes")
        
        # Create admin action for approval
        action_data = {
            "dispute_id": dispute.id,
            "resolution": resolution,
            "notes": notes,
            "order_id": dispute.order_id
        }
        
        admin_action = AdminAction(
            action_reference=f"ADM-{uuid.uuid4().hex[:8].upper()}",
            action_type=AdminActionType.DISPUTE_RESOLVE,
            status=AdminActionStatus.PENDING,
            target_dispute_id=dispute.id,
            action_data=action_data,
            reason=notes or f"Resolving dispute as {resolution}",
            requested_by_id=admin_id,
            approvals_required=settings.min_admin_approvals
        )
        
        self.db.add(admin_action)
        await self.db.commit()
        
        # Auto-approve if super admin and only 1 approval needed
        if admin.role == UserRole.SUPER_ADMIN and settings.min_admin_approvals == 1:
            await self.approve_dispute_resolution(admin_action.id, admin_id)
        
        logger.info(f"Dispute resolution initiated: {dispute.dispute_reference}")
        
        return admin_action
    
    async def approve_dispute_resolution(
        self,
        admin_action_id: int,
        admin_id: int
    ) -> AdminAction:
        """Approve dispute resolution (multi-admin approval)."""
        admin_action = await self._get_admin_action(admin_action_id)
        admin = await self._get_user(admin_id)
        
        if admin.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise PermissionDeniedError("Only admins can approve")
        
        # Check if already approved
        if admin_id in admin_action.approvers:
            raise DisputeError("Admin already approved this action")
        
        # Add approval
        approvers = admin_action.approvers or []
        approvers.append(admin_id)
        admin_action.approvers = approvers
        admin_action.approvals_received += 1
        
        # Check if enough approvals
        if admin_action.approvals_received >= admin_action.approvals_required:
            admin_action.status = AdminActionStatus.APPROVED
            await self.db.commit()
            
            # Execute resolution
            await self._execute_dispute_resolution(admin_action)
        
        await self.db.commit()
        
        logger.info(f"Dispute resolution approved by admin {admin_id}")
        
        return admin_action
    
    async def _execute_dispute_resolution(self, admin_action: AdminAction):
        """Execute the approved dispute resolution."""
        dispute = await self._get_dispute(admin_action.target_dispute_id)
        resolution = admin_action.action_data.get("resolution")
        notes = admin_action.action_data.get("notes")
        
        normalized_resolution = {
            "buyer_wins": "payer_wins",
            "seller_wins": "recipient_wins",
        }.get(resolution, resolution)

        if normalized_resolution == "payer_wins":
            # Full refund to payer
            await self.escrow_service.refund_buyer(
                dispute.order_id,
                f"Dispute resolved in payer's favor: {notes}",
                admin_action.id
            )
            dispute.status = DisputeStatus.RESOLVED_BUYER_WINS
            
            # Flag recipient for potential fraud
            if dispute.seller_id:
                await self.fraud_service.flag_user(dispute.seller_id, "dispute_lost")
            
        elif normalized_resolution == "recipient_wins":
            # Release funds to recipient
            order = await self._get_order(dispute.order_id)
            order.escrow_status = OrderStatus.DELIVERED
            await self.db.commit()
            
            await self.escrow_service.release_funds_to_seller(
                dispute.order_id,
                admin_approved=True
            )
            dispute.status = DisputeStatus.RESOLVED_SELLER_WINS
            
        elif normalized_resolution == "refund":
            # Full refund
            await self.escrow_service.refund_buyer(
                dispute.order_id,
                f"Dispute resolved with refund: {notes}",
                admin_action.id
            )
            dispute.status = DisputeStatus.RESOLVED_REFUND
        
        dispute.resolution_notes = notes
        dispute.resolved_by_id = admin_action.requested_by_id
        dispute.resolved_at = datetime.utcnow()
        
        admin_action.status = AdminActionStatus.EXECUTED
        admin_action.executed_by_id = admin_action.requested_by_id
        admin_action.executed_at = datetime.utcnow()
        
        await self.db.commit()
        
        # Notify parties
        await self.notification_service.send_dispute_resolved(dispute)
        
        logger.info(f"Dispute {dispute.dispute_reference} resolved: {normalized_resolution}")
    
    async def _get_dispute(self, dispute_id: int) -> Dispute:
        """Get dispute by ID."""
        result = await self.db.execute(
            select(Dispute).where(Dispute.id == dispute_id)
        )
        dispute = result.scalar_one_or_none()
        if not dispute:
            raise NotFoundError("Dispute", dispute_id)
        return dispute
    
    async def _get_dispute_by_order(self, order_id: int) -> Optional[Dispute]:
        """Get dispute by order ID."""
        result = await self.db.execute(
            select(Dispute).where(Dispute.order_id == order_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_order_by_reference(self, order_reference: str) -> Order:
        """Get order by reference."""
        result = await self.db.execute(
            select(Order).where(Order.order_reference == order_reference)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order", order_reference)
        return order
    
    async def _get_order(self, order_id: int) -> Order:
        """Get order by ID."""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order", order_id)
        return order
    
    async def _get_user(self, user_id: int) -> User:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)
        return user
    
    async def _get_admin_action(self, action_id: int) -> AdminAction:
        """Get admin action by ID."""
        result = await self.db.execute(
            select(AdminAction).where(AdminAction.id == action_id)
        )
        action = result.scalar_one_or_none()
        if not action:
            raise NotFoundError("AdminAction", action_id)
        return action
    
    async def _notify_admins_new_dispute(self, dispute: Dispute):
        """Notify admins about new dispute."""
        # In production, send to admin notification queue
        pass
