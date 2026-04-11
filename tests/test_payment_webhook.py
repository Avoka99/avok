import hashlib
import hmac
import uuid

import pytest
from fastapi import HTTPException

from app.core.payment_webhook import verify_payment_webhook


def test_webhook_rejects_when_no_secret_and_not_debug():
    with pytest.raises(HTTPException) as exc:
        verify_payment_webhook(
            raw_body=b"{}",
            headers={},
            webhook_secret=None,
            debug=False,
        )
    assert exc.value.status_code == 503


def test_webhook_accepts_matching_secret_header():
    verify_payment_webhook(
        raw_body=b'{"x":1}',
        headers={"X-Avok-Webhook-Secret": "s3cr3t"},
        webhook_secret="s3cr3t",
        debug=False,
    )


def test_webhook_rejects_wrong_secret():
    with pytest.raises(HTTPException) as exc:
        verify_payment_webhook(
            raw_body=b"{}",
            headers={"X-Avok-Webhook-Secret": "wrong"},
            webhook_secret="right",
            debug=False,
        )
    assert exc.value.status_code == 401


def test_webhook_accepts_valid_hmac_signature():
    secret = "shared-secret"
    body = b'{"transaction_reference":"PAY-1","momo_transaction_id":"m1","status":"success"}'
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    verify_payment_webhook(
        raw_body=body,
        headers={"X-Avok-Webhook-Signature": f"sha256={sig}"},
        webhook_secret=secret,
        debug=False,
    )


def test_payment_callback_route_rejects_wrong_header(client):
    r = client.post(
        "/api/v1/payments/callback",
        json={
            "transaction_reference": "PAY-fake",
            "momo_transaction_id": "x",
            "status": "success",
        },
        headers={"X-Avok-Webhook-Secret": "not-the-test-secret"},
    )
    assert r.status_code == 401


def test_payment_callback_route_accepts_valid_secret(client):
    r = client.post(
        "/api/v1/payments/callback",
        json={
            "transaction_reference": "PAY-fake",
            "momo_transaction_id": "x",
            "status": "success",
        },
        headers={"X-Avok-Webhook-Secret": "test-webhook-secret"},
    )
    assert r.status_code == 404


def test_payment_callback_route_is_idempotent_for_repeated_provider_retries(client):
    create_response = client.post(
        "/api/v1/checkout/sessions/guest",
        json={
            "guest_phone_number": "0248881111",
            "guest_full_name": "Guest Payer",
            "guest_email": "guest-webhook@example.com",
            "recipient_display_name": "External Recipient",
            "recipient_contact": "0247654321",
            "payout_destination": "momo",
            "payout_reference": "0247654321",
            "product_name": "Industrial machine",
            "product_price": 4200,
            "delivery_method": "pickup",
            "payment_source": "momo",
        },
    )
    assert create_response.status_code == 200, create_response.text
    session_payload = create_response.json()
    auth_headers = {"Authorization": f"Bearer {session_payload['access_token']}"}

    fund_response = client.post(
        f"/api/v1/checkout/sessions/{session_payload['session_reference']}/fund",
        headers=auth_headers,
        json={
            "funding_source": "momo",
            "payout_destination": "momo",
            "momo_provider": "telecel",
            "momo_number": "0248881111",
        },
    )
    assert fund_response.status_code == 200, fund_response.text
    payment_payload = fund_response.json()
    assert payment_payload["status"] == "pending"

    webhook_headers = {
        "X-Avok-Webhook-Secret": "test-webhook-secret",
        "X-Avok-Idempotency-Key": f"callback-{uuid.uuid4().hex}",
    }
    callback_body = {
        "transaction_reference": payment_payload["transaction_reference"],
        "momo_transaction_id": "MOMO-REAL-1",
        "status": "success",
    }

    first_callback = client.post("/api/v1/payments/callback", json=callback_body, headers=webhook_headers)
    assert first_callback.status_code == 200, first_callback.text
    assert first_callback.json()["message"] == "Callback received"

    second_callback = client.post("/api/v1/payments/callback", json=callback_body, headers=webhook_headers)
    assert second_callback.status_code == 200, second_callback.text
    assert second_callback.json()["idempotent"] is True
