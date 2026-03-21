import pytest
from datetime import datetime, timedelta

from app.services.escrow import EscrowService
from app.models.user import User, UserRole
from app.models.order import Order, OrderStatus
from app.models.wallet import Wallet


@pytest.mark.asyncio
async def test_create_escrow_order(db_session):
    """Test creating escrow order."""
    # Create users
    buyer = User(
        phone_number="0241234567",
        hashed_password="hashed",
        full_name="Test Buyer",
        role=UserRole.BUYER
    )
    seller = User(
        phone_number="0247654321",
        hashed_password="hashed",
        full_name="Test Seller",
        role=UserRole.SELLER
    )
    db_session.add_all([buyer, seller])
    await db_session.commit()
    
    # Create wallets
    buyer_wallet = Wallet(user_id=buyer.id, wallet_type="main")
    seller_wallet = Wallet(user_id=seller.id, wallet_type="main")
    db_session.add_all([buyer_wallet, seller_wallet])
    await db_session.commit()
    
    # Test escrow creation
    escrow_service = EscrowService(db_session)
    order = await escrow_service.create_escrow_order(
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_price=100.0,
        order_id=1
    )
    
    assert order.order_reference.startswith("AVOK-")
    assert order.product_price == 100.0
    assert order.platform_fee == 1.0  # 1% fee
    assert order.total_amount == 101.0
    assert order.escrow_status == OrderStatus.PENDING_PAYMENT


@pytest.mark.asyncio
async def test_hold_funds_in_escrow(db_session):
    """Test holding funds in escrow."""
    # Create user with balance
    buyer = User(
        phone_number="0241234567",
        hashed_password="hashed",
        full_name="Test Buyer",
        role=UserRole.BUYER
    )
    db_session.add(buyer)
    await db_session.commit()
    
    wallet = Wallet(
        user_id=buyer.id,
        wallet_type="main",
        available_balance=200.0,
        escrow_balance=0.0
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Create order
    order = Order(
        order_reference="AVOK-TEST123",
        buyer_id=buyer.id,
        seller_id=2,
        product_name="Test Product",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        escrow_status=OrderStatus.PENDING_PAYMENT
    )
    db_session.add(order)
    await db_session.commit()
    
    # Hold funds
    escrow_service = EscrowService(db_session)
    transaction = await escrow_service.hold_funds_in_escrow(
        order.id,
        "PAY-TEST123"
    )
    
    # Verify wallet balances
    await db_session.refresh(wallet)
    assert wallet.available_balance == 99.0  # 200 - 101
    assert wallet.escrow_balance == 101.0
    
    # Verify order status
    await db_session.refresh(order)
    assert order.escrow_status == OrderStatus.PAYMENT_CONFIRMED
    assert order.escrow_release_date is not None
    assert order.escrow_release_date > datetime.utcnow()