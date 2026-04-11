"""
AirtelTigo Money Collection API (request-to-pay).

AirtelTigo Money API integration for Ghana.
Note: AirtelTigo does not have a public sandbox API.
Contact AirtelTigo Business for API credentials and documentation.

Docs: https://www.airteltigo.com.gh/business/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def ghana_phone_to_airteltigo_msisdn(phone: str) -> str:
    """Normalize Ghana local (0XXXXXXXXX) to international MSISDN."""
    p = phone.strip().replace(" ", "")
    if p.startswith("0") and len(p) == 10:
        return "233" + p[1:]
    if p.startswith("+233"):
        return p[1:]
    return p


async def airteltigo_request_to_pay(
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
    Request payment from an AirtelTigo Money user.
    
    AirtelTigo Money API typically uses:
    POST /api/v1/payments/request
    Headers: Authorization: Bearer {token}, Content-Type: application/json
    Body: { amount, msisdn, reference, description }
    """
    msisdn = ghana_phone_to_airteltigo_msisdn(phone_number)
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
                    "instructions": "AirtelTigo authentication failed.",
                    "provider": "airteltigo_money",
                }

            access_token = token_response.json().get("access_token")

            # Step 2: Request payment
            response = await client.post(
                f"{base_url}/api/v1/payments/request",
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
                    "airteltigo_reference_id": data.get("transaction_id", reference),
                    "instructions": "Approve the AirtelTigo Money prompt on your phone to complete payment.",
                    "provider": "airteltigo_money",
                }

            return {
                "status": "error",
                "http_status": response.status_code,
                "error_detail": response.text[:500],
                "instructions": f"AirtelTigo Money request failed (HTTP {response.status_code}).",
                "provider": "airteltigo_money",
            }

    except Exception as e:
        logger.exception("AirtelTigo Money collection error for ref %s", reference)
        return {
            "status": "error",
            "instructions": "AirtelTigo Money request could not be started. Try again or pay via another method.",
            "provider": "airteltigo_money",
        }


async def try_airteltigo_checkout(
    *,
    transaction_reference: str,
    amount: float,
    phone_number: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    api_secret: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    If AirtelTigo credentials are complete, call live API. Otherwise return None (use stub).
    """
    if not all([base_url, api_key, api_secret, phone_number]):
        return None

    return await airteltigo_request_to_pay(
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret,
        amount=amount,
        phone_number=phone_number,
        reference=transaction_reference,
    )


async def airteltigo_disbursement(
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
    Send money to an AirtelTigo Money user (disbursement/payout).
    """
    msisdn = ghana_phone_to_airteltigo_msisdn(phone_number)
    amount_str = f"{amount:.2f}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
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
                    "instructions": "AirtelTigo authentication failed.",
                    "provider": "airteltigo_money_disbursement",
                }

            access_token = token_response.json().get("access_token")

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
                    "airteltigo_reference_id": data.get("transaction_id", reference),
                    "instructions": f"Payout of {amount_str} GHS initiated to {phone_number}.",
                    "provider": "airteltigo_money_disbursement",
                }

            return {
                "status": "error",
                "http_status": response.status_code,
                "error_detail": response.text[:500],
                "instructions": f"AirtelTigo Money payout failed (HTTP {response.status_code}).",
                "provider": "airteltigo_money_disbursement",
            }

    except Exception as e:
        logger.exception("AirtelTigo Money disbursement error for ref %s", reference)
        return {
            "status": "error",
            "instructions": "AirtelTigo Money payout could not be started. Try again or contact support.",
            "provider": "airteltigo_money_disbursement",
        }


async def try_airteltigo_disbursement(
    *,
    amount: float,
    phone_number: str,
    reference: str,
    base_url: Optional[str],
    api_key: Optional[str],
    api_secret: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    If AirtelTigo credentials are complete, call live disbursement API.
    Otherwise return None (use stub).
    """
    if not all([base_url, api_key, api_secret, phone_number]):
        return None

    return await airteltigo_disbursement(
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret,
        amount=amount,
        phone_number=phone_number,
        reference=reference,
    )
