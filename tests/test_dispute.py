import pytest

from app.services.dispute import DisputeService
from app.models.dispute import DisputeType


@pytest.mark.asyncio
async def test_create_dispute(db_session):
    """Test creating a dispute."""
    # Setup test data
    buyer = User(phone_number="0241234567", hashed_password="hash", full_name="Buyer")
    seller = User(phone_number="0247654321", hashed_password="hash", full_name="Seller")
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
        escrow_status="payment_confirmed"
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
    assert dispute.status == "pending"
    
    # Verify order status changed
    await db_session.refresh(order)
    assert order.escrow_status == "disputed"