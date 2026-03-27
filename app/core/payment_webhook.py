"""Verify payment provider → Avok webhook authenticity."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Mapping, Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

WEBHOOK_SECRET_HEADER = "X-Avok-Webhook-Signature"
LEGACY_SECRET_HEADER = "X-Avok-Webhook-Secret"


def _constant_time_equal(a: str, b: str) -> bool:
    try:
        return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
    except Exception:
        return False


def verify_payment_webhook(
    *,
    raw_body: bytes,
    headers: Mapping[str, str],
    webhook_secret: Optional[str],
    debug: bool,
) -> None:
    """
    Require shared secret header or HMAC-SHA256 of raw body.

    Providers should send either:
    - ``X-Avok-Webhook-Secret: <same value as PAYMENT_WEBHOOK_SECRET>`` (simple shared secret), or
    - ``X-Avok-Webhook-Signature: sha256=<hex>`` where hex = HMAC_SHA256(secret, raw_body).
    """
    if not webhook_secret or not webhook_secret.strip():
        if debug:
            logger.warning(
                "PAYMENT_WEBHOOK_SECRET is unset; accepting payment callback (DEBUG only — never in production)"
            )
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment webhooks are not configured (set PAYMENT_WEBHOOK_SECRET)",
        )

    secret = webhook_secret.strip()

    legacy = headers.get(LEGACY_SECRET_HEADER)
    if legacy and _constant_time_equal(legacy.strip(), secret):
        return

    sig_header = headers.get(WEBHOOK_SECRET_HEADER) or headers.get("X-Hub-Signature-256", "")
    if sig_header.startswith("sha256="):
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if _constant_time_equal(sig_header[7:], expected):
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing webhook credentials",
    )
