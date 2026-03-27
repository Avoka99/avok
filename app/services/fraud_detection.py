from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.user import KYCStatus, User
from app.models.order import Order, OrderStatus
from app.models.dispute import Dispute, DisputeStatus
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)


class FraudDetectionService:
    """Fraud detection and prevention service."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def analyze_dispute(self, dispute: Dispute) -> Dict:
        """Analyze dispute for potential fraud."""
        fraud_score = 0
        flags = []
        
        # Check buyer's dispute history
        buyer_disputes = await self._count_user_disputes(dispute.buyer_id)
        if buyer_disputes > 3:
            fraud_score += 30
            flags.append("High dispute rate as buyer")
        
        # Check seller's dispute history
        seller_disputes = await self._count_user_disputes(dispute.seller_id)
        if seller_disputes > 3:
            fraud_score += 30
            flags.append("High dispute rate as seller")
        
        # Check order amount
        order = await self._get_order(dispute.order_id)
        if order.total_amount > 1000:  # High-value order
            fraud_score += 10
            flags.append("High-value order")
        
        # Check if buyer has recent disputes
        recent_disputes = await self._count_recent_disputes(dispute.buyer_id, days=30)
        if recent_disputes > 2:
            fraud_score += 20
            flags.append("Multiple disputes in last 30 days")
        
        # Check if seller has received multiple disputes
        seller_recent = await self._count_recent_disputes(dispute.seller_id, days=30)
        if seller_recent > 2:
            fraud_score += 20
            flags.append("Multiple disputes against seller in last 30 days")
        
        # Check if order was created recently
        if order.created_at > datetime.utcnow() - timedelta(hours=24):
            fraud_score += 5
            flags.append("Order created less than 24 hours ago")
        
        # Analyze description for suspicious keywords
        suspicious_keywords = ["scam", "fraud", "fake", "not received", "wrong item"]
        if any(keyword in dispute.description.lower() for keyword in suspicious_keywords):
            fraud_score += 10
            flags.append("Suspicious keywords in description")
        
        is_fraudulent = fraud_score > 50
        
        return {
            "fraud_score": fraud_score,
            "is_fraudulent": is_fraudulent,
            "flags": flags,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
    
    async def analyze_user(self, user_id: int) -> Dict:
        """Analyze user for fraudulent behavior."""
        user = await self._get_user(user_id)
        fraud_score = user.fraud_score or 0
        flags = []
        
        # Check dispute rate
        disputes_count = await self._count_user_disputes(user_id)
        if disputes_count > 5:
            fraud_score += 40
            flags.append("Excessive disputes")
        
        # Check KYC status
        if user.kyc_status != KYCStatus.VERIFIED:
            fraud_score += 20
            flags.append("Unverified KYC")
        
        # Check order completion rate
        completion_rate = await self._get_completion_rate(user_id)
        if completion_rate < 0.5:  # Less than 50% completion
            fraud_score += 30
            flags.append("Low order completion rate")
        
        # Check account age
        account_age = (datetime.utcnow() - user.created_at).days
        if account_age < 7 and disputes_count > 0:
            fraud_score += 25
            flags.append("New account with disputes")
        
        # Check if flagged by admins
        if user.is_flagged:
            fraud_score += 50
            flags.append("Admin flagged")
        
        # Update user fraud score
        user.fraud_score = fraud_score
        if fraud_score >= 70 and not user.is_flagged:
            user.is_flagged = True
            logger.warning(f"User {user_id} flagged for fraud with score {fraud_score}")
        
        await self.db.commit()
        
        return {
            "user_id": user_id,
            "fraud_score": fraud_score,
            "is_flagged": user.is_flagged,
            "flags": flags,
            "analysis_timestamp": datetime.utcnow().isoformat()
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
    
    async def _count_recent_disputes(self, user_id: int, days: int) -> int:
        """Count recent disputes."""
        cutoff = datetime.utcnow() - timedelta(days=days)
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
        # In production, send to admin notification queue
        pass


# Import for OR
from sqlalchemy.sql import or_
