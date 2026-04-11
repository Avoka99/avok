from celery import Task
import logging
from datetime import datetime, timezone, timedelta

from app.core.database import get_db_context
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class EscrowTask(Task):
    """Base task with database session."""
    _db = None


@celery_app.task(base=EscrowTask, bind=True)
def schedule_escrow_release(self, order_id: int):
    """Schedule escrow release for an order."""
    import asyncio
    
    async def _release():
        from app.services.escrow import EscrowService
        
        async with get_db_context() as db:
            escrow_service = EscrowService(db)
            
            from app.models.order import Order, OrderStatus
            from sqlalchemy import select
            
            result = await db.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()
            
            if order and order.can_auto_release():
                if order.escrow_status == OrderStatus.SHIPPED:
                    order.escrow_status = OrderStatus.DELIVERED
                    order.delivered_at = datetime.now(timezone.utc)
                    await db.commit()
                await escrow_service.release_funds_to_seller(order_id)
                logger.info(f"Auto-released funds for order {order_id}")
            else:
                logger.info(f"Order {order_id} not eligible for auto-release")
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_release())
        else:
            loop.run_until_complete(_release())
    except RuntimeError:
        asyncio.run(_release())


@celery_app.task(base=EscrowTask, bind=True)
def auto_release_expired_escrow(self):
    """Auto-release escrow for orders that are delivered or past release date without dispute."""
    import asyncio
    
    async def _release_all():
        from app.services.escrow import EscrowService
        
        async with get_db_context() as db:
            from app.models.order import Order, OrderStatus
            from sqlalchemy import select, and_, or_
            
            result = await db.execute(
                select(Order).where(
                    and_(
                        Order.escrow_status.in_([OrderStatus.SHIPPED, OrderStatus.DELIVERED]),
                        Order.escrow_release_date.isnot(None),
                        Order.escrow_release_date <= datetime.now(timezone.utc),
                        Order.escrow_account_active == True
                    )
                )
            )
            orders = result.scalars().all()
            
            escrow_service = EscrowService(db)
            released_count = 0
            failed_count = 0
            
            for order in orders:
                try:
                    if order.escrow_status == OrderStatus.SHIPPED:
                        order.escrow_status = OrderStatus.DELIVERED
                        order.delivered_at = datetime.now(timezone.utc)
                        await db.commit()
                    
                    await escrow_service.release_funds_to_seller(order.id)
                    released_count += 1
                    logger.info(f"Auto-released order {order.order_reference}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to auto-release order {order.id}: {e}")
            
            logger.info(f"Auto-release complete: {released_count} released, {failed_count} failed")
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_release_all())
        else:
            loop.run_until_complete(_release_all())
    except RuntimeError:
        asyncio.run(_release_all())


@celery_app.task(base=EscrowTask, bind=True)
def process_withdrawal(self, transaction_id: int):
    """Process pending withdrawal."""
    import asyncio
    
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
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_process())
        else:
            loop.run_until_complete(_process())
    except RuntimeError:
        asyncio.run(_process())


@celery_app.task(base=EscrowTask, bind=True)
def cleanup_failed_transactions(self):
    """Cleanup old failed transactions."""
    import asyncio
    
    async def _cleanup():
        from app.models.transaction import Transaction, TransactionStatus
        
        async with get_db_context() as db:
            from sqlalchemy import select, and_
            
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            
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
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_cleanup())
        else:
            loop.run_until_complete(_cleanup())
    except RuntimeError:
        asyncio.run(_cleanup())
