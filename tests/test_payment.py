import pytest

from app.core.finance import get_payment_security_requirements
from app.main import app
from app.api.dependencies import get_current_admin
from app.models.user import UserRole
from app.models.user import KYCStatus, User, UserStatus
from app.models.transaction import TransactionStatus, TransactionType
from app.models.order import Order, OrderStatus, DeliveryMethod
from app.services.merchant import MerchantService
from app.services.order import OrderService
from app.services.payment import PaymentService
from app.schemas.order import GuestCheckoutCreate
from app.schemas.payment import MobileMoneyProvider, PaymentInitiate


def test_transaction_enums_are_defined():
    assert TransactionType.DEPOSIT.value == "deposit"
    assert TransactionStatus.PENDING.value == "pending"


def test_payment_initiate_accepts_session_reference_alias():
    payload = PaymentInitiate(
        session_reference="AVOK-SESSION-123",
        funding_source="momo",
        payout_destination="bank",
        momo_provider=MobileMoneyProvider.TELECEL,
        momo_number="0241234567",
    )

    assert payload.session_reference == "AVOK-SESSION-123"
    assert payload.momo_provider == MobileMoneyProvider.TELECEL


def test_payment_initiate_accepts_legacy_order_reference_alias():
    payload = PaymentInitiate(
        order_reference="AVOK-ORDER-123",
        funding_source="verified_account",
        payout_destination="verified_account",
    )

    assert payload.session_reference == "AVOK-ORDER-123"


def test_guest_checkout_schema_accepts_temporary_payer_details():
    payload = GuestCheckoutCreate(
        guest_phone_number="0241234567",
        guest_full_name="Guest Payer",
        recipient_display_name="External Recipient",
        payout_destination="momo",
        payout_reference="0247654321",
        product_name="Industrial machine",
        product_price=4200,
        delivery_method="pickup",
    )

    assert payload.guest_phone_number == "0241234567"
    assert payload.recipient_display_name == "External Recipient"


def test_low_risk_external_payment_stays_fast():
    requirements = get_payment_security_requirements(250, "momo", is_guest=True)

    assert requirements["tier"] == "low"
    assert requirements["can_proceed"] is True
    assert requirements["requires_kyc"] is False


def test_medium_risk_external_payment_requires_phone_for_registered_users():
    user = User(
        phone_number="0241234567",
        hashed_password="hash",
        full_name="Buyer",
        status=UserStatus.ACTIVE,
        is_phone_verified=False,
        kyc_status=KYCStatus.NOT_SUBMITTED,
    )

    requirements = get_payment_security_requirements(1500, "momo", user=user, is_guest=False)

    assert requirements["tier"] == "medium_registered"
    assert requirements["requires_phone_verification"] is True
    assert requirements["can_proceed"] is False


def test_high_risk_guest_payment_requires_registration():
    requirements = get_payment_security_requirements(4500, "bank", is_guest=True)

    assert requirements["tier"] == "high_guest"
    assert requirements["can_proceed"] is True
    assert requirements["requires_kyc"] is False


def test_merchant_intent_signature_helpers_are_consistent():
    payload = {
        "product_price": 4200,
        "merchant_name": "Secure Merchant",
        "items": [{"item_name": "Machine", "quantity": 1, "unit_price": 4200}],
    }

    canonical_payload = MerchantService._canonicalize_payload(payload)
    signature = MerchantService.sign_payload("super-secret-key", canonical_payload)

    assert signature.startswith("sha256=")
    assert signature == MerchantService.sign_payload("super-secret-key", canonical_payload)


def test_signed_embed_intent_can_be_fetched_and_used_for_guest_checkout(client):
    admin = User(
        phone_number="0240000011",
        hashed_password="hash",
        full_name="Admin Merchant Owner",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )

    async def override_get_current_admin():
        return admin

    app.dependency_overrides[get_current_admin] = override_get_current_admin
    try:
        merchant_response = client.post(
            "/api/v1/payments/merchants",
            json={
                "id": "merchant_secure_1",
                "name": "Secure Merchant",
                "secret_key": "super-secret-key-123456",
                "allowed_return_urls": ["https://merchant.example.com/return"],
                "allowed_cancel_urls": ["https://merchant.example.com/cancel"],
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_admin, None)

    assert merchant_response.status_code == 200, merchant_response.text

    intent_payload = {
        "seller_display_name": "Trusted Recipient",
        "seller_contact": "0247000000",
        "payout_destination": "momo",
        "payout_reference": "0247000000",
        "product_name": "Trusted Machine",
        "product_description": "Trusted merchant payload",
        "product_price": 4200,
        "items": [{"item_name": "Trusted Machine", "quantity": 1, "unit_price": 4200}],
        "delivery_method": "pickup",
        "payment_source": "momo",
        "merchant_name": "Secure Merchant",
        "return_url": "https://merchant.example.com/return",
        "cancel_url": "https://merchant.example.com/cancel",
        "metadata": {"cart_id": "CART-1"},
    }
    signature = MerchantService.sign_payload(
        "super-secret-key-123456",
        MerchantService._canonicalize_payload(intent_payload),
    )

    intent_response = client.post(
        "/api/v1/payments/embed/intents",
        headers={
            "X-Avok-Merchant-Id": "merchant_secure_1",
            "X-Avok-Signature": signature,
        },
        json=intent_payload,
    )
    assert intent_response.status_code == 200, intent_response.text
    intent_data = intent_response.json()
    assert "intent_reference" in intent_data
    assert intent_data["checkout_url"].endswith(f"/payments?intent={intent_data['intent_reference']}")

    fetch_response = client.get(f"/api/v1/payments/embed/intents/{intent_data['intent_reference']}")
    assert fetch_response.status_code == 200, fetch_response.text
    fetched_intent = fetch_response.json()
    assert fetched_intent["merchant_name"] == "Secure Merchant"
    assert fetched_intent["payout_reference"] == "0247000000"

    checkout_response = client.post(
        "/api/v1/checkout/sessions/guest",
        json={
            "guest_phone_number": "0242223333",
            "guest_full_name": "Guest Embedded Payer",
            "guest_email": "guest-embed@example.com",
            "merchant_intent_reference": intent_data["intent_reference"],
            "recipient_display_name": "Spoofed Recipient",
            "recipient_contact": "0249999999",
            "payout_destination": "bank",
            "payout_reference": "9999999999",
            "product_name": "Spoofed Product",
            "product_price": 1,
            "delivery_method": "pickup",
            "payment_source": "momo",
        },
    )

    assert checkout_response.status_code == 200, checkout_response.text
    checkout_payload = checkout_response.json()
    assert checkout_payload["recipient_display_name"] == "Trusted Recipient"
    assert checkout_payload["payout_reference"] == "0247000000"
    assert checkout_payload["product_name"] == "Trusted Machine"
    assert checkout_payload["product_price"] == 4200


@pytest.mark.asyncio
async def test_external_payment_initiation_failure_returns_retryable_failed_status(db_session, monkeypatch):
    buyer = User(
        phone_number="0247000111",
        hashed_password="hash",
        full_name="Buyer",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        is_phone_verified=True,
    )
    db_session.add(buyer)
    await db_session.commit()

    order_service = OrderService(db_session)
    order = await order_service.create_order(
        buyer_id=buyer.id,
        recipient_id=None,
        recipient_display_name="External Recipient",
        recipient_contact="0247000222",
        payout_destination="momo",
        payout_reference="0247000222",
        product_name="Machine",
        product_price=1200.0,
        delivery_method=DeliveryMethod.PICKUP,
        payment_source="momo",
    )

    async def fake_external_payment(*args, **kwargs):
        return {
            "status": "error",
            "instructions": "Provider timeout. Retry payment.",
            "provider": "telecel_cash",
        }

    monkeypatch.setattr(PaymentService, "_initiate_external_payment", fake_external_payment)

    payment_service = PaymentService(db_session)
    result = await payment_service.initiate_payment(
        order_id=order.id,
        funding_source="momo",
        payout_destination="momo",
        buyer=buyer,
        momo_provider="telecel",
        momo_number="0247000111",
    )

    refreshed_order = await order_service.get_order(order.order_reference)
    transaction = await payment_service._get_transaction(result["transaction_reference"])

    assert result["status"] == "failed"
    assert "Retry payment" in result["instructions"]
    assert refreshed_order.escrow_status == OrderStatus.PENDING_PAYMENT
    assert transaction.status == TransactionStatus.FAILED


@pytest.mark.asyncio
async def test_order_fraud_flags_daily_order_velocity(db_session):
    buyer = User(
        phone_number="0247000333",
        hashed_password="hash",
        full_name="Buyer",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add(buyer)
    await db_session.commit()

    for index in range(6):
        db_session.add(
            Order(
                order_reference=f"AVOK-VEL-{index}",
                buyer_id=buyer.id,
                seller_id=None,
                seller_display_name="External Recipient",
                seller_contact="0247111222",
                product_name="Machine",
                product_price=100.0,
                platform_fee=1.0,
                total_amount=101.0,
                escrow_status=OrderStatus.PENDING_PAYMENT,
                delivery_method=DeliveryMethod.PICKUP,
            )
        )
    await db_session.commit()

    order_service = OrderService(db_session)
    order = Order(
        order_reference="AVOK-VEL-CANDIDATE",
        buyer_id=buyer.id,
        seller_id=None,
        seller_display_name="External Recipient",
        seller_contact="0247111222",
        product_name="High value machine",
        product_price=100.0,
        platform_fee=1.0,
        total_amount=101.0,
        escrow_status=OrderStatus.PENDING_PAYMENT,
        delivery_method=DeliveryMethod.PICKUP,
    )
    db_session.add(order)
    await db_session.flush()

    fraud_result = await order_service._check_order_fraud(order)

    assert "daily_order_velocity" in fraud_result["flags"]
