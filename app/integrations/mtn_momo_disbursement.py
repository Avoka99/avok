"""
MTN Mobile Money Disbursement API (payout to users).

Configured via env when all credentials are set; otherwise callers should use stub flows.
Docs: https://momodeveloper.mtn.com/ (Disbursement API — Transfer).
"""

from __future__ import annotations

import base64
import logging
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


async def mtn_disbursement_get_access_token(
    *,
    base_url: str,
    subscription_key: str,
    api_user: str,
    api_key: str,
    timeout: float = 30.0,
) -> str:
    """Get OAuth2 access token for MTN Disbursement API."""
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
        raise RuntimeError("MTN disbursement token response missing access_token")
    return token


async def mtn_disbursement_transfer(
    *,
    base_url: str,
    subscription_key: str,
    api_user: str,
    api_key: str,
    target_environment: str,
    currency: str,
    reference_id: str,
    external_id: str,
    amount_value: str,
    payee_msisdn: str,
    payer_message: str = "Avok payout",
    payee_note: str = "Funds from Avok escrow",
    timeout: float = 45.0,
) -> Dict[str, Any]:
    """
    Create a Disbursement Transfer. Returns dict with status and reference.
    """
    token = await mtn_disbursement_get_access_token(
        base_url=base_url,
        subscription_key=subscription_key,
        api_user=api_user,
        api_key=api_key,
        timeout=timeout,
    )
    base = base_url.rstrip("/")
    url = f"{base}/disbursement/v1_0/transfer/{reference_id}"
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
        "payee": {"partyIdType": "MSISDN", "partyId": payee_msisdn},
        "payerMessage": payer_message,
        "payeeNote": payee_note,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=headers, json=body)

    if r.status_code in (200, 201, 202):
        return {
            "status": "accepted",
            "mtn_reference_id": reference_id,
            "instructions": "Payout initiated. Funds should arrive shortly.",
            "provider": "mtn_momo_disbursement",
        }

    err_text = r.text[:500] if r.text else ""
    logger.warning("MTN disbursement failed: %s %s", r.status_code, err_text)
    return {
        "status": "error",
        "http_status": r.status_code,
        "mtn_reference_id": reference_id,
        "error_detail": err_text,
        "instructions": f"MTN disbursement failed (HTTP {r.status_code}). Reference: {reference_id}.",
        "provider": "mtn_momo_disbursement",
    }


async def mtn_disbursement_check_status(
    *,
    base_url: str,
    subscription_key: str,
    api_user: str,
    api_key: str,
    target_environment: str,
    reference_id: str,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Check the status of a disbursement transfer."""
    token = await mtn_disbursement_get_access_token(
        base_url=base_url,
        subscription_key=subscription_key,
        api_user=api_user,
        api_key=api_key,
        timeout=timeout,
    )
    base = base_url.rstrip("/")
    url = f"{base}/disbursement/v1_0/transfer/{reference_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Target-Environment": target_environment,
        "Ocp-Apim-Subscription-Key": subscription_key,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url, headers=headers)

    if r.is_success:
        return {
            "status": "success",
            "data": r.json(),
            "provider": "mtn_momo_disbursement",
        }

    return {
        "status": "error",
        "http_status": r.status_code,
        "error_detail": r.text[:500] if r.text else "",
        "provider": "mtn_momo_disbursement",
    }


async def try_mtn_momo_disbursement(
    *,
    amount: float,
    phone_number: str,
    reference: str,
    base_url: Optional[str],
    subscription_key: Optional[str],
    api_user: Optional[str],
    api_key: Optional[str],
    target_environment: str = "sandbox",
    currency: str = "GHS",
) -> Optional[Dict[str, Any]]:
    """
    If MTN disbursement credentials are complete, call live API.
    Otherwise return None (use stub).
    """
    if not all([base_url, subscription_key, api_user, api_key]):
        return None

    msisdn = ghana_phone_to_mtn_msisdn(phone_number)
    amount_str = f"{amount:.2f}"

    try:
        return await mtn_disbursement_transfer(
            base_url=base_url,
            subscription_key=subscription_key,
            api_user=api_user,
            api_key=api_key,
            target_environment=target_environment,
            currency=currency,
            reference_id=reference,
            external_id=reference,
            amount_value=amount_str,
            payee_msisdn=msisdn,
        )
    except Exception:
        logger.exception("MTN MoMo disbursement error for ref %s", reference)
        return {
            "status": "error",
            "instructions": "Disbursement could not be started. Try again or contact support.",
            "provider": "mtn_momo_disbursement",
        }
