from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.dependencies import get_db, get_current_user, get_current_seller
from app.schemas.order import OrderCreate, OrderResponse, DeliveryConfirmation, DeliveryOTPGenerate
from app.schemas.payment import PaymentInitiate, PaymentResponse
from app.services.order import OrderService
from app.services.payment import PaymentService
from app.services.escrow import EscrowService
from app.models.user import User

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new order (buyer)."""
    order_service = OrderService(db)
    
    # Only buyers can create orders
    if current_user.role != "buyer":
        raise HTTPException(status_code=403, detail="Only buyers can create orders")
    
    order = await order_service.create_order(
        buyer_id=current_user.id,
        **order_data.dict()
    )
    
    return order


@router.get("/{order_reference}", response_model=OrderResponse)
async def get_order(
    order_reference: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get order details."""
    order_service = OrderService(db)
    order = await order_service.get_order(order_reference)
    
    # Check permission
    if current_user.id not in [order.buyer_id, order.seller_id] and current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    return order


@router.get("/", response_model=List[OrderResponse])
async def list_orders(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's orders."""
    order_service = OrderService(db)
    orders = await order_service.get_user_orders(current_user.id, skip, limit)
    return orders


@router.post("/{order_reference}/payment", response_model=PaymentResponse)
async def initiate_payment(
    order_reference: str,
    payment_data: PaymentInitiate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate payment for order."""
    order_service = OrderService(db)
    payment_service = PaymentService(db)
    
    order = await order_service.get_order(order_reference)
    
    # Verify user is the buyer
    if order.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only buyer can pay")
    
    # Initiate payment
    result = await payment_service.initiate_payment(
        order_id=order.id,
        momo_provider=payment_data.momo_provider,
        momo_number=payment_data.momo_number
    )
    
    return result


@router.post("/{order_reference}/delivery/otp")
async def generate_delivery_otp(
    order_reference: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate OTP for delivery confirmation (seller)."""
    order_service = OrderService(db)
    
    order = await order_service.get_order(order_reference)
    
    # Verify user is the seller
    if order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only seller can generate OTP")
    
    otp = await order_service.generate_delivery_otp(order.id)
    
    return {"otp": otp, "message": "OTP generated and sent to buyer"}


@router.post("/{order_reference}/delivery/confirm")
async def confirm_delivery(
    order_reference: str,
    confirmation: DeliveryConfirmation,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Confirm delivery with OTP (seller)."""
    order_service = OrderService(db)
    escrow_service = EscrowService(db)
    
    order = await order_service.get_order(order_reference)
    
    # Verify user is the seller
    if order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only seller can confirm delivery")
    
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
    """Manual delivery confirmation (buyer)."""
    order_service = OrderService(db)
    escrow_service = EscrowService(db)
    
    order = await order_service.get_order(order_reference)
    
    # Verify user is the buyer
    if order.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only buyer can confirm delivery")
    
    # Manually confirm delivery
    await order_service.confirm_delivery_manually(order.id)
    
    # Release funds
    await escrow_service.release_funds_to_seller(order.id)
    
    return {"message": "Delivery confirmed successfully"}