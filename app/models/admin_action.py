from datetime import datetime
from sqlalchemy import func, Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON, Index
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class AdminActionType(str, enum.Enum):
    USER_SUSPEND = "user_suspend"
    USER_UNSUSPEND = "user_unsuspend"
    USER_BAN = "user_ban"
    DISPUTE_RESOLVE = "dispute_resolve"
    ORDER_CANCEL = "order_cancel"
    REFUND_PROCESS = "refund_process"
    FRAUD_FLAG = "fraud_flag"
    KYC_APPROVE = "kyc_approve"
    KYC_REJECT = "kyc_reject"
    WITHDRAWAL_APPROVE = "withdrawal_approve"


class AdminActionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class AdminAction(Base):
    __tablename__ = "admin_actions"
    
    id = Column(Integer, primary_key=True, index=True)
    action_reference = Column(String(50), unique=True, nullable=False, index=True)
    
    action_type = Column(Enum(AdminActionType), nullable=False)
    status = Column(Enum(AdminActionStatus), default=AdminActionStatus.PENDING, nullable=False)
    
    # Target
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    target_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    target_dispute_id = Column(Integer, ForeignKey("disputes.id"), nullable=True)
    
    # Action details
    action_data = Column(JSON, nullable=False)  # Parameters for the action
    reason = Column(Text, nullable=False)
    
    # Admin approval
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approvals_required = Column(Integer, default=2)
    approvals_received = Column(Integer, default=0)
    approvers = Column(JSON, default=list)  # List of admin IDs who approved
    
    # Execution
    executed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    execution_result = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    executed_by = relationship("User", foreign_keys=[executed_by_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
    target_order = relationship("Order", foreign_keys=[target_order_id])
    target_dispute = relationship("Dispute", foreign_keys=[target_dispute_id])
    
    # Indexes
    __table_args__ = (
        Index("ix_admin_actions_status", "status"),
        Index("ix_admin_actions_type", "action_type"),
    )
    
    def __repr__(self):
        return f"<AdminAction {self.action_reference}: {self.action_type} - {self.status}>"