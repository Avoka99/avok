from datetime import datetime
from sqlalchemy import func, Column, Integer, String, DateTime, ForeignKey, Enum, Boolean, Text, JSON
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class NotificationType(str, enum.Enum):
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    guest_checkout_session_id = Column(Integer, ForeignKey("guest_checkout_sessions.id", ondelete="CASCADE"), nullable=True)
    
    notification_type = Column(Enum(NotificationType), nullable=False)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False)
    
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    
    recipient = Column(String(255), nullable=False)  # Phone number or email
    order_reference = Column(String(50), nullable=True)
    action_url = Column(String(500), nullable=True)
    extra_data = Column(JSON, nullable=True)
    
    # Tracking
    external_id = Column(String(255), nullable=True)  # Provider's message ID
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    guest_checkout_session = relationship("GuestCheckoutSession", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification {self.id}: {self.notification_type} - {self.status}>"
