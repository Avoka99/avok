from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_checkout_actor, get_db
from app.schemas.notification import NotificationResponse
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=List[NotificationResponse])
@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    limit: int = Query(50, ge=1, le=100),
    current_actor=Depends(get_current_checkout_actor),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    return await service.list_notifications_for_actor(current_actor, limit=limit)
