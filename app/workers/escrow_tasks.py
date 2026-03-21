from celery import Task
import logging
from datetime import datetime, timedelta

from app.core.database import get_db_context
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class EscrowTask(Task):
    """Base task with database session."""
    _db = None
    
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Cleanup after task."""
        if self._db:
            pass


@celery_app.task(base=EscrowTask, bind=True)
def schedule_escrow_release(self, order_id: int):
    """Schedule escrow release for an order."""
    async def _release():
        # Import inside function to avoid circular imports
        from app.services.escrow import EscrowService
        
        async with get_db_context() as db:
            escrow_service = EscrowService(db)
            
            from app.models.order import Order
            from sqlalchemy import select
            
            result = await db.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()
            
            if order and order.can_auto_release():
                await escrow_service.release_funds_to_seller(order_id)
                logger.info(f"Auto-released funds for order {order_id}")
            else:
                logger.info(f"Order {order_id} not eligible for auto-release")
    
    import asyncio
    asyncio.run(_release())


@celery_app.task(base=EscrowTask, bind=True)
def auto_release_expired_escrow(self):
    """Auto-release all expired escrow orders."""
    async def _release_all():
        from app.services.escrow import EscrowService
        
        async with get_db_context() as db:
            from app.models.order import Order, OrderStatus
            from sqlalchemy import select, and_
            
            result = await db.execute(
                select(Order).where(
                    and_(
                        Order.escrow_status == OrderStatus.PAYMENT_CONFIRMED,
                        Order.escrow_release_date <= datetime.utcnow()
                    )
                )
            )
            orders = result.scalars().all()
            
            escrow_service = EscrowService(db)
            released_count = 0
            
            for order in orders:
                try:
                    await escrow_service.release_funds_to_seller(order.id)
                    released_count += 1
                    logger.info(f"Auto-released order {order.order_reference}")
                except Exception as e:
                    logger.error(f"Failed to auto-release order {order.id}: {e}")
            
            logger.info(f"Auto-released {released_count} orders")
    
    import asyncio
    asyncio.run(_release_all())


@celery_app.task(base=EscrowTask, bind=True)
def process_withdrawal(self, transaction_id: int):
    """Process pending withdrawal."""
    async def _process():
        from app.services.wallet import WalletService
        
        async with get_db_context() as db:
            wallet_service = WalletService(db)
            try:
                transaction = await wallet_service.process_withdrawal(transaction_id)
                logger.info(f"Processed withdrawal {transaction_id}")
            except Exception as e:
                logger.error(f"Failed to process withdrawal {transaction_id}: {e}")
                raise
    
    import asyncio
    asyncio.run(_process())


@celery_app.task(base=EscrowTask, bind=True)
def cleanup_failed_transactions(self):
    """Cleanup old failed transactions."""
    async def _cleanup():
        from app.models.transaction import Transaction, TransactionStatus
        
        async with get_db_context() as db:
            from sqlalchemy import select, and_
            
            cutoff = datetime.utcnow() - timedelta(days=7)
            
            result = await db.execute(
                select(Transaction).where(
                    and_(
                        Transaction.status == TransactionStatus.FAILED,
                        Transaction.created_at < cutoff
                    )
                )
            )
            failed = result.scalars().all()
            
            for transaction in failed:
                await db.delete(transaction)
            
            await db.commit()
            logger.info(f"Cleaned up {len(failed)} failed transactions")
    
    import asyncio
    asyncio.run(_cleanup())