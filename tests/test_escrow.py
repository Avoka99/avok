import pytest
from datetime import datetime, timedelta
from sqlalchemy import select

from app.services.escrow import EscrowService
from app.services.order import OrderService
from app.core.exceptions import EscrowError
from app.models.user import User, UserRole, UserStatus
from app.models.order import DeliveryMethod, Order, OrderStatus
from app.models.wallet import Wallet, WalletType


async def _get_wallet(db_session, wallet_id: int) -> Wallet:
    result = await db_session.execute(select(Wallet).where(Wallet.id == wallet_id))
    return result.scalar_one()


async def _get_order(db_session, order_id: int) -> Order:
    result = await db_session.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_create_escrow_order(db_session):
    """Test creating escrow order."""
    # Create users
    buyer = User(
        phone_number="0241234567",
        hashed_password="hashed",
        full_name="Test Buyer",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    seller = User(
        phone_number="0247654321",
        hashed_password="hashed",
        full_name="Test Seller",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add_all([buyer, seller])
    await db_session.commit()
    
    # Create wallets
    buyer_wallet = Wallet(user_id=buyer.id, wallet_type=WalletType.MAIN)
    seller_wallet = Wallet(user_id=seller.id, wallet_type=WalletType.MAIN)
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
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    seller = User(
        phone_number="0247654321",
        hashed_password="hashed",
        full_name="Test Seller",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add_all([buyer, seller])
    await db_session.commit()
    
    wallet = Wallet(
        user_id=buyer.id,
        wallet_type=WalletType.MAIN,
        available_balance=200.0,
        escrow_balance=0.0
    )
    seller_wallet = Wallet(
        user_id=seller.id,
        wallet_type=WalletType.MAIN,
        available_balance=0.0,
        escrow_balance=0.0,
    )
    db_session.add_all([wallet, seller_wallet])
    await db_session.commit()
    
    # Create order
    order = Order(
        order_reference="AVOK-TEST123",
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_name="Test Product",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        escrow_status=OrderStatus.PENDING_PAYMENT,
        delivery_method=DeliveryMethod.PICKUP,
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
    wallet = await _get_wallet(db_session, wallet.id)
    assert wallet.available_balance == 99.0  # 200 - 101
    assert wallet.escrow_balance == 101.0
    
    # Verify order status
    order = await _get_order(db_session, order.id)
    assert order.escrow_status == OrderStatus.PAYMENT_CONFIRMED
    assert order.escrow_release_date is None


@pytest.mark.asyncio
async def test_mark_order_as_shipped_starts_auto_release_countdown(db_session):
    buyer = User(
        phone_number="0241234569",
        hashed_password="hashed",
        full_name="Test Buyer",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    seller = User(
        phone_number="0247654329",
        hashed_password="hashed",
        full_name="Test Seller",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add_all([buyer, seller])
    await db_session.commit()

    order = Order(
        order_reference="AVOK-SHIP123",
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_name="Test Product",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        entry_fee=1.0,
        escrow_status=OrderStatus.PAYMENT_CONFIRMED,
        delivery_method=DeliveryMethod.PICKUP,
    )
    db_session.add(order)
    await db_session.commit()

    order_service = OrderService(db_session)
    shipped_order = await order_service.mark_order_as_shipped(order.id, seller.id, tracking_number="TRACK-1")

    assert shipped_order.escrow_status == OrderStatus.SHIPPED
    assert shipped_order.escrow_release_date is not None
    assert shipped_order.escrow_release_date > datetime.utcnow()


@pytest.mark.asyncio
async def test_release_funds_closes_escrow_and_credits_recipient(db_session):
    buyer = User(
        phone_number="0241234567",
        hashed_password="hashed",
        full_name="Test Buyer",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    seller = User(
        phone_number="0247654321",
        hashed_password="hashed",
        full_name="Test Seller",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add_all([buyer, seller])
    await db_session.commit()

    buyer_wallet = Wallet(user_id=buyer.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=101.0)
    seller_wallet = Wallet(user_id=seller.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=0.0)
    db_session.add_all([buyer_wallet, seller_wallet])
    await db_session.commit()

    order = Order(
        order_reference="AVOK-REL123",
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_name="Test Product",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        entry_fee=1.0,
        escrow_status=OrderStatus.DELIVERED,
        delivery_method=DeliveryMethod.PICKUP,
    )
    db_session.add(order)
    await db_session.commit()

    escrow_service = EscrowService(db_session)
    transaction = await escrow_service.release_funds_to_seller(order.id)

    order = await _get_order(db_session, order.id)
    buyer_wallet = await _get_wallet(db_session, buyer_wallet.id)
    seller_wallet = await _get_wallet(db_session, seller_wallet.id)

    assert transaction.net_amount == 100.0
    assert order.escrow_status == OrderStatus.COMPLETED
    assert order.escrow_account_active is False
    assert order.escrow_closed_at is not None
    assert buyer_wallet.escrow_balance == 0.0
    assert seller_wallet.available_balance == 100.0


@pytest.mark.asyncio
async def test_cannot_release_same_checkout_session_twice(db_session):
    buyer = User(
        phone_number="0241234567",
        hashed_password="hashed",
        full_name="Test Buyer",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    seller = User(
        phone_number="0247654321",
        hashed_password="hashed",
        full_name="Test Seller",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add_all([buyer, seller])
    await db_session.commit()

    buyer_wallet = Wallet(user_id=buyer.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=101.0)
    seller_wallet = Wallet(user_id=seller.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=0.0)
    db_session.add_all([buyer_wallet, seller_wallet])
    await db_session.commit()

    order = Order(
        order_reference="AVOK-REL456",
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_name="Test Product",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        entry_fee=1.0,
        escrow_status=OrderStatus.DELIVERED,
        delivery_method=DeliveryMethod.PICKUP,
    )
    db_session.add(order)
    await db_session.commit()

    escrow_service = EscrowService(db_session)
    await escrow_service.release_funds_to_seller(order.id)

    with pytest.raises(EscrowError):
        await escrow_service.release_funds_to_seller(order.id)


@pytest.mark.asyncio
async def test_cannot_refund_completed_checkout_session(db_session):
    buyer = User(
        phone_number="0241234567",
        hashed_password="hashed",
        full_name="Test Buyer",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add(buyer)
    await db_session.commit()

    buyer_wallet = Wallet(user_id=buyer.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=0.0)
    db_session.add(buyer_wallet)
    await db_session.commit()

    order = Order(
        order_reference="AVOK-REF123",
        buyer_id=buyer.id,
        product_name="Test Product",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        entry_fee=1.0,
        escrow_status=OrderStatus.COMPLETED,
        escrow_account_active=False,
        delivery_method=DeliveryMethod.PICKUP,
    )
    db_session.add(order)
    await db_session.commit()

    escrow_service = EscrowService(db_session)

    with pytest.raises(EscrowError):
        await escrow_service.refund_buyer(order.id, "Already completed")


@pytest.mark.asyncio
async def test_release_to_external_recipient_applies_capped_fee_and_closes_temporary_escrow(db_session):
    buyer = User(
        phone_number="0241234500",
        hashed_password="hashed",
        full_name="Test Buyer",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add(buyer)
    await db_session.commit()

    buyer_wallet = Wallet(
        user_id=buyer.id,
        wallet_type=WalletType.MAIN,
        available_balance=0.0,
        escrow_balance=6030.0,
    )
    db_session.add(buyer_wallet)
    await db_session.commit()

    order = Order(
        order_reference="AVOK-EXTREL",
        buyer_id=buyer.id,
        seller_id=None,
        seller_display_name="Factory Recipient",
        seller_contact="+8613712345678",
        payout_destination="bank",
        payout_reference="6222020202020202",
        payout_bank_name="Bank of China",
        product_name="Industrial Machine",
        product_price=6000.0,
        platform_fee=30.0,
        total_amount=6030.0,
        entry_fee=30.0,
        escrow_status=OrderStatus.DELIVERED,
        delivery_method=DeliveryMethod.SHIPPING,
    )
    db_session.add(order)
    await db_session.commit()

    escrow_service = EscrowService(db_session)
    transaction = await escrow_service.release_funds_to_seller(order.id)

    order = await _get_order(db_session, order.id)
    buyer_wallet = await _get_wallet(db_session, buyer_wallet.id)

    assert transaction.fee_amount == 30.0
    assert transaction.net_amount == 5970.0
    assert transaction.wallet_id is None
    assert transaction.extra_data["external_recipient"] is True
    assert transaction.extra_data["payout_destination"] == "bank"
    assert buyer_wallet.escrow_balance == 0.0
    assert order.escrow_status == OrderStatus.COMPLETED
    assert order.release_fee == 30.0
    assert order.escrow_account_active is False


@pytest.mark.asyncio
async def test_can_auto_release_only_after_shipment_window_starts(db_session):
    buyer = User(
        phone_number="0241234510",
        hashed_password="hashed",
        full_name="Test Buyer",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    seller = User(
        phone_number="0247654330",
        hashed_password="hashed",
        full_name="Test Seller",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add_all([buyer, seller])
    await db_session.commit()

    order = Order(
        order_reference="AVOK-AUTO123",
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_name="Test Product",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        entry_fee=1.0,
        escrow_status=OrderStatus.PAYMENT_CONFIRMED,
        delivery_method=DeliveryMethod.PICKUP,
        escrow_release_date=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(order)
    await db_session.commit()

    order = await _get_order(db_session, order.id)
    assert order.can_auto_release() is False

    order.escrow_status = OrderStatus.SHIPPED
    await db_session.commit()
    order = await _get_order(db_session, order.id)
    assert order.can_auto_release() is True
