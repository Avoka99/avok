import pytest
from sqlalchemy import select

from app.models.admin_action import AdminActionStatus
from app.models.order import DeliveryMethod, Order, OrderStatus
from app.models.wallet import Wallet, WalletType
from app.models.user import User, UserRole, UserStatus
from app.services.dispute import DisputeService
from app.models.dispute import DisputeStatus, DisputeType
from app.schemas.dispute import DisputeCreate
from app.services.fraud_detection import FraudDetectionService


async def _get_order(db_session, order_id: int) -> Order:
    result = await db_session.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one()


async def _get_wallet(db_session, wallet_id: int) -> Wallet:
    result = await db_session.execute(select(Wallet).where(Wallet.id == wallet_id))
    return result.scalar_one()


def test_dispute_schema_accepts_session_reference_alias():
    payload = DisputeCreate(
        session_reference="AVOK-TEST",
        dispute_type=DisputeType.ITEM_NOT_RECEIVED,
        description="Item never arrived after enough time passed."
    )

    assert payload.session_reference == "AVOK-TEST"


@pytest.mark.asyncio
async def test_create_dispute(db_session):
    """Test creating a dispute."""
    # Setup test data
    buyer = User(phone_number="0241234567", hashed_password="hash", full_name="Buyer", role=UserRole.USER, status=UserStatus.ACTIVE)
    seller = User(phone_number="0247654321", hashed_password="hash", full_name="Seller", role=UserRole.USER, status=UserStatus.ACTIVE)
    db_session.add_all([buyer, seller])
    await db_session.commit()
    
    order = Order(
        order_reference="AVOK-TEST",
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_name="Test",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        escrow_status=OrderStatus.PAYMENT_CONFIRMED,
        delivery_method=DeliveryMethod.PICKUP,
    )
    db_session.add(order)
    await db_session.commit()
    
    # Create dispute
    dispute_service = DisputeService(db_session)
    dispute = await dispute_service.create_dispute(
        order_reference="AVOK-TEST",
        buyer_id=buyer.id,
        dispute_type=DisputeType.ITEM_NOT_RECEIVED,
        description="Item never arrived after 2 weeks"
    )
    
    assert dispute.dispute_reference.startswith("DSP-")
    assert dispute.dispute_type == DisputeType.ITEM_NOT_RECEIVED
    assert dispute.status == DisputeStatus.PENDING
    
    # Verify order status changed
    order = await _get_order(db_session, order.id)
    assert order.escrow_status == OrderStatus.DISPUTED


@pytest.mark.asyncio
async def test_dispute_resolution_refunds_payer_after_required_approvals(db_session):
    buyer = User(phone_number="0241234567", hashed_password="hash", full_name="Buyer", role=UserRole.USER, status=UserStatus.ACTIVE)
    seller = User(phone_number="0247654321", hashed_password="hash", full_name="Recipient", role=UserRole.USER, status=UserStatus.ACTIVE)
    admin_one = User(phone_number="0240000001", hashed_password="hash", full_name="Admin One", role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    admin_two = User(phone_number="0240000002", hashed_password="hash", full_name="Admin Two", role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    db_session.add_all([buyer, seller, admin_one, admin_two])
    await db_session.commit()

    buyer_wallet = Wallet(user_id=buyer.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=101.0)
    seller_wallet = Wallet(user_id=seller.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=0.0)
    db_session.add_all([buyer_wallet, seller_wallet])
    await db_session.commit()

    order = Order(
        order_reference="AVOK-DSP-REFUND",
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_name="Machine",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        entry_fee=1.0,
        escrow_status=OrderStatus.PAYMENT_CONFIRMED,
        delivery_method=DeliveryMethod.PICKUP,
    )
    db_session.add(order)
    await db_session.commit()

    dispute_service = DisputeService(db_session)
    dispute = await dispute_service.create_dispute(
        order_reference=order.order_reference,
        buyer_id=buyer.id,
        dispute_type=DisputeType.ITEM_NOT_RECEIVED,
        description="The product was never received and escrow should be refunded."
    )

    admin_action = await dispute_service.resolve_dispute(
        dispute_id=dispute.id,
        admin_id=admin_one.id,
        resolution="payer_wins",
        notes="Evidence supports the payer."
    )

    await dispute_service.approve_dispute_resolution(admin_action.id, admin_one.id)
    assert admin_action.status == AdminActionStatus.PENDING

    await dispute_service.approve_dispute_resolution(admin_action.id, admin_two.id)

    order = await _get_order(db_session, order.id)
    buyer_wallet = await _get_wallet(db_session, buyer_wallet.id)

    assert order.escrow_status == OrderStatus.REFUNDED
    assert dispute.status == DisputeStatus.RESOLVED_BUYER_WINS
    assert admin_action.status == AdminActionStatus.EXECUTED
    assert buyer_wallet.available_balance == 101.0
    assert buyer_wallet.escrow_balance == 0.0


@pytest.mark.asyncio
async def test_dispute_resolution_releases_to_recipient_after_required_approvals(db_session):
    buyer = User(phone_number="0241234567", hashed_password="hash", full_name="Buyer", role=UserRole.USER, status=UserStatus.ACTIVE)
    seller = User(phone_number="0247654321", hashed_password="hash", full_name="Recipient", role=UserRole.USER, status=UserStatus.ACTIVE)
    admin_one = User(phone_number="0240000011", hashed_password="hash", full_name="Admin One", role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    admin_two = User(phone_number="0240000012", hashed_password="hash", full_name="Admin Two", role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    db_session.add_all([buyer, seller, admin_one, admin_two])
    await db_session.commit()

    buyer_wallet = Wallet(user_id=buyer.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=101.0)
    seller_wallet = Wallet(user_id=seller.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=0.0)
    db_session.add_all([buyer_wallet, seller_wallet])
    await db_session.commit()

    order = Order(
        order_reference="AVOK-DSP-RELEASE",
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_name="Machine",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        entry_fee=1.0,
        escrow_status=OrderStatus.PAYMENT_CONFIRMED,
        payout_destination="avok_account",
        delivery_method=DeliveryMethod.PICKUP,
    )
    db_session.add(order)
    await db_session.commit()

    dispute_service = DisputeService(db_session)
    dispute = await dispute_service.create_dispute(
        order_reference=order.order_reference,
        buyer_id=buyer.id,
        dispute_type=DisputeType.OTHER,
        description="Both sides submitted evidence and recipient should be paid."
    )

    admin_action = await dispute_service.resolve_dispute(
        dispute_id=dispute.id,
        admin_id=admin_one.id,
        resolution="recipient_wins",
        notes="Evidence supports the recipient."
    )

    await dispute_service.approve_dispute_resolution(admin_action.id, admin_one.id)
    await dispute_service.approve_dispute_resolution(admin_action.id, admin_two.id)

    order = await _get_order(db_session, order.id)
    buyer_wallet = await _get_wallet(db_session, buyer_wallet.id)
    seller_wallet = await _get_wallet(db_session, seller_wallet.id)

    assert order.escrow_status == OrderStatus.COMPLETED
    assert dispute.status == DisputeStatus.RESOLVED_SELLER_WINS
    assert admin_action.status == AdminActionStatus.EXECUTED
    assert buyer_wallet.escrow_balance == 0.0
    assert seller_wallet.available_balance == 100.0


@pytest.mark.asyncio
async def test_dispute_resolution_accepts_legacy_buyer_wins_alias(db_session):
    buyer = User(phone_number="0241234568", hashed_password="hash", full_name="Buyer", role=UserRole.USER, status=UserStatus.ACTIVE)
    seller = User(phone_number="0247654328", hashed_password="hash", full_name="Recipient", role=UserRole.USER, status=UserStatus.ACTIVE)
    admin_one = User(phone_number="0240000021", hashed_password="hash", full_name="Admin One", role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    admin_two = User(phone_number="0240000022", hashed_password="hash", full_name="Admin Two", role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    db_session.add_all([buyer, seller, admin_one, admin_two])
    await db_session.commit()

    buyer_wallet = Wallet(user_id=buyer.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=101.0)
    seller_wallet = Wallet(user_id=seller.id, wallet_type=WalletType.MAIN, available_balance=0.0, escrow_balance=0.0)
    db_session.add_all([buyer_wallet, seller_wallet])
    await db_session.commit()

    order = Order(
        order_reference="AVOK-DSP-LEGACY-BUYER",
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_name="Machine",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        entry_fee=1.0,
        escrow_status=OrderStatus.PAYMENT_CONFIRMED,
        delivery_method=DeliveryMethod.PICKUP,
    )
    db_session.add(order)
    await db_session.commit()

    dispute_service = DisputeService(db_session)
    dispute = await dispute_service.create_dispute(
        order_reference=order.order_reference,
        buyer_id=buyer.id,
        dispute_type=DisputeType.ITEM_NOT_RECEIVED,
        description="Legacy buyer_wins alias should still refund the payer."
    )

    admin_action = await dispute_service.resolve_dispute(
        dispute_id=dispute.id,
        admin_id=admin_one.id,
        resolution="buyer_wins",
        notes="Backward compatibility path."
    )

    await dispute_service.approve_dispute_resolution(admin_action.id, admin_one.id)
    await dispute_service.approve_dispute_resolution(admin_action.id, admin_two.id)

    order = await _get_order(db_session, order.id)
    buyer_wallet = await _get_wallet(db_session, buyer_wallet.id)

    assert order.escrow_status == OrderStatus.REFUNDED
    assert dispute.status == DisputeStatus.RESOLVED_BUYER_WINS
    assert buyer_wallet.available_balance == 101.0
    assert buyer_wallet.escrow_balance == 0.0


@pytest.mark.asyncio
async def test_external_recipient_dispute_does_not_crash_fraud_analysis(db_session):
    buyer = User(phone_number="0241234999", hashed_password="hash", full_name="Buyer", role=UserRole.USER, status=UserStatus.ACTIVE)
    db_session.add(buyer)
    await db_session.commit()

    order = Order(
        order_reference="AVOK-DSP-EXT",
        buyer_id=buyer.id,
        seller_id=None,
        seller_display_name="External Recipient",
        seller_contact="0247000000",
        product_name="Machine",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        entry_fee=1.0,
        escrow_status=OrderStatus.PAYMENT_CONFIRMED,
        delivery_method=DeliveryMethod.PICKUP,
    )
    db_session.add(order)
    await db_session.commit()

    dispute_service = DisputeService(db_session)
    dispute = await dispute_service.create_dispute(
        order_reference=order.order_reference,
        buyer_id=buyer.id,
        dispute_type=DisputeType.ITEM_NOT_RECEIVED,
        description="External recipient never completed delivery.",
    )

    fraud_service = FraudDetectionService(db_session)
    analysis = await fraud_service.analyze_dispute(dispute)

    assert dispute.seller_id is None
    assert "External recipient dispute" in analysis["flags"]
