from typing import Dict, List, Optional
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.sql import or_

from app.models.user import KYCStatus, User
from app.models.order import Order, OrderStatus
from app.models.dispute import Dispute, DisputeStatus
from app.models.transaction import Transaction
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


class FraudDetectionService:
    """Fraud detection and prevention service."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_service = NotificationService(db)
    
    async def analyze_dispute(self, dispute: Dispute) -> Dict:
        """Analyze dispute for potential fraud."""
        fraud_score = 0
        flags = []
        
        buyer_disputes = await self._count_user_disputes(dispute.buyer_id)
        if buyer_disputes > settings.fraud_max_dispute_count:
            fraud_score += 30
            flags.append("High dispute rate as buyer")
        
        if dispute.seller_id is not None:
            seller_disputes = await self._count_user_disputes(dispute.seller_id)
            if seller_disputes > settings.fraud_max_dispute_count:
                fraud_score += 30
                flags.append("High dispute rate as seller")
        else:
            fraud_score += 5
            flags.append("External recipient dispute")
        
        order = await self._get_order(dispute.order_id)
        if order.total_amount > settings.fraud_high_value_threshold:
            fraud_score += 10
            flags.append("High-value order")
        
        recent_disputes = await self._count_recent_disputes(dispute.buyer_id, days=30)
        if recent_disputes > 2:
            fraud_score += 20
            flags.append("Multiple disputes in last 30 days")
        
        if dispute.seller_id is not None:
            seller_recent = await self._count_recent_disputes(dispute.seller_id, days=30)
            if seller_recent > 2:
                fraud_score += 20
                flags.append("Multiple disputes against seller in last 30 days")
        elif order.seller_contact:
            recipient_risk = await self._count_recent_disputes_by_contact(order.seller_contact, days=30)
            if recipient_risk > 2:
                fraud_score += 15
                flags.append("Multiple recent disputes against external recipient contact")
        
        if self._ensure_utc(order.created_at) > datetime.now(timezone.utc) - timedelta(hours=24):
            fraud_score += 5
            flags.append("Order created less than 24 hours ago")
        
        suspicious_keywords = ["scam", "fraud", "fake", "not received", "wrong item"]
        if any(keyword in dispute.description.lower() for keyword in suspicious_keywords):
            fraud_score += 10
            flags.append("Suspicious keywords in description")
        
        is_fraudulent = fraud_score > settings.fraud_medium_risk_threshold
        
        return {
            "fraud_score": fraud_score,
            "is_fraudulent": is_fraudulent,
            "flags": flags,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def analyze_user(self, user_id: int) -> Dict:
        """Analyze user for fraudulent behavior."""
        user = await self._get_user(user_id)
        fraud_score = user.fraud_score or 0
        flags = []
        
        disputes_count = await self._count_user_disputes(user_id)
        if disputes_count > settings.fraud_max_dispute_count + 2:
            fraud_score += 40
            flags.append("Excessive disputes")
        
        if user.kyc_status != KYCStatus.VERIFIED:
            fraud_score += 20
            flags.append("Unverified KYC")
        
        completion_rate = await self._get_completion_rate(user_id)
        if completion_rate < settings.fraud_completion_rate_threshold:
            fraud_score += 30
            flags.append("Low order completion rate")
        
        account_age = (datetime.now(timezone.utc) - self._ensure_utc(user.created_at)).days
        if account_age < settings.fraud_new_account_days and disputes_count > 0:
            fraud_score += 25
            flags.append("New account with disputes")
        
        if user.is_flagged:
            fraud_score += 50
            flags.append("Admin flagged")
        
        user.fraud_score = fraud_score
        if fraud_score >= settings.fraud_auto_flag_threshold and not user.is_flagged:
            user.is_flagged = True
            logger.warning(f"User {user_id} flagged for fraud with score {fraud_score}")
        
        await self.db.commit()
        
        return {
            "user_id": user_id,
            "fraud_score": fraud_score,
            "is_flagged": user.is_flagged,
            "flags": flags,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def flag_user(self, user_id: int, reason: str) -> User:
        """Flag user for fraud."""
        user = await self._get_user(user_id)
        
        user.is_flagged = True
        user.fraud_score = min(user.fraud_score + 30, 100)
        
        await self.db.commit()
        
        logger.warning(f"User {user_id} flagged for fraud: {reason}")
        
        # Trigger admin notification
        await self._notify_admins_fraud_flag(user_id, reason)
        
        return user
    
    async def _count_user_disputes(self, user_id: int) -> int:
        """Count disputes for a user."""
        result = await self.db.execute(
            select(func.count()).where(
                or_(
                    Dispute.buyer_id == user_id,
                    Dispute.seller_id == user_id
                )
            )
        )
        return result.scalar() or 0

    async def _count_recent_disputes_by_contact(self, recipient_contact: str, days: int) -> int:
        """Count recent disputes involving an external recipient contact."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(func.count())
            .select_from(Dispute)
            .join(Order, Order.id == Dispute.order_id)
            .where(
                and_(
                    Order.seller_id.is_(None),
                    Order.seller_contact == recipient_contact,
                    Dispute.created_at >= cutoff,
                )
            )
        )
        return result.scalar() or 0
    
    async def _count_recent_disputes(self, user_id: int, days: int) -> int:
        """Count recent disputes."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(func.count()).where(
                and_(
                    or_(
                        Dispute.buyer_id == user_id,
                        Dispute.seller_id == user_id
                    ),
                    Dispute.created_at >= cutoff
                )
            )
        )
        return result.scalar() or 0
    
    async def _get_completion_rate(self, user_id: int) -> float:
        """Get order completion rate for user."""
        # Get total orders
        total_orders = await self.db.execute(
            select(func.count()).where(
                or_(
                    Order.buyer_id == user_id,
                    Order.seller_id == user_id
                )
            )
        )
        total = total_orders.scalar() or 0
        
        if total == 0:
            return 1.0
        
        # Get completed orders
        completed = await self.db.execute(
            select(func.count()).where(
                and_(
                    or_(
                        Order.buyer_id == user_id,
                        Order.seller_id == user_id
                    ),
                    Order.escrow_status == OrderStatus.COMPLETED
                )
            )
        )
        completed_count = completed.scalar() or 0
        
        return completed_count / total
    
    async def _get_user(self, user_id: int) -> User:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)
        return user
    
    async def _get_order(self, order_id: int) -> Order:
        """Get order by ID."""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order", order_id)
        return order
    
    async def _notify_admins_fraud_flag(self, user_id: int, reason: str):
        """Notify admins about flagged user."""
        action_url = f"{settings.frontend_base_url.rstrip('/')}/admin"
        await self.notification_service.notify_admins(
            title="Fraud flag requires admin review",
            message=(
                f"User {user_id} was flagged by the fraud engine. "
                f"Reason: {reason}. Review the account and recent escrow activity."
            ),
            action_url=action_url,
        )

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
