from datetime import datetime
from sqlalchemy import func, Column, Integer, Float, DateTime, ForeignKey, String, Enum, Index, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
import enum

from app.core.database import Base


class WalletType(str, enum.Enum):
    """Wallet type enum."""
    MAIN = "main"
    ESCROW = "escrow"


class Wallet(Base):
    """User wallet model."""
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint('available_balance >= 0', name='check_positive_available_balance'),
        CheckConstraint('pending_balance >= 0', name='check_positive_pending_balance'),
        CheckConstraint('escrow_balance >= 0', name='check_positive_escrow_balance'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    wallet_type = Column(Enum(WalletType), default=WalletType.MAIN, nullable=False)
    
    available_balance = Column(Float, default=0.0, nullable=False)
    pending_balance = Column(Float, default=0.0, nullable=False)
    escrow_balance = Column(Float, default=0.0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet", cascade="all, delete-orphan")
    
    @hybrid_property
    def total_balance(self):
        """Total balance across all wallet types."""
        return self.available_balance + self.pending_balance
    
    def __repr__(self):
        return f"<Wallet {self.id}: User {self.user_id} - Available: {self.available_balance} GHS>"