import logging
import asyncio
from datetime import datetime, timedelta

from app.core.database import get_db_context
from app.services.notification import NotificationService
from app.workers.celery_app import celery_app

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
def send_escrow_reminders(self):
    """Send escrow release reminders."""
    async def _send():
        async with get_db_context() as db:
            from app.models.order import Order, OrderStatus
            from sqlalchemy import select, and_
            from app.core.config import settings
            
            notification_service = NotificationService(db)
            
            result = await db.execute(
                select(Order).where(
                    and_(
                        Order.escrow_status.in_([OrderStatus.SHIPPED, OrderStatus.DELIVERED]),
                        Order.escrow_release_date.isnot(None)
                    )
                )
            )
            orders = result.scalars().all()
            
            reminders_sent = 0
            
            for order in orders:
                days_remaining = order.days_until_auto_release()
                
                if days_remaining is not None:
                    if days_remaining == settings.escrow_reminder_day_1:
                        await notification_service.send_reminder(order, days_remaining)
                        reminders_sent += 1
                    elif days_remaining == settings.escrow_reminder_day_2:
                        await notification_service.send_reminder(order, days_remaining)
                        reminders_sent += 1
                    elif days_remaining == settings.escrow_reminder_day_3:
                        await notification_service.send_reminder(order, days_remaining)
                        reminders_sent += 1
            
            logger.info(f"Sent {reminders_sent} escrow reminders")
    
    _run_async_task(_send())


@celery_app.task(bind=True)
def retry_failed_notifications(self):
    """Retry failed notifications."""
    async def _retry():
        async with get_db_context() as db:
            from app.models.notification import Notification, NotificationStatus, NotificationType
            from sqlalchemy import select, and_
            
            result = await db.execute(
                select(Notification).where(
                    and_(
                        Notification.status == NotificationStatus.FAILED,
                        Notification.retry_count < 3
                    )
                ).limit(100)
            )
            notifications = result.scalars().all()
            
            notification_service = NotificationService(db)
            retried_count = 0
            
            for notification in notifications:
                try:
                    if notification.notification_type == NotificationType.SMS:
                        await notification_service.send_sms(
                            notification.recipient,
                            notification.content
                        )
                    elif notification.notification_type == NotificationType.EMAIL:
                        await notification_service.send_email(
                            notification.recipient,
                            notification.title,
                            notification.content
                        )
                    
                    notification.retry_count += 1
                    await db.commit()
                    retried_count += 1
                    
                except Exception as e:
                    notification.retry_count += 1
                    notification.error_message = str(e)
                    await db.commit()
                    logger.error(f"Failed to retry notification {notification.id}: {e}")
            
            logger.info(f"Retried {retried_count} notifications")
    
    _run_async_task(_retry())
