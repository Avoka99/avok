import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_checkout_actor,
    get_current_admin,
    get_db,
    require_payment_sandbox_enabled,
)
from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.payment_webhook import verify_payment_webhook
from app.schemas.merchant import MerchantCreate, MerchantIntentCreate, MerchantIntentPayload, MerchantIntentResponse, MerchantResponse
from app.schemas.payment import PaymentCallback, PaymentInitiate, PaymentResponse
from app.models.user import User
from app.services.merchant import MerchantService
from app.services.order import OrderService
from app.services.payment import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])

SandboxGuard = Annotated[None, Depends(require_payment_sandbox_enabled)]


@router.post("/merchants", response_model=MerchantResponse)
async def create_merchant(
    merchant_data: MerchantCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = MerchantService(db)
    try:
        merchant = await service.create_merchant(merchant_data)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
    return merchant


@router.post("/embed/intents", response_model=MerchantIntentResponse)
async def create_embed_intent(
    request: Request,
    intent_data: MerchantIntentCreate,
    merchant_id: str = Header(..., alias="X-Avok-Merchant-Id"),
    signature: str = Header(..., alias="X-Avok-Signature"),
    merchant_secret: str | None = Header(default=None, alias="X-Avok-Merchant-Secret"),
    db: AsyncSession = Depends(get_db),
):
    service = MerchantService(db)
    try:
        canonical_payload = MerchantService._canonicalize_payload(
            json.loads((await request.body()).decode("utf-8"))
        )
        return await service.create_checkout_intent(
            merchant_id=merchant_id,
            signature=signature,
            payload=intent_data,
            canonical_payload=canonical_payload,
            provided_secret_key=merchant_secret,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.get("/embed/intents/{intent_reference}", response_model=MerchantIntentPayload)
async def get_embed_intent(
    intent_reference: str,
    db: AsyncSession = Depends(get_db),
):
    service = MerchantService(db)
    try:
        return await service.get_checkout_intent(intent_reference)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.post("/initiate", response_model=PaymentResponse)
async def initiate_payment(
    payment_data: PaymentInitiate,
    current_user = Depends(get_current_checkout_actor),
    db: AsyncSession = Depends(get_db),
):
    """Initiate payment for a checkout session."""
    if not payment_data.session_reference:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="session_reference is required")

    order_service = OrderService(db)
    payment_service = PaymentService(db)
    order = await order_service.get_order(payment_data.session_reference)

    is_guest_actor = getattr(current_user, "is_guest", False)
    if is_guest_actor:
        if order.guest_checkout_session_id != current_user.guest_session_id:
            raise HTTPException(status_code=403, detail="Only the payer can initiate payment")
    elif order.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the payer can initiate payment")

    result = await payment_service.initiate_payment(
        order_id=order.id,
        funding_source=payment_data.funding_source,
        payout_destination=payment_data.payout_destination,
        buyer=None if is_guest_actor else current_user,
        guest_checkout_session=order.guest_checkout_session if is_guest_actor else None,
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
    Supports idempotency via ``X-Avok-Idempotency-Key`` header.
    """
    raw = await request.body()
    verify_payment_webhook(
        raw_body=raw,
        headers=request.headers,
        webhook_secret=settings.payment_webhook_secret,
        debug=settings.debug,
    )

    # Idempotency check via header
    idempotency_key = request.headers.get("X-Avok-Idempotency-Key")
    if idempotency_key:
        from app.core.redis_client import get_redis_client
        redis = get_redis_client()
        if redis:
            existing = await redis.get(f"idempotency:payment:{idempotency_key}")
            if existing:
                return {"message": "Callback already processed", "idempotent": True}

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

    # Store idempotency key
    if idempotency_key:
        from app.core.redis_client import get_redis_client
        redis = get_redis_client()
        if redis:
            await redis.setex(f"idempotency:payment:{idempotency_key}", 86400, "1")

    return {"message": "Callback received"}


@router.post("/sandbox/{transaction_reference}/success")
async def sandbox_payment_success(
    _: SandboxGuard,
    transaction_reference: str,
    current_user = Depends(get_current_checkout_actor),
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
    current_user = Depends(get_current_checkout_actor),
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
