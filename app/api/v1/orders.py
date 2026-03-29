from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from app.api.dependencies import get_db, get_current_user
from app.schemas.order import OrderCreate, OrderResponse, DeliveryConfirmation, DeliveryOTPGenerate
from app.schemas.payment import PaymentInitiate, PaymentResponse
from app.services.order import OrderService
from app.services.payment import PaymentService
from app.services.escrow import EscrowService
from app.models.user import User, UserRole

router = APIRouter(prefix="/orders", tags=["orders"])


class PaginatedResponse(BaseModel):
    items: List
    total: int
    skip: int
    limit: int
    has_more: bool


@router.post("/", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a checkout session using the legacy orders endpoint."""
    order_service = OrderService(db)
    
    order = await order_service.create_order(
        buyer_id=current_user.id,
        **order_data.model_dump()
    )
    
    return order


@router.get("/{order_reference}", response_model=OrderResponse)
async def get_order(
    order_reference: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get checkout session details using the legacy orders endpoint."""
    order_service = OrderService(db)
    order = await order_service.get_order(order_reference)
    
    # Check permission
    if current_user.id not in [order.buyer_id, order.seller_id] and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    return order


@router.get("/", response_model=PaginatedResponse)
async def list_orders(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List the authenticated user's checkout sessions using the legacy orders endpoint."""
    order_service = OrderService(db)
    orders = await order_service.get_user_orders(current_user.id, skip, limit)
    total = len(orders)
    return PaginatedResponse(
        items=orders,
        total=total,
        skip=skip,
        limit=limit,
        has_more=total >= limit
    )


@router.post("/{order_reference}/payment", response_model=PaymentResponse)
async def initiate_payment(
    order_reference: str,
    payment_data: PaymentInitiate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate payment for a checkout session using the legacy orders endpoint."""
    order_service = OrderService(db)
    payment_service = PaymentService(db)
    
    order = await order_service.get_order(order_reference)
    
    # Verify user is the payer
    if order.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the payer can fund this session")
    
    # Initiate payment
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


@router.post("/{order_reference}/delivery/otp")
async def generate_delivery_otp(
    order_reference: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate OTP for delivery confirmation (registered recipient)."""
    order_service = OrderService(db)
    
    order = await order_service.get_order(order_reference)
    
    # Verify user is the registered recipient
    if order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the registered recipient can generate OTP")
    
    otp = await order_service.generate_delivery_otp(order.id)
    
    return {"otp": otp, "message": "OTP generated and sent to payer"}


@router.post("/{order_reference}/delivery/confirm")
async def confirm_delivery(
    order_reference: str,
    confirmation: DeliveryConfirmation,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Confirm delivery with OTP (registered recipient)."""
    order_service = OrderService(db)
    escrow_service = EscrowService(db)
    
    order = await order_service.get_order(order_reference)
    
    # Verify user is the registered recipient
    if order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the registered recipient can confirm delivery")
    
    # Confirm delivery with OTP
    await escrow_service.confirm_delivery_with_otp(
        order.id,
        confirmation.otp,
        current_user.id
    )
    
    return {"message": "Delivery confirmed successfully"}


@router.post("/{order_reference}/confirm")
async def manual_delivery_confirmation(
    order_reference: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manual delivery confirmation (payer)."""
    order_service = OrderService(db)
    escrow_service = EscrowService(db)
    
    order = await order_service.get_order(order_reference)
    
    # Verify user is the payer
    if order.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the payer can confirm delivery")
    
    # Manually confirm delivery
    await order_service.confirm_delivery_manually(order.id)
    
    # Release funds
    await escrow_service.release_funds_to_seller(order.id)
    
    return {"message": "Delivery confirmed successfully"}
