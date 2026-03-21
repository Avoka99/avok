from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Enum, JSON, Index
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class TransactionStatus(str, enum.Enum):
    """Transaction status enum."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class TransactionType(str, enum.Enum):
    """Transaction type enum."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    ESCROW_HOLD = "escrow_hold"
    ESCROW_RELEASE = "escrow_release"
    REFUND = "refund"
    FEE = "fee"
    PLATFORM_FEE = "platform_fee"
    SELLER_FEE = "seller_fee"


class Transaction(Base):
    """Transaction model for all financial transactions."""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    
    transaction_type = Column(Enum(TransactionType), nullable=False)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    
    amount = Column(Float, nullable=False)
    fee_amount = Column(Float, default=0.0)
    net_amount = Column(Float, nullable=False)
    
    reference = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    extra_data = Column(JSON, nullable=True)  # Additional data as JSON
    
    # Mobile money specific
    momo_provider = Column(String(50), nullable=True)  # MTN, Vodafone, AirtelTigo
    momo_number = Column(String(20), nullable=True)
    momo_transaction_id = Column(String(255), nullable=True)
    momo_approval_code = Column(String(50), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    wallet = relationship("Wallet", back_populates="transactions")
    order = relationship("Order", back_populates="transactions")
    
    # Indexes
    __table_args__ = (
        Index("ix_transactions_wallet_status", "wallet_id", "status"),
        Index("ix_transactions_order", "order_id"),
        Index("ix_transactions_type", "transaction_type"),
        Index("ix_transactions_created", "created_at"),
    )
    
    def __repr__(self):
        return f"<Transaction {self.id}: {self.transaction_type.value} - {self.amount} GHS ({self.status.value})>"
    
    def to_dict(self):
        """Convert transaction to dictionary."""
        return {
            "id": self.id,
            "reference": self.reference,
            "type": self.transaction_type.value,
            "status": self.status.value,
            "amount": self.amount,
            "fee": self.fee_amount,
            "net_amount": self.net_amount,
            "description": self.description,
	    "extra_data": self.extra_data,
            "momo_provider": self.momo_provider,
            "momo_transaction_id": self.momo_transaction_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }