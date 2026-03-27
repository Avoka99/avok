import logging
from datetime import datetime, timedelta

from app.core.database import get_db_context
from app.services.fraud_detection import FraudDetectionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def scan_for_fraud(self):
    """Scan for fraudulent activities."""
    async def _scan():
        async with get_db_context() as db:
            from app.models.user import User, UserStatus
            from sqlalchemy import select, and_
            
            fraud_service = FraudDetectionService(db)
            
            # Get active users to scan
            result = await db.execute(
                select(User).where(
                    and_(
                        User.status == UserStatus.ACTIVE,
                        User.fraud_score < 80  # Not already heavily flagged
                    )
                ).limit(500)
            )
            users = result.scalars().all()
            
            flagged_users = 0
            
            for user in users:
                analysis = await fraud_service.analyze_user(user.id)
                if analysis["is_flagged"] and not user.is_flagged:
                    flagged_users += 1
                    logger.warning(f"User {user.id} flagged by fraud scan")
            
            logger.info(f"Fraud scan completed. Flagged {flagged_users} new users.")
    
    import asyncio
    asyncio.run(_scan())


@celery_app.task(bind=True)
def analyze_suspicious_activity(self):
    """Analyze suspicious activity patterns."""
    async def _analyze():
        async with get_db_context() as db:
            from app.models.transaction import Transaction, TransactionStatus
            from app.models.user import User
            from app.models.wallet import Wallet
            from sqlalchemy import select, func, and_
            
            # Find rapid transactions
            cutoff = datetime.utcnow() - timedelta(hours=1)
            
            # Count transactions per user in last hour
            result = await db.execute(
                select(
                    Transaction.wallet_id,
                    func.count(Transaction.id).label("tx_count")
                ).where(
                    and_(
                        Transaction.created_at >= cutoff,
                        Transaction.status == TransactionStatus.COMPLETED
                    )
                ).group_by(Transaction.wallet_id)
                .having(func.count(Transaction.id) > 10)
            )
            
            high_volume = result.all()
            
            for wallet_id, count in high_volume:
                # Get user for this wallet
                user_result = await db.execute(
                    select(User).join(Wallet).where(Wallet.id == wallet_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user:
                    logger.warning(f"High transaction volume detected for user {user.id}: {count} in last hour")
                    
                    # Flag user if not already flagged
                    if not user.is_flagged and count > 20:
                        user.is_flagged = True
                        await db.commit()
                        logger.warning(f"User {user.id} flagged for high transaction volume")
    
    import asyncio
    asyncio.run(_analyze())
