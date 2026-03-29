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
    assert payload["guest_session_id"] > 0
    assert payload["session_reference"] == payload["order_reference"]
    assert payload["recipient_display_name"] == "External Recipient"
    assert payload["is_guest_checkout"] is True
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["guest_payer_phone_number"] == "0241234567"
    assert payload["token_type"] == "bearer"

    notifications_response = client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert notifications_response.status_code == 200, notifications_response.text
    notifications_payload = notifications_response.json()
    assert notifications_payload
    assert any(
        notification["order_reference"] == payload["session_reference"]
        and notification["action_url"].endswith(f"/checkout/{payload['session_reference']}")
        for notification in notifications_payload
    )


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
    detail_payload = detail_response.json()
    assert detail_payload["viewer_role"] == "payer"
    assert detail_payload["can_fund"] is True
    assert detail_payload["can_confirm_delivery"] is False
    assert detail_payload["is_read_only_monitor"] is False

    payment_response = client.post(
        f"/api/v1/checkout/sessions/{payload['session_reference']}/fund",
        headers=headers,
        json={
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


def test_guest_checkout_phone_can_register_later(client):
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

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Guest Payer",
            "phone_number": "0241234567",
            "email": "guest-account@example.com",
            "password": "SecurePass1",
            "wants_avok_account": True,
        },
    )

    assert register_response.status_code == 200, register_response.text


def test_guest_checkout_session_supports_multiple_items(client):
    response = client.post(
        "/api/v1/checkout/sessions/guest",
        json={
            "guest_phone_number": "0248889999",
            "guest_full_name": "Guest Cart Payer",
            "guest_email": "guestcart@example.com",
            "recipient_display_name": "External Recipient",
            "recipient_contact": "0247654321",
            "payout_destination": "momo",
            "payout_reference": "0247654321",
            "items": [
                {
                    "item_name": "Industrial machine",
                    "item_description": "Main machine",
                    "quantity": 1,
                    "unit_price": 4200
                },
                {
                    "item_name": "Replacement parts",
                    "item_description": "Spare parts bundle",
                    "quantity": 2,
                    "unit_price": 150
                }
            ],
            "product_price": 4500,
            "delivery_method": "pickup",
            "payment_source": "momo",
            "merchant_name": "External Merchant",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["product_price"] == 4500
    assert payload["item_count"] == 3
    assert len(payload["items"]) == 2
    assert payload["items"][0]["item_name"] == "Industrial machine"
    assert payload["items"][1]["line_total"] == 300
