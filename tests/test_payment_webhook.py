import hashlib
import hmac

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
