import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_admin
from app.main import app
from app.models.dispute import Dispute, DisputeStatus, DisputeType
from app.models.order import DeliveryMethod, Order, OrderStatus
from app.models.user import User, UserRole, UserStatus


@pytest.mark.asyncio
async def test_admin_dispute_queue_returns_real_dispute_data(db_session):
    admin = User(
        phone_number="0240000099",
        hashed_password="hash",
        full_name="Admin",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    payer = User(
        phone_number="0241234000",
        hashed_password="hash",
        full_name="Payer",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    recipient = User(
        phone_number="0247654000",
        hashed_password="hash",
        full_name="Recipient",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add_all([admin, payer, recipient])
    await db_session.commit()

    order = Order(
        order_reference="AVOK-ADMIN-Q",
        buyer_id=payer.id,
        seller_id=recipient.id,
        product_name="Machine",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        escrow_status=OrderStatus.DISPUTED,
        delivery_method=DeliveryMethod.SHIPPING,
    )
    db_session.add(order)
    await db_session.commit()

    dispute = Dispute(
        dispute_reference="DSP-ADMINQ",
        order_id=order.id,
        buyer_id=payer.id,
        seller_id=recipient.id,
        dispute_type=DisputeType.DAMAGED_ITEM,
        description="The item arrived damaged and needs review.",
        status=DisputeStatus.PENDING,
        evidence_urls=["https://example.com/evidence-1.jpg"],
    )
    db_session.add(dispute)
    await db_session.commit()

    async def override_get_current_admin():
        return admin

    app.dependency_overrides[get_current_admin] = override_get_current_admin
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/admin/disputes/queue")
    finally:
        app.dependency_overrides.pop(get_current_admin, None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["dispute_reference"] == "DSP-ADMINQ"
    assert payload[0]["session_reference"] == "AVOK-ADMIN-Q"
    assert payload[0]["evidence_count"] == 1
    assert payload[0]["evidence_urls"] == ["https://example.com/evidence-1.jpg"]
