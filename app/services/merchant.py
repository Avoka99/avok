import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.merchant import Merchant
from app.models.merchant_checkout_intent import MerchantCheckoutIntent
from app.schemas.merchant import (
    MerchantCreate,
    MerchantIntentCreate,
    MerchantIntentPayload,
    MerchantIntentResponse,
)
from app.schemas.order import OrderItemCreate


class MerchantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_merchant(self, payload: MerchantCreate) -> Merchant:
        existing = await self.db.execute(select(Merchant).where(Merchant.id == payload.id))
        if existing.scalar_one_or_none():
            raise ValidationError("Merchant with this id already exists")

        merchant = Merchant(
            id=payload.id,
            name=payload.name,
            secret_key=payload.secret_key,
            allowed_return_urls=self._dump_urls(payload.allowed_return_urls),
            allowed_cancel_urls=self._dump_urls(payload.allowed_cancel_urls),
        )
        self.db.add(merchant)
        await self.db.commit()
        await self.db.refresh(merchant)
        return merchant

    async def create_checkout_intent(
        self,
        merchant_id: str,
        signature: str,
        payload: MerchantIntentCreate,
        canonical_payload: Optional[str] = None,
    ) -> MerchantIntentResponse:
        merchant = await self.get_merchant(merchant_id)
        canonical_payload = canonical_payload or self._canonicalize_payload(payload.model_dump(mode="json", exclude_none=True))
        expected_signature = self.sign_payload(merchant.secret_key, canonical_payload)
        if not hmac.compare_digest(expected_signature, signature):
            raise ValidationError("Invalid merchant signature")

        merchant_name = payload.merchant_name or merchant.name
        if merchant_name != merchant.name:
            raise ValidationError("merchant_name must match the configured merchant")

        self._validate_allowed_url(payload.return_url, self._load_urls(merchant.allowed_return_urls), "return_url")
        self._validate_allowed_url(payload.cancel_url, self._load_urls(merchant.allowed_cancel_urls), "cancel_url")

        items_payload = []
        if payload.items:
            items_payload = [item.model_dump(mode="json") for item in payload.items]
            computed_total = round(sum(item.quantity * item.unit_price for item in payload.items), 2)
        else:
            computed_total = round(float(payload.product_price or 0), 2)

        if computed_total < 1.0:
            raise ValidationError("Checkout amount must be at least 1.00 GHS")
        if payload.product_price is not None and abs(round(payload.product_price, 2) - computed_total) > 0.01:
            raise ValidationError("product_price must match the sum of line items")

        intent_reference = f"avok_intent_{secrets.token_urlsafe(18)}"
        expires_at = datetime.utcnow() + timedelta(minutes=payload.expires_in_minutes)
        intent = MerchantCheckoutIntent(
            intent_reference=intent_reference,
            merchant_id=merchant.id,
            seller_id=payload.seller_id,
            seller_display_name=payload.seller_display_name,
            seller_contact=payload.seller_contact,
            payout_destination=payload.payout_destination,
            payout_reference=payload.payout_reference,
            payout_account_name=payload.payout_account_name,
            payout_bank_name=payload.payout_bank_name,
            product_name=payload.product_name,
            product_description=payload.product_description,
            product_price=computed_total,
            items=items_payload,
            delivery_method=payload.delivery_method.value,
            shipping_address=payload.shipping_address,
            product_url=payload.product_url,
            payment_source=payload.payment_source,
            merchant_name=merchant_name,
            return_url=payload.return_url,
            cancel_url=payload.cancel_url,
            extra_data=payload.metadata,
            expires_at=expires_at,
        )
        self.db.add(intent)
        await self.db.commit()

        checkout_url = f"{settings.frontend_base_url.rstrip('/')}/payments?intent={intent_reference}"
        return MerchantIntentResponse(
            intent_reference=intent_reference,
            checkout_url=checkout_url,
            expires_at=expires_at,
        )

    async def get_checkout_intent(self, intent_reference: str) -> MerchantIntentPayload:
        intent = await self._get_intent(intent_reference)
        if intent.expires_at <= datetime.utcnow():
            raise ValidationError("Checkout intent has expired")

        items = [OrderItemCreate.model_validate(item) for item in (intent.items or [])]
        return MerchantIntentPayload(
            intent_reference=intent.intent_reference,
            merchant_id=intent.merchant_id,
            merchant_name=intent.merchant_name,
            seller_id=intent.seller_id,
            seller_display_name=intent.seller_display_name,
            seller_contact=intent.seller_contact,
            payout_destination=intent.payout_destination,
            payout_reference=intent.payout_reference,
            payout_account_name=intent.payout_account_name,
            payout_bank_name=intent.payout_bank_name,
            product_name=intent.product_name,
            product_description=intent.product_description,
            product_price=intent.product_price,
            items=items,
            delivery_method=intent.delivery_method,
            shipping_address=intent.shipping_address,
            product_url=intent.product_url,
            payment_source=intent.payment_source,
            return_url=intent.return_url,
            cancel_url=intent.cancel_url,
            expires_at=intent.expires_at,
            metadata=intent.extra_data or {},
        )

    async def resolve_embedded_order_payload(self, merchant_intent_reference: Optional[str], raw_payload: Dict) -> Dict:
        if not merchant_intent_reference:
            return raw_payload

        intent = await self._get_intent(merchant_intent_reference)
        if intent.expires_at <= datetime.utcnow():
            raise ValidationError("Checkout intent has expired")

        items = intent.items or []
        return {
            **raw_payload,
            "recipient_id": intent.seller_id,
            "recipient_display_name": intent.seller_display_name,
            "recipient_contact": intent.seller_contact,
            "payout_destination": intent.payout_destination,
            "payout_reference": intent.payout_reference,
            "payout_account_name": intent.payout_account_name,
            "payout_bank_name": intent.payout_bank_name,
            "product_name": intent.product_name,
            "product_description": intent.product_description,
            "product_price": intent.product_price,
            "items": items,
            "delivery_method": intent.delivery_method,
            "shipping_address": raw_payload.get("shipping_address") or intent.shipping_address,
            "product_url": intent.product_url,
            "payment_source": raw_payload.get("payment_source") or intent.payment_source,
            "auto_import_product_details": False,
            "checkout_context": {
                **(raw_payload.get("checkout_context") or {}),
                "merchant_name": intent.merchant_name,
                "return_url": intent.return_url,
                "cancel_url": intent.cancel_url,
                "merchant_id": intent.merchant_id,
                "merchant_intent_reference": intent.intent_reference,
                "embedded_checkout": True,
                "intent_metadata": intent.extra_data or {},
            },
        }

    async def get_merchant(self, merchant_id: str) -> Merchant:
        result = await self.db.execute(select(Merchant).where(Merchant.id == merchant_id, Merchant.is_active == True))
        merchant = result.scalar_one_or_none()
        if not merchant:
            raise NotFoundError("Merchant", merchant_id)
        return merchant

    async def _get_intent(self, intent_reference: str) -> MerchantCheckoutIntent:
        result = await self.db.execute(
            select(MerchantCheckoutIntent).where(MerchantCheckoutIntent.intent_reference == intent_reference)
        )
        intent = result.scalar_one_or_none()
        if not intent:
            raise NotFoundError("Checkout intent", intent_reference)
        return intent

    @staticmethod
    def sign_payload(secret_key: str, canonical_payload: str) -> str:
        digest = hmac.new(secret_key.encode("utf-8"), canonical_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    @staticmethod
    def _canonicalize_payload(payload: Dict) -> str:
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _dump_urls(urls):
        return json.dumps(urls or [])

    @staticmethod
    def _load_urls(raw: Optional[str]):
        if not raw:
            return []
        return json.loads(raw)

    def _validate_allowed_url(self, value: Optional[str], allowed_urls, field_name: str) -> None:
        if not value:
            return
        if not allowed_urls:
            raise ValidationError(f"{field_name} is not allowed for this merchant")

        parsed_value = urlparse(value)
        normalized_value = f"{parsed_value.scheme}://{parsed_value.netloc}{parsed_value.path}"
        normalized_allowed = {
            f"{urlparse(allowed).scheme}://{urlparse(allowed).netloc}{urlparse(allowed).path}" for allowed in allowed_urls
        }
        if normalized_value not in normalized_allowed:
            raise ValidationError(f"{field_name} is not allowed for this merchant")
