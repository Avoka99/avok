from datetime import datetime, timedelta
from typing import Optional, List
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.core.exceptions import NotFoundError, ValidationError
from app.core.config import settings
from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.order import Order, OrderStatus
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


class WalletService:
    """Wallet management service."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_service = NotificationService(db)
    
    async def get_balance(self, user_id: int) -> dict:
        """Get user's wallet balance."""
        wallet = await self._get_wallet(user_id)
        
        return {
            "available_balance": wallet.available_balance,
            "pending_balance": wallet.pending_balance,
            "escrow_balance": wallet.escrow_balance,
            "total_balance": wallet.available_balance + wallet.pending_balance + wallet.escrow_balance
        }
    
    async def get_transactions(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        transaction_type: Optional[TransactionType] = None
    ) -> List[Transaction]:
        """Get user's transaction history."""
        wallet = await self._get_wallet(user_id)
        
        query = select(Transaction).where(Transaction.wallet_id == wallet.id)
        
        if transaction_type:
            query = query.where(Transaction.transaction_type == transaction_type)
        
        query = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def initiate_withdrawal(
        self,
        user_id: int,
        amount: float,
        momo_number: str,
        momo_provider: str
    ) -> Transaction:
        """Initiate withdrawal request."""
        wallet = await self._get_wallet(user_id)
        
        if amount <= 0:
            raise ValidationError("Withdrawal amount must be positive")
        
        if amount > wallet.available_balance:
            raise ValidationError("Insufficient balance")
        
        # Calculate seller fee if applicable
        user = await self._get_user(user_id)
        fee_amount = 0
        
        if user.role == "seller":
            fee_amount = amount * (settings.seller_withdrawal_fee_percent / 100)
            net_amount = amount - fee_amount
        else:
            net_amount = amount
        
        # Create withdrawal transaction
        transaction = Transaction(
            wallet_id=wallet.id,
            transaction_type=TransactionType.WITHDRAWAL,
            status=TransactionStatus.PENDING,
            amount=amount,
            fee_amount=fee_amount,
            net_amount=net_amount,
            reference=f"WDR-{uuid.uuid4().hex[:12].upper()}",
            description=f"Withdrawal to {momo_provider} {momo_number}",
            momo_provider=momo_provider,
        )
        
        self.db.add(transaction)
        
        # Hold funds in pending balance
        wallet.available_balance -= amount
        wallet.pending_balance += amount
        
        await self.db.commit()
        
        # Schedule withdrawal processing after delay
        from app.workers.escrow_tasks import process_withdrawal
        process_withdrawal.apply_async(
            args=[transaction.id],
            countdown=settings.withdrawal_delay_hours * 3600
        )
        
        logger.info(f"Withdrawal initiated for user {user_id}: {amount} GHS")
        
        # Send notification
        await self.notification_service.send_withdrawal_initiated(
            user.phone_number,
            amount,
            transaction.reference
        )
        
        return transaction
    
    async def process_withdrawal(self, transaction_id: int) -> Transaction:
        """Process pending withdrawal."""
        transaction = await self._get_transaction(transaction_id)
        
        if transaction.status != TransactionStatus.PENDING:
            raise ValidationError("Transaction already processed")
        
        wallet = await self._get_wallet_by_id(transaction.wallet_id)
        
        # Process actual payout (integrate with Mobile Money API)
        try:
            payout_result = await self._process_momo_payout(
                amount=transaction.net_amount,
                phone_number=transaction.momo_number,
                provider=transaction.momo_provider,
                reference=transaction.reference
            )
            
            if payout_result["success"]:
                transaction.status = TransactionStatus.COMPLETED
                transaction.completed_at = datetime.utcnow()
                
                # Move from pending to completed
                wallet.pending_balance -= transaction.amount
                
                await self.db.commit()
                
                # Send success notification
                await self.notification_service.send_withdrawal_completed(
                    wallet.user.phone_number,
                    transaction.amount,
                    transaction.reference
                )
                
                logger.info(f"Withdrawal processed: {transaction.reference}")
            else:
                # Refund the amount back to available balance
                wallet.available_balance += transaction.amount
                wallet.pending_balance -= transaction.amount
                transaction.status = TransactionStatus.FAILED
                
                await self.db.commit()
                
                # Send failure notification
                await self.notification_service.send_withdrawal_failed(
                    wallet.user.phone_number,
                    transaction.amount,
                    transaction.reference,
                    payout_result.get("error", "Unknown error")
                )
                
        except Exception as e:
            logger.error(f"Withdrawal processing failed: {e}")
            # Rollback - refund the amount
            wallet.available_balance += transaction.amount
            wallet.pending_balance -= transaction.amount
            transaction.status = TransactionStatus.FAILED
            
            await self.db.commit()
            raise
        
        return transaction
    
    async def _process_momo_payout(
        self,
        amount: float,
        phone_number: str,
        provider: str,
        reference: str
    ) -> dict:
        """Process Mobile Money payout (placeholder - integrate with provider API)."""
        # In production, integrate with actual provider APIs
        # This is a placeholder that always succeeds
        
        logger.info(f"Processing payout: {amount} GHS to {phone_number} via {provider}")
        
        # Simulate API call
        return {
            "success": True,
            "transaction_id": f"PAYOUT-{reference}",
            "message": "Payout successful"
        }
    
    async def _get_wallet(self, user_id: int) -> Wallet:
        """Get user's main wallet."""
        result = await self.db.execute(
            select(Wallet).where(
                Wallet.user_id == user_id,
                Wallet.wallet_type == "main"
            )
        )
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise NotFoundError("Wallet", user_id)
        return wallet
    
    async def _get_wallet_by_id(self, wallet_id: int) -> Wallet:
        """Get wallet by ID."""
        result = await self.db.execute(
            select(Wallet).where(Wallet.id == wallet_id)
        )
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise NotFoundError("Wallet", wallet_id)
        return wallet
    
    async def _get_transaction(self, transaction_id: int) -> Transaction:
        """Get transaction by ID."""
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise NotFoundError("Transaction", transaction_id)
        return transaction
    
    async def _get_user(self, user_id: int) -> User:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)
        return user