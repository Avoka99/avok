"""
Direct Bank Collection API (receiving payments from bank accounts).

Direct integration with Ghana's banking infrastructure:
1. GhIPSS Instant Pay (GIP) - Real-time interbank transfers
2. Sponsor Bank API - Direct bank partnership for collections
3. RTGS - Real-Time Gross Settlement for large amounts

For production, Avok partners with a sponsor bank (e.g., GCB, Ecobank, Fidelity)
to receive payments directly without intermediaries like Paystack/Flutterwave.

GhIPSS Docs: https://ghipss.net/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


async def ghipss_instant_pay_collection(
    *,
    amount: float,
    account_number: str,
    bank_code: str,
    reference: str,
    customer_name: str,
    sponsor_bank_api_url: str,
    sponsor_bank_api_key: str,
    sponsor_bank_api_secret: str,
    currency: str = "GHS",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Collect payment via GhIPSS Instant Pay through sponsor bank.
    
    This is the standard way banks in Ghana receive real-time payments.
    The sponsor bank initiates a GIP request to the customer's bank.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Step 1: Authenticate with sponsor bank
            token_response = await client.post(
                f"{sponsor_bank_api_url}/api/v1/auth/token",
                json={
                    "api_key": sponsor_bank_api_key,
                    "api_secret": sponsor_bank_api_secret,
                },
            )
            if not token_response.is_success:
                return {
                    "status": "error",
                    "error_detail": f"Bank authentication failed: {token_response.text}",
                    "instructions": "Bank authentication failed. Contact support.",
                    "provider": "ghipss_direct",
                }

            access_token = token_response.json().get("access_token")

            # Step 2: Initiate GhIPSS Instant Pay collection
            response = await client.post(
                f"{sponsor_bank_api_url}/api/v1/ghipss/collect",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Request-ID": reference,
                },
                json={
                    "amount": f"{amount:.2f}",
                    "currency": currency,
                    "reference": reference,
                    "customer": {
                        "name": customer_name,
                        "account_number": account_number,
                        "bank_code": bank_code,
                    },
                    "narration": f"Avok escrow payment - {reference}",
                    "callback_url": f"{sponsor_bank_api_url}/api/v1/webhooks/ghipss",
                },
            )

            if response.status_code in (200, 201, 202):
                data = response.json().get("data", {})
                return {
                    "status": "accepted",
                    "ghipss_reference": data.get("transaction_id", reference),
                    "instructions": f"Bank collection of {amount:.2f} {currency} initiated. Funds will be credited to Avok account within 30 seconds via GhIPSS Instant Pay.",
                    "provider": "ghipss_direct",
                }

            return {
                "status": "error",
                "http_status": response.status_code,
                "error_detail": response.text[:500],
                "instructions": f"Bank collection failed (HTTP {response.status_code}).",
                "provider": "ghipss_direct",
            }

    except Exception as e:
        logger.exception("GhIPSS collection error for ref %s", reference)
        return {
            "status": "error",
            "instructions": "Bank collection could not be started. Try again or pay via another method.",
            "provider": "ghipss_direct",
        }


async def sponsor_bank_virtual_account_collection(
    *,
    amount: float,
    reference: str,
    customer_email: str,
    sponsor_bank_api_url: str,
    sponsor_bank_api_key: str,
    sponsor_bank_api_secret: str,
    avok_virtual_account: str,
    currency: str = "GHS",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Generate a unique virtual account number for the customer to pay into.
    
    The sponsor bank creates a temporary virtual account linked to Avok's
    master account. When the customer pays into it, the bank notifies Avok
    and credits the master account.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            token_response = await client.post(
                f"{sponsor_bank_api_url}/api/v1/auth/token",
                json={
                    "api_key": sponsor_bank_api_key,
                    "api_secret": sponsor_bank_api_secret,
                },
            )
            if not token_response.is_success:
                return {
                    "status": "error",
                    "error_detail": f"Bank authentication failed: {token_response.text}",
                    "instructions": "Bank authentication failed.",
                    "provider": "virtual_account_direct",
                }

            access_token = token_response.json().get("access_token")

            response = await client.post(
                f"{sponsor_bank_api_url}/api/v1/virtual-accounts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "master_account": avok_virtual_account,
                    "reference": reference,
                    "amount": f"{amount:.2f}",
                    "currency": currency,
                    "customer_email": customer_email,
                    "narration": f"Avok escrow - {reference}",
                    "expires_in_minutes": 60,
                },
            )

            if response.is_success:
                data = response.json().get("data", {})
                virtual_account = data.get("account_number")
                bank_name = data.get("bank_name", "Avok Sponsor Bank")
                
                return {
                    "status": "accepted",
                    "virtual_account": virtual_account,
                    "bank_name": bank_name,
                    "reference": reference,
                    "instructions": (
                        f"Transfer {amount:.2f} {currency} to:\n"
                        f"Bank: {bank_name}\n"
                        f"Account: {virtual_account}\n"
                        f"Name: Avok Escrow\n"
                        f"Reference: {reference}"
                    ),
                    "provider": "virtual_account_direct",
                }

            return {
                "status": "error",
                "http_status": response.status_code,
                "error_detail": response.text[:500],
                "instructions": f"Virtual account creation failed (HTTP {response.status_code}).",
                "provider": "virtual_account_direct",
            }

    except Exception as e:
        logger.exception("Virtual account collection error for ref %s", reference)
        return {
            "status": "error",
            "instructions": "Bank payment setup could not be completed. Try again or pay via another method.",
            "provider": "virtual_account_direct",
        }


async def try_bank_collection_payment(
    *,
    transaction_reference: str,
    amount: float,
    email: Optional[str],
    account_number: Optional[str] = None,
    bank_code: Optional[str] = None,
    customer_name: Optional[str] = None,
    sponsor_bank_api_url: Optional[str] = None,
    sponsor_bank_api_key: Optional[str] = None,
    sponsor_bank_api_secret: Optional[str] = None,
    avok_virtual_account: Optional[str] = None,
    collection_method: str = "virtual_account",
    currency: str = "GHS",
) -> Optional[Dict[str, Any]]:
    """
    Collect bank payment via direct bank integration.
    
    Two methods:
    1. "ghipss" - Pull payment from customer's bank account via GhIPSS
    2. "virtual_account" - Generate virtual account for customer to push payment
    
    Returns None if credentials not configured.
    """
    if not all([sponsor_bank_api_url, sponsor_bank_api_key, sponsor_bank_api_secret]):
        return None

    if collection_method == "ghipss" and account_number and bank_code:
        return await ghipss_instant_pay_collection(
            amount=amount,
            account_number=account_number,
            bank_code=bank_code,
            reference=transaction_reference,
            customer_name=customer_name or email or "Avok Customer",
            sponsor_bank_api_url=sponsor_bank_api_url,
            sponsor_bank_api_key=sponsor_bank_api_key,
            sponsor_bank_api_secret=sponsor_bank_api_secret,
            currency=currency,
        )
    
    # Default: virtual account method (customer pushes payment)
    if avok_virtual_account:
        return await sponsor_bank_virtual_account_collection(
            amount=amount,
            reference=transaction_reference,
            customer_email=email or "",
            sponsor_bank_api_url=sponsor_bank_api_url,
            sponsor_bank_api_key=sponsor_bank_api_key,
            sponsor_bank_api_secret=sponsor_bank_api_secret,
            avok_virtual_account=avok_virtual_account,
            currency=currency,
        )

    return None
