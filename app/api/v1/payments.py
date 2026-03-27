import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    get_db,
    require_payment_sandbox_enabled,
)
from app.core.config import settings
from app.core.payment_webhook import verify_payment_webhook
from app.models.user import User
from app.schemas.payment import PaymentCallback, PaymentInitiate, PaymentResponse
from app.services.order import OrderService
from app.services.payment import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])

SandboxGuard = Annotated[None, Depends(require_payment_sandbox_enabled)]


@router.post("/initiate", response_model=PaymentResponse)
async def initiate_payment(
    payment_data: PaymentInitiate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Initiate payment for a checkout session."""
    order_service = OrderService(db)
    payment_service = PaymentService(db)
    order = await order_service.get_order(payment_data.session_reference)

    if order.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the payer can initiate payment")

    result = await payment_service.initiate_payment(
        order_id=order.id,
        funding_source=payment_data.funding_source,
        payout_destination=payment_data.payout_destination,
        buyer=current_user,
        momo_provider=payment_data.momo_provider,
        momo_number=payment_data.momo_number,
        bank_reference=payment_data.bank_reference,
    )
    return result


@router.post("/callback")
async def payment_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Authenticated webhook from payment rails.

    Send header ``X-Avok-Webhook-Secret`` matching ``PAYMENT_WEBHOOK_SECRET``, or
    ``X-Avok-Webhook-Signature: sha256=<hmac>`` where HMAC is SHA256(secret, raw body).
    """
    raw = await request.body()
    verify_payment_webhook(
        raw_body=raw,
        headers=request.headers,
        webhook_secret=settings.payment_webhook_secret,
        debug=settings.debug,
    )
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )
    try:
        payload = PaymentCallback.model_validate(data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    payment_service = PaymentService(db)
    await payment_service.handle_payment_callback(
        transaction_reference=payload.transaction_reference,
        momo_transaction_id=payload.momo_transaction_id,
        status=payload.status,
        approval_code=payload.approval_code,
    )
    return {"message": "Callback received"}


@router.post("/sandbox/{transaction_reference}/success")
async def sandbox_payment_success(
    _: SandboxGuard,
    transaction_reference: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulate a successful payment in local development."""
    payment_service = PaymentService(db)
    transaction = await payment_service.handle_payment_callback(
        transaction_reference=transaction_reference,
        momo_transaction_id=f"SIM-{transaction_reference}",
        status="success",
        approval_code="SANDBOX",
    )
    return {
        "message": "Sandbox payment marked successful",
        "transaction_reference": transaction.reference,
        "status": transaction.status,
        "order_id": transaction.order_id,
    }


@router.post("/sandbox/{transaction_reference}/fail")
async def sandbox_payment_fail(
    _: SandboxGuard,
    transaction_reference: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulate a failed payment in local development."""
    payment_service = PaymentService(db)
    transaction = await payment_service.handle_payment_callback(
        transaction_reference=transaction_reference,
        momo_transaction_id=f"SIM-{transaction_reference}",
        status="failed",
    )
    return {
        "message": "Sandbox payment marked failed",
        "transaction_reference": transaction.reference,
        "status": transaction.status,
        "order_id": transaction.order_id,
    }
