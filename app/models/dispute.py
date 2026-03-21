from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON, Index
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class DisputeType(str, enum.Enum):
    ITEM_NOT_RECEIVED = "item_not_received"
    WRONG_ITEM = "wrong_item"
    DAMAGED_ITEM = "damaged_item"
    FRAUDULENT = "fraudulent"
    OTHER = "other"


class DisputeStatus(str, enum.Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    AWAITING_BUYER_RESPONSE = "awaiting_buyer_response"
    AWAITING_SELLER_RESPONSE = "awaiting_seller_response"
    RESOLVED_BUYER_WINS = "resolved_buyer_wins"
    RESOLVED_SELLER_WINS = "resolved_seller_wins"
    RESOLVED_REFUND = "resolved_refund"
    CANCELLED = "cancelled"


class EvidenceType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    TEXT = "text"


class Dispute(Base):
    __tablename__ = "disputes"
    
    id = Column(Integer, primary_key=True, index=True)
    dispute_reference = Column(String(50), unique=True, nullable=False, index=True)
    
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    dispute_type = Column(Enum(DisputeType), nullable=False)
    description = Column(Text, nullable=False)
    
    status = Column(Enum(DisputeStatus), default=DisputeStatus.PENDING, nullable=False)
    
    # Evidence
    evidence_urls = Column(JSON, default=list)  # List of S3 URLs
    ai_analysis_result = Column(JSON, nullable=True)  # AI fraud detection results
    
    # Resolution
    resolution_notes = Column(Text, nullable=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Admin approval
    admin_approvals_required = Column(Integer, default=2)
    admin_approvals_received = Column(Integer, default=0)
    admin_approvers = Column(JSON, default=list)  # List of admin IDs who approved
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order = relationship("Order", back_populates="dispute")
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="disputes_as_buyer")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="disputes_as_seller")
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    
    # Indexes
    __table_args__ = (
        Index("ix_disputes_status", "status"),
        Index("ix_disputes_buyer", "buyer_id"),
    )
    
    def __repr__(self):
        return f"<Dispute {self.dispute_reference}: {self.dispute_type} - {self.status}>"