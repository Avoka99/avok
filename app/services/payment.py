from typing import Optional, Dict
import logging
import uuid
import httpx
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import PaymentError, NotFoundError
from app.core.config import settings
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.order import Order, OrderStatus
from app.services.escrow import EscrowService
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


class PaymentService:
    """Handle payment processing with Mobile Money integration."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.escrow_service = EscrowService(db)
        self.notification_service = NotificationService(db)
    
    async def initiate_payment(
        self,
        order_id: int,
        momo_provider: str,
        momo_number: str
    ) -> Dict:
        """Initiate Mobile Money payment."""
        order = await self._get_order(order_id)
        
        if order.escrow_status != OrderStatus.PENDING_PAYMENT:
            raise PaymentError(f"Order {order.order_reference} cannot be paid for")
        
        # Generate unique transaction reference
        transaction_reference = f"PAY-{order.order_reference}-{uuid.uuid4().hex[:8]}"
        
        # Create pending transaction record
        transaction = Transaction(
            wallet_id=None,  # Will be linked after payment
            order_id=order.id,
            transaction_type=TransactionType.DEPOSIT,
            status=TransactionStatus.PENDING,
            amount=order.total_amount,
            fee_amount=order.platform_fee,
            net_amount=order.product_price,
            reference=transaction_reference,
            description=f"Payment for order {order.order_reference}",
            momo_provider=momo_provider,
        )
        
        self.db.add(transaction)
        await self.db.commit()
        
        # Initiate Mobile Money payment (abstracted for different providers)
        payment_result = await self._initiate_momo_payment(
            transaction_reference=transaction_reference,
            amount=order.total_amount,
            phone_number=momo_number,
            provider=momo_provider
        )
        
        logger.info(f"Payment initiated for order {order.order_reference}: {transaction_reference}")
        
        return {
            "transaction_reference": transaction_reference,
            "order_reference": order.order_reference,
            "amount": order.total_amount,
            "platform_fee": order.platform_fee,
            "total_amount": order.total_amount,
            "momo_provider": momo_provider,
            "momo_number": momo_number,
            "payment_url": payment_result.get("payment_url"),
            "instructions": payment_result.get("instructions"),
            "status": "pending"
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
                transaction_reference
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
    
    async def _initiate_momo_payment(
        self,
        transaction_reference: str,
        amount: float,
        phone_number: str,
        provider: str
    ) -> Dict:
        """
        Initiate Mobile Money payment with provider.
        Abstracted for different providers (MTN, Vodafone, AirtelTigo).
        """
        # This is a placeholder for actual Mobile Money integration
        # In production, integrate with provider APIs
        
        if provider == "mtn":
            # MTN MoMo API integration
            return {
                "payment_url": f"https://api.mtn.com/momo/pay/{transaction_reference}",
                "instructions": f"Enter PIN on your phone to complete payment of {amount} GHS"
            }
        elif provider == "vodafone":
            # Vodafone Cash API
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