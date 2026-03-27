"""
MTN Mobile Money Collection API (request-to-pay).

Configured via env when all credentials are set; otherwise callers should use stub flows.
Docs: https://momodeveloper.mtn.com/ (Collection API — Request to Pay).
"""

from __future__ import annotations

import base64
import logging
import uuid
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def ghana_phone_to_mtn_msisdn(phone: str) -> str:
    """Normalize Ghana local (0XXXXXXXXX) to international MSISDN without +."""
    p = phone.strip().replace(" ", "")
    if p.startswith("0") and len(p) == 10:
        return "233" + p[1:]
    if p.startswith("+233"):
        return p[1:]
    return p


async def mtn_get_access_token(
    *,
    base_url: str,
    subscription_key: str,
    api_user: str,
    api_key: str,
    timeout: float = 30.0,
) -> str:
    base = base_url.rstrip("/")
    url = f"{base}/collection/token/"
    basic = base64.b64encode(f"{api_user}:{api_key}".encode()).decode()
    headers = {
        "Authorization": f"Basic {basic}",
        "Ocp-Apim-Subscription-Key": subscription_key,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=headers)
        r.raise_for_status()
        data = r.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("MTN token response missing access_token")
    return token


async def mtn_request_to_pay(
    *,
    base_url: str,
    subscription_key: str,
    api_user: str,
    api_key: str,
    target_environment: str,
    currency: str,
    external_id: str,
    amount_value: str,
    payer_msisdn: str,
    payer_message: str = "Avok escrow payment",
    payee_note: str = "Escrow funding",
    timeout: float = 45.0,
) -> Dict[str, Any]:
    """
    Create a Request to Pay. Returns dict with ``status`` (``accepted`` | ``error``), reference ids, and instructions.
    """
    reference_id = str(uuid.uuid4())
    token = await mtn_get_access_token(
        base_url=base_url,
        subscription_key=subscription_key,
        api_user=api_user,
        api_key=api_key,
        timeout=timeout,
    )
    base = base_url.rstrip("/")
    url = f"{base}/collection/v1_0/requesttopay"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Reference-Id": reference_id,
        "X-Target-Environment": target_environment,
        "Ocp-Apim-Subscription-Key": subscription_key,
        "Content-Type": "application/json",
    }
    body = {
        "amount": amount_value,
        "currency": currency,
        "externalId": external_id,
        "payer": {"partyIdType": "MSISDN", "partyId": payer_msisdn},
        "payerMessage": payer_message,
        "payeeNote": payee_note,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=headers, json=body)

    if r.status_code in (200, 202):
        return {
            "status": "accepted",
            "mtn_reference_id": reference_id,
            "instructions": "Approve the Mobile Money prompt on your phone to complete payment.",
            "provider": "mtn_momo",
        }

    err_text = r.text[:500] if r.text else ""
    logger.warning("MTN requestToPay failed: %s %s", r.status_code, err_text)
    return {
        "status": "error",
        "http_status": r.status_code,
        "mtn_reference_id": reference_id,
        "error_detail": err_text,
        "instructions": f"MTN could not start the payment (HTTP {r.status_code}). Use support ref {external_id}.",
        "provider": "mtn_momo",
    }


async def try_mtn_momo_checkout(
    *,
    transaction_reference: str,
    amount: float,
    phone_number: Optional[str],
    base_url: Optional[str],
    subscription_key: Optional[str],
    api_user: Optional[str],
    api_key: Optional[str],
    target_environment: str,
    currency: str,
) -> Optional[Dict[str, Any]]:
    """
    If MTN credentials are complete, call live API. Otherwise return None (use stub).
    """
    if not all([base_url, subscription_key, api_user, api_key, phone_number]):
        return None

    msisdn = ghana_phone_to_mtn_msisdn(phone_number)
    # MTN expects string amount; minor units depend on currency — Collection API uses main unit as string for GHS/EUR sandboxes
    amount_str = f"{amount:.2f}"

    try:
        return await mtn_request_to_pay(
            base_url=base_url,
            subscription_key=subscription_key,
            api_user=api_user,
            api_key=api_key,
            target_environment=target_environment,
            currency=currency,
            external_id=transaction_reference,
            amount_value=amount_str,
            payer_msisdn=msisdn,
        )
    except Exception:
        logger.exception("MTN MoMo integration error for ref %s", transaction_reference)
        return {
            "status": "error",
            "instructions": "Mobile Money request could not be started. Try again or pay via bank instructions.",
            "provider": "mtn_momo",
        }
