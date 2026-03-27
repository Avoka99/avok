def test_guest_checkout_session_creation_returns_tokens(client):
    response = client.post(
        "/api/v1/checkout/sessions/guest",
        json={
            "guest_phone_number": "0241234567",
            "guest_full_name": "Guest Payer",
            "guest_email": "guest@example.com",
            "recipient_display_name": "External Recipient",
            "recipient_contact": "0247654321",
            "payout_destination": "momo",
            "payout_reference": "0247654321",
            "product_name": "Industrial machine",
            "product_description": "Factory machine payment protected by escrow.",
            "product_price": 4200,
            "delivery_method": "pickup",
            "payment_source": "momo",
            "merchant_name": "External Merchant",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["guest_user_id"] > 0
    assert payload["session_reference"] == payload["order_reference"]
    assert payload["recipient_display_name"] == "External Recipient"
    assert payload["is_guest_checkout"] is True
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["token_type"] == "bearer"


def test_guest_checkout_session_can_be_funded_with_temporary_token(client):
    create_response = client.post(
        "/api/v1/checkout/sessions/guest",
        json={
            "guest_phone_number": "0241234567",
            "guest_full_name": "Guest Payer",
            "guest_email": "guest@example.com",
            "recipient_display_name": "External Recipient",
            "recipient_contact": "0247654321",
            "payout_destination": "momo",
            "payout_reference": "0247654321",
            "product_name": "Industrial machine",
            "product_description": "Factory machine payment protected by escrow.",
            "product_price": 4200,
            "delivery_method": "pickup",
            "payment_source": "momo",
            "merchant_name": "External Merchant",
        },
    )

    assert create_response.status_code == 200, create_response.text
    payload = create_response.json()
    headers = {"Authorization": f"Bearer {payload['access_token']}"}

    detail_response = client.get(f"/api/v1/checkout/sessions/{payload['session_reference']}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text

    payment_response = client.post(
        "/api/v1/payments/initiate",
        headers=headers,
        json={
            "session_reference": payload["session_reference"],
            "funding_source": "momo",
            "payout_destination": "momo",
            "momo_provider": "telecel",
            "momo_number": "0241234567",
        },
    )
    assert payment_response.status_code == 200, payment_response.text
    payment_payload = payment_response.json()
    assert payment_payload["session_reference"] == payload["session_reference"]
    assert payment_payload["status"] == "pending"

    sandbox_response = client.post(
        f"/api/v1/payments/sandbox/{payment_payload['transaction_reference']}/success",
        headers=headers,
    )
    assert sandbox_response.status_code == 200, sandbox_response.text
