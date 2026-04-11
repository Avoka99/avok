from datetime import datetime

from sqlalchemy import func, Boolean, Column, DateTime, String, Text

from app.core.database import Base


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    secret_key = Column(String(255), nullable=False)
    allowed_return_urls = Column(Text, nullable=True)
    allowed_cancel_urls = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Merchant {self.id}: {self.name}>"
