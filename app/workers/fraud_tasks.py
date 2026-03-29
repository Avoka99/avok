import logging
import asyncio
from datetime import datetime, timedelta

from app.core.database import get_db_context
from app.services.fraud_detection import FraudDetectionService
from app.workers.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


def _run_async_task(coro):
    """Run async task with proper event loop handling."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        asyncio.run(coro)


@celery_app.task(bind=True)
def scan_for_fraud(self):
    """Scan for fraudulent activities."""
    async def _scan():
        async with get_db_context() as db:
            from app.models.user import User, UserStatus
            from sqlalchemy import select, and_
            
            fraud_service = FraudDetectionService(db)
            
            result = await db.execute(
                select(User).where(
                    and_(
                        User.status == UserStatus.ACTIVE,
                        User.fraud_score < settings.fraud_auto_flag_threshold
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
    
    _run_async_task(_scan())


@celery_app.task(bind=True)
def analyze_suspicious_activity(self):
    """Analyze suspicious activity patterns."""
    async def _analyze():
        async with get_db_context() as db:
            from app.models.transaction import Transaction, TransactionStatus
            from app.models.user import User
            from app.models.wallet import Wallet
            from sqlalchemy import select, func, and_
            
            cutoff = datetime.utcnow() - timedelta(hours=1)
            
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
                user_result = await db.execute(
                    select(User).join(Wallet).where(Wallet.id == wallet_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user:
                    logger.warning(f"High transaction volume detected for user {user.id}: {count} in last hour")
                    
                    if not user.is_flagged and count > 20:
                        user.is_flagged = True
                        await db.commit()
                        logger.warning(f"User {user.id} flagged for high transaction volume")
    
    _run_async_task(_analyze())
