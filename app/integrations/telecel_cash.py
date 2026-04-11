"""
Telecel Cash Collection API (request-to-pay).

Telecel Cash (formerly Vodafone Cash) API integration for Ghana.
Note: Telecel does not have a public sandbox API.
Contact Telecel Business for API credentials and documentation.

Docs: https://www.telecelghana.com.gh/business/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def ghana_phone_to_telecel_msisdn(phone: str) -> str:
    """Normalize Ghana local (0XXXXXXXXX) to international MSISDN."""
    p = phone.strip().replace(" ", "")
    if p.startswith("0") and len(p) == 10:
        return "233" + p[1:]
    if p.startswith("+233"):
        return p[1:]
    return p


async def telecel_request_to_pay(
    *,
    base_url: str,
    api_key: str,
    api_secret: str,
    amount: float,
    phone_number: str,
    reference: str,
    description: str = "Avok escrow payment",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Request payment from a Telecel Cash user.
    
    Telecel Cash API typically uses:
    POST /api/v1/collections/request
    Headers: Authorization: Bearer {token}, Content-Type: application/json
    Body: { amount, msisdn, reference, description }
    """
    msisdn = ghana_phone_to_telecel_msisdn(phone_number)
    amount_str = f"{amount:.2f}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Step 1: Get access token
            token_response = await client.post(
                f"{base_url}/api/v1/auth/token",
                json={
                    "api_key": api_key,
                    "api_secret": api_secret,
                },
            )
            if not token_response.is_success:
                return {
                    "status": "error",
                    "error_detail": f"Token failed: {token_response.text}",
                    "instructions": "Telecel authentication failed.",
                    "provider": "telecel_cash",
                }

            access_token = token_response.json().get("access_token")

            # Step 2: Request payment
            response = await client.post(
                f"{base_url}/api/v1/collections/request",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "amount": amount_str,
                    "msisdn": msisdn,
                    "reference": reference,
                    "description": description,
                },
            )

            if response.status_code in (200, 201, 202):
                data = response.json()
                return {
                    "status": "accepted",
                    "telecel_reference_id": data.get("transaction_id", reference),
                    "instructions": "Approve the Telecel Cash prompt on your phone to complete payment.",
                    "provider": "telecel_cash",
                }

            return {
                "status": "error",
                "http_status": response.status_code,
                "error_detail": response.text[:500],
                "instructions": f"Telecel Cash request failed (HTTP {response.status_code}).",
                "provider": "telecel_cash",
            }

    except Exception as e:
        logger.exception("Telecel Cash collection error for ref %s", reference)
        return {
            "status": "error",
            "instructions": "Telecel Cash request could not be started. Try again or pay via another method.",
            "provider": "telecel_cash",
        }


async def try_telecel_cash_checkout(
    *,
    transaction_reference: str,
    amount: float,
    phone_number: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    api_secret: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    If Telecel credentials are complete, call live API. Otherwise return None (use stub).
    """
    if not all([base_url, api_key, api_secret, phone_number]):
        return None

    return await telecel_request_to_pay(
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret,
        amount=amount,
        phone_number=phone_number,
        reference=transaction_reference,
    )


async def telecel_disbursement(
    *,
    base_url: str,
    api_key: str,
    api_secret: str,
    amount: float,
    phone_number: str,
    reference: str,
    description: str = "Avok payout",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Send money to a Telecel Cash user (disbursement/payout).
    
    Telecel Cash Disbursement API typically uses:
    POST /api/v1/disbursements/send
    """
    msisdn = ghana_phone_to_telecel_msisdn(phone_number)
    amount_str = f"{amount:.2f}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Step 1: Get access token
            token_response = await client.post(
                f"{base_url}/api/v1/auth/token",
                json={
                    "api_key": api_key,
                    "api_secret": api_secret,
                },
            )
            if not token_response.is_success:
                return {
                    "status": "error",
                    "error_detail": f"Token failed: {token_response.text}",
                    "instructions": "Telecel authentication failed.",
                    "provider": "telecel_cash_disbursement",
                }

            access_token = token_response.json().get("access_token")

            # Step 2: Send disbursement
            response = await client.post(
                f"{base_url}/api/v1/disbursements/send",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "amount": amount_str,
                    "msisdn": msisdn,
                    "reference": reference,
                    "description": description,
                },
            )

            if response.status_code in (200, 201, 202):
                data = response.json()
                return {
                    "status": "accepted",
                    "telecel_reference_id": data.get("transaction_id", reference),
                    "instructions": f"Payout of {amount_str} GHS initiated to {phone_number}.",
                    "provider": "telecel_cash_disbursement",
                }

            return {
                "status": "error",
                "http_status": response.status_code,
                "error_detail": response.text[:500],
                "instructions": f"Telecel Cash payout failed (HTTP {response.status_code}).",
                "provider": "telecel_cash_disbursement",
            }

    except Exception as e:
        logger.exception("Telecel Cash disbursement error for ref %s", reference)
        return {
            "status": "error",
            "instructions": "Telecel Cash payout could not be started. Try again or contact support.",
            "provider": "telecel_cash_disbursement",
        }


async def try_telecel_disbursement(
    *,
    amount: float,
    phone_number: str,
    reference: str,
    base_url: Optional[str],
    api_key: Optional[str],
    api_secret: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    If Telecel credentials are complete, call live disbursement API.
    Otherwise return None (use stub).
    """
    if not all([base_url, api_key, api_secret, phone_number]):
        return None

    return await telecel_disbursement(
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret,
        amount=amount,
        phone_number=phone_number,
        reference=reference,
    )
