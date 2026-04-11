"""
Direct Bank Disbursement API (payout to bank accounts).

Direct integration with Ghana's banking infrastructure:
1. GhIPSS Instant Pay (GIP) - Real-time interbank transfers
2. Sponsor Bank API - Direct bank partnership for payouts
3. RTGS - Real-Time Gross Settlement for large amounts

Avok partners with a sponsor bank (e.g., GCB, Ecobank, Fidelity)
to send payouts directly without intermediaries.

GhIPSS Docs: https://ghipss.net/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


async def ghipss_instant_pay_disbursement(
    *,
    amount: float,
    account_number: str,
    bank_code: str,
    reference: str,
    recipient_name: str,
    sponsor_bank_api_url: str,
    sponsor_bank_api_key: str,
    sponsor_bank_api_secret: str,
    avok_settlement_account: str,
    currency: str = "GHS",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Send money to a bank account via GhIPSS Instant Pay through sponsor bank.
    
    Avok's sponsor bank initiates a GIP transfer from Avok's settlement
    account to the recipient's bank account in real-time.
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
                    "provider": "ghipss_direct_disbursement",
                }

            access_token = token_response.json().get("access_token")

            # Step 2: Initiate GhIPSS Instant Pay disbursement
            response = await client.post(
                f"{sponsor_bank_api_url}/api/v1/ghipss/disburse",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Request-ID": reference,
                },
                json={
                    "amount": f"{amount:.2f}",
                    "currency": currency,
                    "reference": reference,
                    "source_account": avok_settlement_account,
                    "recipient": {
                        "name": recipient_name,
                        "account_number": account_number,
                        "bank_code": bank_code,
                    },
                    "narration": f"Avok escrow payout - {reference}",
                    "callback_url": f"{sponsor_bank_api_url}/api/v1/webhooks/ghipss-disbursement",
                },
            )

            if response.status_code in (200, 201, 202):
                data = response.json().get("data", {})
                return {
                    "status": "accepted",
                    "ghipss_reference": data.get("transaction_id", reference),
                    "instructions": f"Bank payout of {amount:.2f} {currency} initiated to {account_number}. Funds should arrive within 30 seconds via GhIPSS Instant Pay.",
                    "provider": "ghipss_direct_disbursement",
                }

            return {
                "status": "error",
                "http_status": response.status_code,
                "error_detail": response.text[:500],
                "instructions": f"Bank payout failed (HTTP {response.status_code}).",
                "provider": "ghipss_direct_disbursement",
            }

    except Exception as e:
        logger.exception("GhIPSS disbursement error for ref %s", reference)
        return {
            "status": "error",
            "instructions": "Bank payout could not be started. Try again or contact support.",
            "provider": "ghipss_direct_disbursement",
        }


async def sponsor_bank_bulk_disbursement(
    *,
    amount: float,
    account_number: str,
    bank_code: str,
    reference: str,
    recipient_name: str,
    sponsor_bank_api_url: str,
    sponsor_bank_api_key: str,
    sponsor_bank_api_secret: str,
    avok_settlement_account: str,
    currency: str = "GHS",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Queue a bank payout for batch processing by the sponsor bank.
    
    Used for non-urgent payouts. The sponsor bank processes these in
    batches (typically every 1-2 hours during business hours).
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
                    "provider": "bank_batch_disbursement",
                }

            access_token = token_response.json().get("access_token")

            response = await client.post(
                f"{sponsor_bank_api_url}/api/v1/bulk-disbursements",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "source_account": avok_settlement_account,
                    "transfers": [
                        {
                            "amount": f"{amount:.2f}",
                            "currency": currency,
                            "reference": reference,
                            "recipient": {
                                "name": recipient_name,
                                "account_number": account_number,
                                "bank_code": bank_code,
                            },
                            "narration": f"Avok escrow payout",
                        }
                    ],
                },
            )

            if response.is_success:
                data = response.json().get("data", {})
                return {
                    "status": "accepted",
                    "batch_reference": data.get("batch_id", reference),
                    "instructions": f"Bank payout of {amount:.2f} {currency} queued for processing. Funds should arrive within 1-2 business hours.",
                    "provider": "bank_batch_disbursement",
                }

            return {
                "status": "error",
                "http_status": response.status_code,
                "error_detail": response.text[:500],
                "instructions": f"Bank payout queuing failed (HTTP {response.status_code}).",
                "provider": "bank_batch_disbursement",
            }

    except Exception as e:
        logger.exception("Bank batch disbursement error for ref %s", reference)
        return {
            "status": "error",
            "instructions": "Bank payout could not be queued. Try again or contact support.",
            "provider": "bank_batch_disbursement",
        }


async def try_bank_disbursement(
    *,
    amount: float,
    account_number: str,
    bank_code: str,
    reference: str,
    recipient_name: str,
    provider: str = "ghipss",
    sponsor_bank_api_url: Optional[str] = None,
    sponsor_bank_api_key: Optional[str] = None,
    sponsor_bank_api_secret: Optional[str] = None,
    avok_settlement_account: Optional[str] = None,
    currency: str = "GHS",
) -> Optional[Dict[str, Any]]:
    """
    Process bank disbursement via direct sponsor bank integration.
    
    Two methods:
    1. "ghipss" - Real-time transfer via GhIPSS Instant Pay
    2. "batch" - Queued for batch processing (slower, cheaper)
    
    Returns None if credentials not configured.
    """
    if not all([sponsor_bank_api_url, sponsor_bank_api_key, sponsor_bank_api_secret, avok_settlement_account]):
        return None

    if provider == "batch":
        return await sponsor_bank_bulk_disbursement(
            amount=amount,
            account_number=account_number,
            bank_code=bank_code,
            reference=reference,
            recipient_name=recipient_name,
            sponsor_bank_api_url=sponsor_bank_api_url,
            sponsor_bank_api_key=sponsor_bank_api_key,
            sponsor_bank_api_secret=sponsor_bank_api_secret,
            avok_settlement_account=avok_settlement_account,
            currency=currency,
        )
    
    # Default: real-time GhIPSS
    return await ghipss_instant_pay_disbursement(
        amount=amount,
        account_number=account_number,
        bank_code=bank_code,
        reference=reference,
        recipient_name=recipient_name,
        sponsor_bank_api_url=sponsor_bank_api_url,
        sponsor_bank_api_key=sponsor_bank_api_key,
        sponsor_bank_api_secret=sponsor_bank_api_secret,
        avok_settlement_account=avok_settlement_account,
        currency=currency,
    )
