from app.models.transaction import TransactionStatus, TransactionType
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
