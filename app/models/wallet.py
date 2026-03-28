from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String, Enum, Index
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
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    wallet_type = Column(Enum(WalletType), default=WalletType.MAIN, nullable=False)
    
    available_balance = Column(Float, default=0.0, nullable=False)
    pending_balance = Column(Float, default=0.0, nullable=False)
    escrow_balance = Column(Float, default=0.0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet", cascade="all, delete-orphan")
    
    @hybrid_property
    def total_balance(self):
        """Total balance across all wallet types."""
        return self.available_balance + self.pending_balance
    
    def __repr__(self):
        return f"<Wallet {self.id}: User {self.user_id} - Available: {self.available_balance} GHS>"
    
    def to_dict(self):
        """Convert wallet to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "wallet_type": self.wallet_type.value,
            "available_balance": self.available_balance,
            "pending_balance": self.pending_balance,
            "escrow_balance": self.escrow_balance,
            "total_balance": self.total_balance,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }