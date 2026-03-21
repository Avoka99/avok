from celery import Celery
from celery.schedules import crontab
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "avok",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.escrow_tasks",
        "app.workers.notification_tasks",
        "app.workers.fraud_tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    result_expires=3600,  # 1 hour
)

# Scheduled tasks
celery_app.conf.beat_schedule = {
    "auto-release-escrow": {
        "task": "app.workers.escrow_tasks.auto_release_expired_escrow",
        "schedule": crontab(hour="*/1"),  # Every hour
    },
    "send-reminders": {
        "task": "app.workers.notification_tasks.send_escrow_reminders",
        "schedule": crontab(hour="9,12,18"),  # 9 AM, 12 PM, 6 PM
    },
    "fraud-detection-scan": {
        "task": "app.workers.fraud_tasks.scan_for_fraud",
        "schedule": crontab(hour="*/6"),  # Every 6 hours
    },
    "cleanup-failed-transactions": {
        "task": "app.workers.escrow_tasks.cleanup_failed_transactions",
        "schedule": crontab(hour="2", minute="0"),  # 2 AM daily
    },
}