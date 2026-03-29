from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Boolean, DateTime, Enum, Integer, Text, ForeignKey, Index, JSON
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"


class UserStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    DEACTIVATED = "deactivated"


class KYCStatus(str, enum.Enum):
    NOT_SUBMITTED = "not_submitted"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    status = Column(Enum(UserStatus), default=UserStatus.PENDING, nullable=False)
    
    # KYC Information
    kyc_status = Column(Enum(KYCStatus), default=KYCStatus.NOT_SUBMITTED)
    national_id_type = Column(String(50), nullable=True)
    national_id_number = Column(String(50), index=True, nullable=True)
    national_id_image_url = Column(String(500), nullable=True)
    selfie_image_url = Column(String(500), nullable=True)
    kyc_approvals = Column(JSON, default=list, nullable=True)
    
    # Verification
    is_phone_verified = Column(Boolean, default=False)
    phone_verified_at = Column(DateTime, nullable=True)
    
    # Security
    last_login_at = Column(DateTime, nullable=True)
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Fraud detection
    dispute_count = Column(Integer, default=0)
    fraud_score = Column(Integer, default=0)
    is_flagged = Column(Boolean, default=False)
    
    # Avok Account System
    avok_account_number = Column(String(20), unique=True, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    orders_as_buyer = relationship("Order", foreign_keys="Order.buyer_id", back_populates="buyer")
    orders_as_seller = relationship("Order", foreign_keys="Order.seller_id", back_populates="seller")
    disputes_as_buyer = relationship("Dispute", foreign_keys="Dispute.buyer_id", back_populates="buyer")
    disputes_as_seller = relationship("Dispute", foreign_keys="Dispute.seller_id", back_populates="seller")
    notifications = relationship("Notification", back_populates="user")
    admin_actions = relationship(
        "AdminAction",
        foreign_keys="AdminAction.target_user_id",
        back_populates="target_user",
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_users_phone_verified", "phone_number", "is_phone_verified"),
        Index("ix_users_fraud_score", "fraud_score"),
    )
    
    def __repr__(self):
        return f"<User {self.id}: {self.phone_number} ({self.role})>"
