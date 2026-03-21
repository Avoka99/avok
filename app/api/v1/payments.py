from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db, get_current_user
from app.schemas.payment import PaymentInitiate, PaymentResponse
from app.services.payment import PaymentService
from app.models.user import User

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/initiate", response_model=PaymentResponse)
async def initiate_payment(
    payment_data: PaymentInitiate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate payment for an order."""
    payment_service = PaymentService(db)
    result = await payment_service.initiate_payment(
        order_id=payment_data.order_id,
        momo_provider=payment_data.momo_provider,
        momo_number=payment_data.momo_number
    )
    return result


@router.post("/callback")
async def payment_callback(
    transaction_reference: str,
    status: str,
    db: AsyncSession = Depends(get_db)
):
    """Handle payment callback from mobile money provider."""
    payment_service = PaymentService(db)
    await payment_service.handle_payment_callback(
        transaction_reference=transaction_reference,
        momo_transaction_id="",
        status=status
    )
    return {"message": "Callback received"}