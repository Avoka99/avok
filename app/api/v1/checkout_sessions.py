import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.api.dependencies import get_db, get_current_user
from app.core.security import create_access_token, create_refresh_token, get_password_hash
from app.schemas.order import OrderCreate, OrderResponse, DeliveryConfirmation, GuestCheckoutCreate, GuestCheckoutResponse
from app.schemas.payment import PaymentInitiate, PaymentResponse
from app.models.wallet import Wallet, WalletType
from app.services.order import OrderService
from app.services.payment import PaymentService
from app.services.escrow import EscrowService
from app.models.user import User, UserRole, UserStatus

router = APIRouter(prefix="/checkout/sessions", tags=["checkout sessions"])


@router.post("/", response_model=OrderResponse)
@router.post("", response_model=OrderResponse)
async def create_checkout_session(
    session_data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an Avok checkout session for an external website or embedded payment flow."""
    service = OrderService(db)
    return await service.create_order(buyer_id=current_user.id, **session_data.model_dump())


@router.post("/guest", response_model=GuestCheckoutResponse)
async def create_guest_checkout_session(
    session_data: GuestCheckoutCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a temporary guest checkout session for a non-Avok payer."""
    existing_user = await db.execute(select(User).where(User.phone_number == session_data.guest_phone_number))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Phone number already belongs to an Avok account. Please sign in to continue.")

    guest_user = User(
        phone_number=session_data.guest_phone_number,
        email=session_data.guest_email,
        full_name=session_data.guest_full_name,
        hashed_password=get_password_hash(secrets.token_urlsafe(24)),
        role=UserRole.BUYER,
        status=UserStatus.ACTIVE,
        is_phone_verified=False,
    )
    db.add(guest_user)
    await db.flush()

    guest_wallet = Wallet(user_id=guest_user.id, wallet_type=WalletType.MAIN)
    db.add(guest_wallet)
    await db.flush()

    service = OrderService(db)
    payload = session_data.model_dump(exclude={"guest_phone_number", "guest_full_name", "guest_email", "merchant_name", "return_url", "cancel_url"})
    session = await service.create_order(
        buyer_id=guest_user.id,
        checkout_context={
            "guest_checkout": True,
            "guest_phone_number": session_data.guest_phone_number,
            "guest_full_name": session_data.guest_full_name,
            "guest_email": session_data.guest_email,
            "merchant_name": session_data.merchant_name,
            "return_url": session_data.return_url,
            "cancel_url": session_data.cancel_url,
        },
        **payload,
    )
    access_token = create_access_token({"sub": str(guest_user.id), "role": guest_user.role.value})
    refresh_token = create_refresh_token({"sub": str(guest_user.id), "role": guest_user.role.value})
    return {
        **GuestCheckoutResponse.model_validate(session).model_dump(),
        "guest_user_id": guest_user.id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get("/", response_model=List[OrderResponse])
@router.get("", response_model=List[OrderResponse])
async def list_checkout_sessions(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List checkout sessions related to the authenticated user."""
    service = OrderService(db)
    return await service.get_user_orders(current_user.id, skip, limit)


@router.get("/{session_reference}", response_model=OrderResponse)
async def get_checkout_session(
    session_reference: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a checkout session by reference."""
    service = OrderService(db)
    session = await service.get_order(session_reference)
    if current_user.id not in [session.buyer_id, session.seller_id] and current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(status_code=403, detail="Permission denied")
    return session


@router.post("/{session_reference}/fund", response_model=PaymentResponse)
async def fund_checkout_session(
    session_reference: str,
    payment_data: PaymentInitiate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fund a checkout session from Avok balance, MoMo, or bank rails."""
    order_service = OrderService(db)
    payment_service = PaymentService(db)
    session = await order_service.get_order(session_reference)

    if session.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the payer can fund this checkout session")

    return await payment_service.initiate_payment(
        order_id=session.id,
        funding_source=payment_data.funding_source,
        payout_destination=payment_data.payout_destination,
        buyer=current_user,
        momo_provider=payment_data.momo_provider,
        momo_number=payment_data.momo_number,
        bank_reference=payment_data.bank_reference,
    )


@router.post("/{session_reference}/confirm")
async def confirm_checkout_session(
    session_reference: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Payer confirms delivery and releases escrow."""
    order_service = OrderService(db)
    escrow_service = EscrowService(db)
    session = await order_service.get_order(session_reference)

    if session.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the payer can confirm this checkout session")

    await order_service.confirm_delivery_manually(session.id)
    await escrow_service.release_funds_to_seller(session.id)
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
