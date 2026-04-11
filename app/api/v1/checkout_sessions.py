import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List

from app.api.dependencies import get_db, get_current_checkout_actor, get_current_user
from app.core.security import create_guest_access_token, create_guest_refresh_token
from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.order import OrderCreate, OrderResponse, DeliveryConfirmation, GuestCheckoutCreate, GuestCheckoutResponse, PaginatedOrders
from app.schemas.payment import PaymentInitiate, PaymentResponse
from app.services.order import OrderService
from app.services.payment import PaymentService
from app.services.escrow import EscrowService
from app.services.fraud_detection import FraudDetectionService
from app.models.user import User, UserRole
from app.services.guest_checkout import GuestCheckoutService
from app.services.merchant import MerchantService
from app.core.config import settings

router = APIRouter(prefix="/checkout/sessions", tags=["checkout sessions"])


@router.post("/", response_model=OrderResponse)
@router.post("", response_model=OrderResponse)
async def create_checkout_session(
    session_data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Create an Avok checkout session for an external website or embedded payment flow."""
    service = OrderService(db)
    merchant_service = MerchantService(db)
    try:
        payload = await merchant_service.resolve_embedded_order_payload(
            session_data.merchant_intent_reference,
            session_data.model_dump(exclude={"merchant_intent_reference"}),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    checkout_context = payload.pop("checkout_context", None)
    order = await service.create_order(buyer_id=current_user.id, checkout_context=checkout_context, **payload)
    if background_tasks:
        background_tasks.add_task(service.enrich_order_metadata, order.id)
    return order


@router.post("/guest", response_model=GuestCheckoutResponse)
async def create_guest_checkout_session(
    session_data: GuestCheckoutCreate,
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Create a temporary guest checkout session for a non-Avok payer."""
    existing_user = await db.execute(select(User).where(User.phone_number == session_data.guest_phone_number))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Phone number already belongs to an Avok account. Please sign in to continue.")
    
    fraud_service = FraudDetectionService(db)
    
    phone_prefix = session_data.guest_phone_number[:3] if len(session_data.guest_phone_number) >= 3 else ""
    if phone_prefix:
        from sqlalchemy import and_
        fraudulent_similar = await db.execute(
            select(User).where(
                and_(
                    User.phone_number.like(f"{phone_prefix}%"),
                    User.is_flagged == True
                )
            )
        )
        fraudulent_count = len(fraudulent_similar.scalars().all())
        
        if fraudulent_count >= 2:
            raise HTTPException(
                status_code=403,
                detail="We couldn't complete your checkout session. Please try again later or contact our support team for assistance."
            )
    
    merchant_service = MerchantService(db)
    try:
        resolved_payload = await merchant_service.resolve_embedded_order_payload(
            session_data.merchant_intent_reference,
            session_data.model_dump(exclude={"guest_phone_number", "guest_full_name", "guest_email", "merchant_intent_reference"}),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    checkout_context = resolved_payload.pop("checkout_context", {})

    product_price = resolved_payload.get("product_price") or session_data.product_price or sum(item.quantity * item.unit_price for item in session_data.items)
    if product_price > settings.fraud_high_value_threshold:
        if not session_data.guest_email:
            raise HTTPException(
                status_code=400,
                detail="For purchases above GHS 1,000, please provide your email address to help us verify your order."
            )

    guest_service = GuestCheckoutService(db)
    guest_session = await guest_service.create_session(
        phone_number=session_data.guest_phone_number,
        full_name=session_data.guest_full_name,
        email=session_data.guest_email,
    )

    service = OrderService(db)
    payload = resolved_payload
    session = await service.create_order(
        buyer_id=None,
        guest_checkout_session_id=guest_session.id,
        checkout_context={
            "guest_checkout": True,
            "guest_phone_number": session_data.guest_phone_number,
            "guest_full_name": session_data.guest_full_name,
            "guest_email": session_data.guest_email,
            **checkout_context,
        },
        **payload,
    )
    access_token = create_guest_access_token(guest_session.id, session.order_reference, expires_delta=GuestCheckoutService.ACCESS_TOKEN_TTL)
    refresh_token = create_guest_refresh_token(guest_session.id, session.order_reference, expires_delta=GuestCheckoutService.REFRESH_TOKEN_TTL)
    
    if background_tasks:
        background_tasks.add_task(service.enrich_order_metadata, session.id)

    await db.commit()
    session_payload = OrderResponse.model_validate(session).model_dump()
    return GuestCheckoutResponse(
        **session_payload,
        guest_session_id=guest_session.id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=guest_session.expires_at,
        token_type="bearer",
    )


@router.get("/", response_model=PaginatedOrders)
@router.get("", response_model=PaginatedOrders)
async def list_checkout_sessions(
    skip: int = 0,
    limit: int = 50,
    role: str = Query(None, description="Filter by relationship: 'buyer'/'payer' or 'seller'/'recipient'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List checkout sessions related to the authenticated user with pagination and actor context."""
    service = OrderService(db)
    
    if role in {"buyer", "payer"}:
        items = await service.get_buyer_orders(current_user.id, skip, limit)
    elif role in {"seller", "recipient"}:
        items = await service.get_seller_orders(current_user.id, skip, limit)
    else:
        items = await service.get_user_orders(current_user.id, skip, limit)

    enriched_items = [_with_actor_capabilities(item, current_user) for item in items]
    
    return PaginatedOrders(
        items=enriched_items,
        total=len(items), # Simplified total for now
        skip=skip,
        limit=limit,
        has_more=len(items) >= limit
    )


@router.get("/{session_reference}", response_model=OrderResponse)
async def get_checkout_session(
    session_reference: str,
    current_user = Depends(get_current_checkout_actor),
    db: AsyncSession = Depends(get_db),
):
    """Get a checkout session by reference."""
    service = OrderService(db)
    session = await service.get_order(session_reference)
    is_allowed_guest = getattr(current_user, "is_guest", False) and session.guest_checkout_session_id == getattr(current_user, "guest_session_id", None)
    if not is_allowed_guest and current_user.id not in [session.buyer_id, session.seller_id] and current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(status_code=403, detail="Permission denied")
    return _with_actor_capabilities(session, current_user)


def _with_actor_capabilities(session: OrderResponse, current_user):
    is_guest_actor = getattr(current_user, "is_guest", False)
    is_admin = not is_guest_actor and getattr(current_user, "role", None) in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
    is_payer = (
        session.guest_checkout_session_id == getattr(current_user, "guest_session_id", None)
        if is_guest_actor
        else session.buyer_id == getattr(current_user, "id", None)
    )
    is_recipient = not is_guest_actor and session.seller_id == getattr(current_user, "id", None)

    escrow_status = session.escrow_status.value if hasattr(session.escrow_status, "value") else str(session.escrow_status)
    can_fund = is_payer and escrow_status == "pending_payment"
    can_confirm_delivery = is_payer and escrow_status in {"shipped", "delivered"}
    can_generate_delivery_otp = is_recipient and escrow_status in {"payment_confirmed", "processing", "shipped"}
    can_submit_delivery_otp = is_recipient and escrow_status in {"shipped", "delivered"}
    can_open_dispute = (is_payer or is_recipient) and escrow_status in {"payment_confirmed", "processing", "shipped", "delivered"}

    viewer_role = "admin" if is_admin else "recipient" if is_recipient else "payer"

    return OrderResponse.model_validate(
        {
            **OrderResponse.model_validate(session).model_dump(),
            "viewer_role": viewer_role,
            "can_fund": can_fund,
            "can_confirm_delivery": can_confirm_delivery,
            "can_generate_delivery_otp": can_generate_delivery_otp,
            "can_submit_delivery_otp": can_submit_delivery_otp,
            "can_open_dispute": can_open_dispute,
            "is_read_only_monitor": not any(
                [
                    can_fund,
                    can_confirm_delivery,
                    can_generate_delivery_otp,
                    can_submit_delivery_otp,
                    can_open_dispute,
                ]
            ),
        }
    )


@router.post("/{session_reference}/fund", response_model=PaymentResponse)
async def fund_checkout_session(
    session_reference: str,
    payment_data: PaymentInitiate,
    current_user = Depends(get_current_checkout_actor),
    db: AsyncSession = Depends(get_db),
):
    """Fund a checkout session from Avok balance, MoMo, or bank rails."""
    order_service = OrderService(db)
    payment_service = PaymentService(db)
    session = await order_service.get_order(session_reference)

    is_guest_actor = getattr(current_user, "is_guest", False)
    if is_guest_actor:
        if session.guest_checkout_session_id != current_user.guest_session_id:
            raise HTTPException(status_code=403, detail="Only the payer can fund this checkout session")
    elif session.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the payer can fund this checkout session")

    return await payment_service.initiate_payment(
        order_id=session.id,
        funding_source=payment_data.funding_source,
        payout_destination=payment_data.payout_destination,
        buyer=None if is_guest_actor else current_user,
        guest_checkout_session=session.guest_checkout_session if is_guest_actor else None,
        momo_provider=payment_data.momo_provider,
        momo_number=payment_data.momo_number,
        bank_reference=payment_data.bank_reference,
    )


@router.post("/{session_reference}/confirm")
async def confirm_checkout_session(
    session_reference: str,
    current_user = Depends(get_current_checkout_actor),
    db: AsyncSession = Depends(get_db),
):
    """Payer confirms delivery and releases escrow."""
    order_service = OrderService(db)
    escrow_service = EscrowService(db)
    session = await order_service.get_order(session_reference)

    is_guest_actor = getattr(current_user, "is_guest", False)
    if is_guest_actor:
        if session.guest_checkout_session_id != current_user.guest_session_id:
            raise HTTPException(status_code=403, detail="Only the payer can confirm this checkout session")
    elif session.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the payer can confirm this checkout session")

    try:
        # Check for open dispute before confirming delivery
        from app.models.dispute import Dispute, DisputeStatus
        from sqlalchemy import select as sa_select
        dispute_check = await db.execute(
            sa_select(Dispute).where(
                Dispute.order_id == session.id,
                Dispute.status.in_([DisputeStatus.PENDING, DisputeStatus.UNDER_REVIEW])
            )
        )
        if dispute_check.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Cannot confirm delivery while a dispute is open. Please resolve the dispute first."
            )

        await order_service.confirm_delivery_manually(session.id, commit=False)
        await escrow_service.release_funds_to_seller(session.id)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    return {"message": "Checkout session confirmed and escrow released"}


@router.post("/{session_reference}/delivery/confirm")
async def confirm_checkout_session_with_otp(
    session_reference: str,
    confirmation: DeliveryConfirmation,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Registered payout recipients can confirm delivery with OTP."""
    order_service = OrderService(db)
    escrow_service = EscrowService(db)
    session = await order_service.get_order(session_reference)

    if session.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the registered payout recipient can confirm with OTP")

    await escrow_service.confirm_delivery_with_otp(session.id, confirmation.otp, current_user.id)
    return {"message": "Checkout session confirmed with OTP"}
