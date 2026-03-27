from typing import Optional, Dict
import logging
import uuid
import httpx
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import PaymentError, NotFoundError
from app.core.config import settings
from app.core.finance import calculate_capped_fee, is_verified_account
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.services.escrow import EscrowService
from app.services.notification import NotificationService
from app.integrations.mtn_momo_collection import try_mtn_momo_checkout

logger = logging.getLogger(__name__)


class PaymentService:
    """Handle checkout funding across Avok balance, MoMo, and bank rails."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.escrow_service = EscrowService(db)
        self.notification_service = NotificationService(db)
    
    async def initiate_payment(
        self,
        order_id: int,
        funding_source: str,
        payout_destination: str,
        buyer: User,
        momo_provider: Optional[str] = None,
        momo_number: Optional[str] = None,
        bank_reference: Optional[str] = None,
    ) -> Dict:
        """Initiate payment into escrow from a verified Avok account or external rails."""
        order = await self._get_order(order_id)
        
        if order.escrow_status != OrderStatus.PENDING_PAYMENT:
            raise PaymentError(f"Checkout session {order.order_reference} cannot be funded")
        
        transaction_reference = f"PAY-{order.order_reference}-{uuid.uuid4().hex[:8]}"

        entry_fee = 0.0
        if funding_source != "verified_account":
            entry_fee = calculate_capped_fee(
                order.product_price,
                percent=settings.platform_fee_percent,
                cap_amount=settings.external_transfer_fee_cap,
            )
        elif not is_verified_account(buyer):
            raise PaymentError("Only verified Avok accounts can pay directly from wallet balance")

        release_fee = 0.0
        if payout_destination != "verified_account":
            release_fee = calculate_capped_fee(
                order.product_price,
                percent=settings.seller_withdrawal_fee_percent,
                cap_amount=settings.external_transfer_fee_cap,
            )

        gross_amount = order.product_price + entry_fee

        transaction = Transaction(
            wallet_id=None,
            order_id=order.id,
            transaction_type=TransactionType.DEPOSIT,
            status=TransactionStatus.PENDING if funding_source != "verified_account" else TransactionStatus.COMPLETED,
            amount=gross_amount,
            fee_amount=entry_fee,
            net_amount=order.product_price,
            reference=transaction_reference,
            description=f"Funding for checkout session {order.order_reference}",
            momo_provider=momo_provider,
            momo_number=momo_number,
            extra_data={
                "funding_source": funding_source,
                "payout_destination": payout_destination,
                "bank_reference": bank_reference,
                "release_fee": release_fee,
            },
        )
        
        self.db.add(transaction)
        await self.db.commit()
        
        order.entry_fee = entry_fee
        order.platform_fee = entry_fee
        order.total_amount = gross_amount
        order.release_fee = release_fee
        order.payment_source = funding_source
        order.payout_destination = payout_destination

        payment_result = {}
        if funding_source == "verified_account":
            await self.db.commit()
            await self.escrow_service.hold_funds_in_escrow(
                transaction.order_id,
                transaction_reference,
                payment_source=funding_source,
                gross_amount=gross_amount,
                fee_amount=entry_fee,
            )
            await self.notification_service.send_payment_confirmation(transaction.order_id)
        else:
            await self.db.commit()
            payment_result = await self._initiate_external_payment(
                transaction_reference=transaction_reference,
                amount=gross_amount,
                phone_number=momo_number,
                provider=momo_provider,
                bank_reference=bank_reference,
                source_type=funding_source,
            )
        
        logger.info(f"Payment initiated for checkout session {order.order_reference}: {transaction_reference}")
        
        return {
            "transaction_reference": transaction_reference,
            "order_reference": order.order_reference,
            "session_reference": order.order_reference,
            "amount": gross_amount,
            "platform_fee": entry_fee,
            "entry_fee": entry_fee,
            "release_fee": release_fee,
            "total_amount": gross_amount,
            "funding_source": funding_source,
            "payout_destination": payout_destination,
            "momo_provider": momo_provider,
            "momo_number": momo_number,
            "payment_url": payment_result.get("payment_url"),
            "instructions": payment_result.get("instructions"),
            "status": "completed" if funding_source == "verified_account" else "pending"
        }
    
    async def handle_payment_callback(
        self,
        transaction_reference: str,
        momo_transaction_id: str,
        status: str,
        approval_code: Optional[str] = None
    ) -> Transaction:
        """Handle payment callback from Mobile Money provider."""
        transaction = await self._get_transaction(transaction_reference)
        
        if transaction.status != TransactionStatus.PENDING:
            logger.warning(f"Transaction {transaction_reference} already processed")
            return transaction
        
        if status == "success":
            # Update transaction
            transaction.status = TransactionStatus.COMPLETED
            transaction.momo_transaction_id = momo_transaction_id
            transaction.momo_approval_code = approval_code
            transaction.completed_at = datetime.utcnow()
            
            # Hold funds in escrow
            await self.escrow_service.hold_funds_in_escrow(
                transaction.order_id,
                transaction_reference,
                payment_source=transaction.extra_data.get("funding_source", "momo") if transaction.extra_data else "momo",
                gross_amount=transaction.amount,
                fee_amount=transaction.fee_amount,
            )
            
            # Send confirmation
            await self.notification_service.send_payment_confirmation(transaction.order_id)
            
            logger.info(f"Payment successful for transaction {transaction_reference}")
            
        else:
            transaction.status = TransactionStatus.FAILED
            transaction.momo_transaction_id = momo_transaction_id
            
            # Update order status
            order = await self._get_order(transaction.order_id)
            order.escrow_status = OrderStatus.CANCELLED
            
            await self.notification_service.send_payment_failed(transaction.order_id)
            
            logger.warning(f"Payment failed for transaction {transaction_reference}")
        
        await self.db.commit()
        
        return transaction
    
    async def _initiate_external_payment(
        self,
        transaction_reference: str,
        amount: float,
        phone_number: Optional[str],
        provider: Optional[str],
        bank_reference: Optional[str],
        source_type: str,
    ) -> Dict:
        """
        Initiate Mobile Money payment with provider.
        Abstracted for different providers (MTN, Telecel, AirtelTigo).
        """
        # This is a placeholder for actual Mobile Money integration
        # In production, integrate with provider APIs
        
        if source_type == "bank":
            return {
                "instructions": f"Transfer {amount} GHS from your bank using reference {bank_reference or transaction_reference}"
            }
        if provider == "mtn":
            mtn = await try_mtn_momo_checkout(
                transaction_reference=transaction_reference,
                amount=amount,
                phone_number=phone_number,
                base_url=settings.mtn_momo_base_url,
                subscription_key=settings.mtn_momo_subscription_key,
                api_user=settings.mtn_momo_api_user,
                api_key=settings.mtn_momo_api_key,
                target_environment=settings.mtn_momo_target_environment,
                currency=settings.mtn_momo_currency,
            )
            if mtn is not None:
                return {
                    "payment_url": None,
                    "instructions": mtn.get(
                        "instructions",
                        f"Complete payment of {amount} GHS for {transaction_reference}",
                    ),
                }
            return {
                "payment_url": f"https://momodeveloper.mtn.com/docs/services/collection",
                "instructions": (
                    f"Configure MTN_MOMO_* env vars for live request-to-pay. "
                    f"Dev stub: approve {amount} GHS on your phone when prompted (ref {transaction_reference})."
                ),
            }
        elif provider == "telecel":
            # Telecel Cash API
            return {
                "instructions": f"Dial *110# and enter code {transaction_reference[-6:]} to pay"
            }
        elif provider == "airtel_tigo":
            # AirtelTigo Money API
            return {
                "instructions": f"Check your phone for payment prompt"
            }
        else:
            raise PaymentError(f"Unsupported provider: {provider}")
    
    async def _get_order(self, order_id: int) -> Order:
        """Get order by ID."""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order", order_id)
        return order
    
    async def _get_transaction(self, reference: str) -> Transaction:
        """Get transaction by reference."""
        result = await self.db.execute(
            select(Transaction).where(Transaction.reference == reference)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise NotFoundError("Transaction", reference)
        return transaction
