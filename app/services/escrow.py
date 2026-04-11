from datetime import datetime, timezone, timedelta
from typing import Optional
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.exceptions import EscrowError, NotFoundError
from app.core.finance import calculate_capped_fee, is_verified_account
from app.models.order import DeliveryMethod, Order, OrderStatus
from app.models.wallet import Wallet, WalletType
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.user import User
from app.core.config import settings
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


class EscrowService:
    """Core escrow logic for holding and releasing funds."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_service = NotificationService(db)

    async def _get_refundable_payment_transaction(self, order_id: int) -> Optional[Transaction]:
        result = await self.db.execute(
            select(Transaction)
            .where(
                Transaction.order_id == order_id,
                Transaction.transaction_type.in_([TransactionType.ESCROW_HOLD, TransactionType.DEPOSIT]),
                Transaction.status == TransactionStatus.COMPLETED,
            )
            .order_by(Transaction.created_at.desc())
        )
        return result.scalars().first()

    def _resolve_refund_destination(
        self,
        order: Order,
        payment_transaction: Optional[Transaction],
    ) -> Optional[dict]:
        if payment_transaction and payment_transaction.extra_data:
            refund_destination = payment_transaction.extra_data.get("refund_destination")
            if refund_destination:
                return refund_destination

        payout_metadata = order.payout_metadata or {}
        refund_destination = payout_metadata.get("refund_destination")
        if refund_destination:
            return refund_destination

        if order.payment_source == "momo" and payment_transaction and payment_transaction.momo_number:
            return {
                "destination_type": "momo",
                "destination_reference": payment_transaction.momo_number,
                "provider": payment_transaction.momo_provider,
                "charge_fee": False,
            }
        if order.payment_source == "bank" and payment_transaction and payment_transaction.extra_data:
            bank_reference = payment_transaction.extra_data.get("bank_reference")
            if bank_reference:
                return {
                    "destination_type": "bank",
                    "destination_reference": bank_reference,
                    "provider": "bank",
                    "charge_fee": False,
                }
        return None

    async def _refund_to_original_source(self, amount: float, destination: dict, reference: str) -> dict:
        from app.services.wallet import WalletService

        wallet_service = WalletService(self.db)
        payout_result = await wallet_service.process_external_payout(
            amount=amount,
            destination_type=destination["destination_type"],
            destination_reference=destination["destination_reference"],
            reference=reference,
            momo_provider=destination.get("provider"),
        )
        if not payout_result.get("success"):
            raise EscrowError(
                payout_result.get("error_message", "Refund to the original payment source could not be started")
            )
        return payout_result
    
    async def hold_funds_in_escrow(
        self,
        order_id: int,
        transaction_reference: str,
        payment_source: str = "verified_account",
        gross_amount: Optional[float] = None,
        fee_amount: Optional[float] = None,
    ) -> Transaction:
        """Hold payer funds in escrow after payment confirmation."""
        order = await self._get_order(order_id)
        
        if order.escrow_status != OrderStatus.PENDING_PAYMENT:
            raise EscrowError(f"Invalid order status: {order.escrow_status}")
        
        buyer_wallet = await self._get_wallet_with_lock(order.buyer_id) if order.buyer_id is not None else None
        gross_amount = gross_amount if gross_amount is not None else order.total_amount
        fee_amount = fee_amount if fee_amount is not None else order.entry_fee
        
        # Fetch existing or create transaction record
        result = await self.db.execute(
            select(Transaction).where(Transaction.reference == transaction_reference)
        )
        transaction = result.scalar_one_or_none()
        
        if transaction:
            transaction.wallet_id = buyer_wallet.id if buyer_wallet else None
            transaction.transaction_type = TransactionType.ESCROW_HOLD
            transaction.status = TransactionStatus.COMPLETED
            transaction.amount = gross_amount
            transaction.fee_amount = fee_amount
            transaction.net_amount = order.product_price
            transaction.description = f"Escrow hold for checkout session {order.order_reference}"
            if not transaction.extra_data:
                transaction.extra_data = {}
            transaction.extra_data["payment_source"] = payment_source
        else:
            transaction = Transaction(
                wallet_id=buyer_wallet.id if buyer_wallet else None,
                order_id=order.id,
                transaction_type=TransactionType.ESCROW_HOLD,
                status=TransactionStatus.COMPLETED,
                amount=gross_amount,
                fee_amount=fee_amount,
                net_amount=order.product_price,
                reference=transaction_reference,
                description=f"Escrow hold for checkout session {order.order_reference}",
                extra_data={"payment_source": payment_source},
            )
            self.db.add(transaction)
        
        # Update wallet balances
        if buyer_wallet:
            buyer_wallet.escrow_balance += gross_amount
        if payment_source == "verified_account":
            if not buyer_wallet:
                raise EscrowError("Verified account funding requires a registered payer wallet")
            if buyer_wallet.available_balance < gross_amount:
                raise EscrowError("Insufficient verified account balance for escrow funding")
            buyer_wallet.available_balance -= gross_amount
        
        # Update order status
        order.escrow_status = OrderStatus.PAYMENT_CONFIRMED
        order.escrow_held_at = datetime.now(timezone.utc)
        order.escrow_release_date = None
        order.payment_source = payment_source
        order.entry_fee = fee_amount
        order.total_amount = gross_amount
        
        await self.db.commit()
        
        logger.info(f"Funds held in escrow for order {order.order_reference}: {order.total_amount} GHS")
        
        # Notification removed to prevent duplicates
        
        return transaction
    
    async def release_funds_to_seller(
        self,
        order_id: int,
        admin_approved: bool = False
    ) -> Transaction:
        """Release funds from escrow to the payout recipient."""
        order = await self._get_order_with_lock(order_id)

        if order.escrow_status == OrderStatus.COMPLETED:
            raise EscrowError("Funds have already been released for this checkout session")
        if order.escrow_status == OrderStatus.REFUNDED:
            raise EscrowError("Cannot release funds for a refunded checkout session")
        releasable_statuses = {OrderStatus.DELIVERED}
        if admin_approved:
            releasable_statuses.add(OrderStatus.DISPUTED)
        if order.escrow_status not in releasable_statuses:
            raise EscrowError(f"Cannot release funds for order in status: {order.escrow_status}")
        if not order.escrow_account_active:
            raise EscrowError("Escrow is already closed for this checkout session")
        
        buyer_wallet = await self._get_wallet_with_lock(order.buyer_id) if order.buyer_id is not None else None
        seller_wallet = await self._get_wallet_with_lock(order.seller_id) if order.seller_id else None

        existing_release = await self.db.execute(
            select(Transaction).where(
                Transaction.order_id == order.id,
                Transaction.transaction_type == TransactionType.ESCROW_RELEASE,
                Transaction.status == TransactionStatus.COMPLETED,
            )
        )
        if existing_release.scalar_one_or_none():
            raise EscrowError("Escrow release already exists for this checkout session")

        if buyer_wallet and buyer_wallet.escrow_balance < order.total_amount:
            raise EscrowError("Escrow balance is insufficient to release these funds")

        release_fee = 0.0
        if order.payout_destination in {"momo", "bank"}:
            release_fee = calculate_capped_fee(
                order.product_price,
                percent=settings.seller_withdrawal_fee_percent,
                cap_amount=settings.external_transfer_fee_cap,
            )

        net_seller_amount = order.product_price - release_fee
        if net_seller_amount < 0:
            raise EscrowError("Release fee cannot exceed the product amount")
        if order.payout_destination == "avok_account" and not seller_wallet:
            raise EscrowError("An Avok payout destination requires a registered recipient wallet")
        
        # Create transaction
        transaction = Transaction(
            wallet_id=seller_wallet.id if seller_wallet else None,
            order_id=order.id,
            transaction_type=TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            amount=order.product_price,
            fee_amount=release_fee,
            net_amount=net_seller_amount,
            reference=f"REL-{order.order_reference}-{uuid.uuid4().hex[:8]}",
            description=f"Escrow release for checkout session {order.order_reference}",
            extra_data={
                "payout_destination": order.payout_destination,
                "payout_reference": order.payout_reference,
                "external_recipient": order.seller_id is None,
            },
        )
        
        self.db.add(transaction)
        
        # Update balances
        if buyer_wallet:
            buyer_wallet.escrow_balance -= order.total_amount

        if seller_wallet and order.payout_destination == "avok_account":
            seller_wallet.available_balance += net_seller_amount
        
        # Update order
        order.escrow_status = OrderStatus.COMPLETED
        order.completed_at = datetime.now(timezone.utc)
        order.release_fee = release_fee
        order.escrow_account_active = False
        order.escrow_closed_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        logger.info(f"Funds released for checkout session {order.order_reference}: {net_seller_amount} GHS")
        
        # Send notifications
        await self.notification_service.send_payment_release(order)
        
        return transaction
    
    async def refund_buyer(
        self,
        order_id: int,
        reason: str,
        admin_action_id: Optional[int] = None
    ) -> Transaction:
        """Refund buyer from escrow (full refund, no fees)."""
        order = await self._get_order_with_lock(order_id)
        
        if order.escrow_status == OrderStatus.COMPLETED:
            raise EscrowError("Cannot refund a checkout session that has already been released")
        if order.escrow_status == OrderStatus.REFUNDED:
            raise EscrowError("This checkout session has already been refunded")
        if order.escrow_status not in [OrderStatus.PAYMENT_CONFIRMED, OrderStatus.DISPUTED]:
            raise EscrowError(f"Cannot refund order in status: {order.escrow_status}")
        if not order.escrow_account_active:
            raise EscrowError("Escrow is already closed for this checkout session")
        
        buyer_wallet = await self._get_wallet_with_lock(order.buyer_id) if order.buyer_id is not None else None
        if buyer_wallet and buyer_wallet.escrow_balance < order.total_amount:
            raise EscrowError("Escrow balance is insufficient to process this refund")

        existing_refund = await self.db.execute(
            select(Transaction).where(
                Transaction.order_id == order.id,
                Transaction.transaction_type == TransactionType.REFUND,
                Transaction.status == TransactionStatus.COMPLETED,
            )
        )
        if existing_refund.scalar_one_or_none():
            raise EscrowError("Refund already exists for this checkout session")

        payment_transaction = await self._get_refundable_payment_transaction(order.id)
        refund_destination = self._resolve_refund_destination(order, payment_transaction)
        refund_extra_data = {
            "reason": reason,
            "payment_source": order.payment_source,
            "refund_destination": refund_destination,
            "charged_fee": False,
            "refund_to_original_source": bool(refund_destination),
        }

        refund_reference = f"REF-{order.order_reference}-{uuid.uuid4().hex[:8]}"
        provider_result = None
        if not buyer_wallet and order.payment_source in {"momo", "bank"}:
            if not refund_destination:
                raise EscrowError("Refund destination for the original payment source is missing")
            provider_result = await self._refund_to_original_source(
                amount=order.total_amount,
                destination=refund_destination,
                reference=refund_reference,
            )
            refund_extra_data["provider_result"] = provider_result
        
        # Create refund transaction
        transaction = Transaction(
            wallet_id=buyer_wallet.id if buyer_wallet else None,
            order_id=order.id,
            transaction_type=TransactionType.REFUND,
            status=TransactionStatus.COMPLETED,
            amount=order.total_amount,
            fee_amount=0,
            net_amount=order.total_amount,
            reference=refund_reference,
            description=f"Refund for checkout session {order.order_reference}: {reason}",
            extra_data=refund_extra_data,
            completed_at=datetime.now(timezone.utc),
        )
        
        self.db.add(transaction)
        
        # Update balances
        if buyer_wallet:
            buyer_wallet.escrow_balance -= order.total_amount
            buyer_wallet.available_balance += order.total_amount
        
        # Update order
        order.escrow_status = OrderStatus.REFUNDED
        order.escrow_account_active = False
        order.escrow_closed_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        logger.info(f"Refund processed for order {order.order_reference}: {order.total_amount} GHS")
        
        # Send notification
        await self.notification_service.send_refund_notification(order, reason)
        
        return transaction
    
    async def confirm_delivery_with_otp(
        self,
        order_id: int,
        otp: str,
        seller_id: int
    ) -> bool:
        """Confirm delivery using OTP."""
        order = await self._get_order_with_lock(order_id)
        
        if order.seller_id != seller_id:
            raise EscrowError("Unauthorized: Only seller can confirm delivery")
        
        if order.escrow_status != OrderStatus.SHIPPED:
            raise EscrowError(f"Cannot confirm delivery for order in status: {order.escrow_status}")
        
        from app.models.otp_delivery import OTPDelivery
        
        result = await self.db.execute(
            select(OTPDelivery).where(OTPDelivery.order_id == order_id)
        )
        otp_record = result.scalar_one_or_none()
        
        if not otp_record or otp_record.otp_code != otp:
            if otp_record:
                otp_record.attempts += 1
                await self.db.commit()
            raise EscrowError("Invalid OTP")
        
        if otp_record.is_expired():
            raise EscrowError("OTP has expired")
        
        otp_record.is_verified = True
        otp_record.verified_at = datetime.now(timezone.utc)
        otp_record.verified_by_id = seller_id
        
        order.escrow_status = OrderStatus.DELIVERED
        order.delivered_at = datetime.now(timezone.utc)
        
        await self.release_funds_to_seller(order.id)
        await self.db.commit()
        
        logger.info(f"Delivery confirmed with OTP for order {order.order_reference}")
        
        return True
    
    async def _get_order(self, order_id: int) -> Order:
        """Get order by ID."""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order", order_id)
        return order
    
    async def _get_order_with_lock(self, order_id: int) -> Order:
        """Get order by ID with row-level lock to prevent race conditions."""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order", order_id)
        return order
    
    async def _get_wallet(self, user_id: int) -> Wallet:
        """Get user's main wallet."""
        result = await self.db.execute(
            select(Wallet).where(
                Wallet.user_id == user_id,
                Wallet.wallet_type == WalletType.MAIN
            )
        )
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise NotFoundError("Wallet", user_id)
        return wallet
    
    async def _get_wallet_with_lock(self, user_id: int) -> Wallet:
        """Get user's main wallet with row-level lock to prevent race conditions."""
        result = await self.db.execute(
            select(Wallet).where(
                Wallet.user_id == user_id,
                Wallet.wallet_type == WalletType.MAIN
            ).with_for_update()
        )
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise NotFoundError("Wallet", user_id)
        return wallet
