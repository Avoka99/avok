from typing import Optional, Dict, List
import logging
from datetime import datetime
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.notification import Notification, NotificationType, NotificationStatus
from app.models.user import User
from app.models.order import Order

logger = logging.getLogger(__name__)


class NotificationService:
    """Multi-channel notification service."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def send_sms(self, phone_number: str, message: str) -> Optional[Notification]:
        """Send SMS notification."""
        # Create notification record
        notification = Notification(
            user_id=None,  # Will be set if user exists
            notification_type=NotificationType.SMS,
            status=NotificationStatus.PENDING,
            title="SMS Notification",
            content=message,
            recipient=phone_number
        )
        
        # Find user if exists
        user = await self._get_user_by_phone(phone_number)
        if user:
            notification.user_id = user.id
        
        self.db.add(notification)
        await self.db.commit()
        
        # In production, integrate with Africa's Talking or Twilio
        try:
            # Placeholder for actual SMS sending
            success = await self._send_sms_provider(phone_number, message)
            
            if success:
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.utcnow()
            else:
                notification.status = NotificationStatus.FAILED
                notification.error_message = "Provider returned error"
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            notification.status = NotificationStatus.FAILED
            notification.error_message = str(e)
            await self.db.commit()
        
        return notification
    
    async def send_email(self, email: str, subject: str, content: str) -> Optional[Notification]:
        """Send email notification."""
        notification = Notification(
            user_id=None,
            notification_type=NotificationType.EMAIL,
            status=NotificationStatus.PENDING,
            title=subject,
            content=content,
            recipient=email
        )
        
        # Find user if exists
        user = await self._get_user_by_email(email)
        if user:
            notification.user_id = user.id
        
        self.db.add(notification)
        await self.db.commit()
        
        # In production, integrate with SendGrid
        try:
            success = await self._send_email_provider(email, subject, content)
            
            if success:
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.utcnow()
            else:
                notification.status = NotificationStatus.FAILED
                notification.error_message = "Provider returned error"
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            notification.status = NotificationStatus.FAILED
            notification.error_message = str(e)
            await self.db.commit()
        
        return notification
    
    async def send_order_confirmation(self, order: Order):
        """Send order confirmation notification."""
        buyer = await self._get_user(order.buyer_id)
        seller = await self._get_user(order.seller_id)
        
        # SMS to buyer
        buyer_message = f"Your order {order.order_reference} for {order.product_name} has been created. Amount: {order.total_amount} GHS"
        await self.send_sms(buyer.phone_number, buyer_message)
        
        # Email to buyer if available
        if buyer.email:
            await self.send_email(
                buyer.email,
                f"Order Confirmation - {order.order_reference}",
                f"Your order has been created. Total: {order.total_amount} GHS"
            )
        
        # SMS to seller
        seller_message = f"New order {order.order_reference} for {order.product_name}. Prepare for delivery."
        await self.send_sms(seller.phone_number, seller_message)
    
    async def send_payment_confirmation(self, order_id: int):
        """Send payment confirmation notification."""
        order = await self._get_order(order_id)
        buyer = await self._get_user(order.buyer_id)
        seller = await self._get_user(order.seller_id)
        
        # Buyer notification
        buyer_message = f"Payment of {order.total_amount} GHS confirmed for order {order.order_reference}. Funds held in escrow."
        await self.send_sms(buyer.phone_number, buyer_message)
        
        if buyer.email:
            await self.send_email(
                buyer.email,
                f"Payment Confirmed - {order.order_reference}",
                f"Your payment of {order.total_amount} GHS has been confirmed. Funds are securely held in escrow."
            )
        
        # Seller notification
        seller_message = f"Payment confirmed for order {order.order_reference}. Proceed with delivery."
        await self.send_sms(seller.phone_number, seller_message)
    
    async def send_payment_release(self, order: Order):
        """Send payment release notification."""
        seller = await self._get_user(order.seller_id)
        
        seller_message = f"Payment of {order.product_price} GHS released to your wallet for order {order.order_reference}. (Fee: {order.product_price * 0.02} GHS)"
        await self.send_sms(seller.phone_number, seller_message)
        
        if seller.email:
            await self.send_email(
                seller.email,
                f"Payment Released - {order.order_reference}",
                f"Payment of {order.product_price} GHS has been released to your wallet."
            )
    
    async def send_refund_notification(self, order: Order, reason: str):
        """Send refund notification."""
        buyer = await self._get_user(order.buyer_id)
        
        buyer_message = f"Refund of {order.total_amount} GHS processed for order {order.order_reference}. Reason: {reason}"
        await self.send_sms(buyer.phone_number, buyer_message)
        
        if buyer.email:
            await self.send_email(
                buyer.email,
                f"Refund Processed - {order.order_reference}",
                f"Your refund of {order.total_amount} GHS has been processed. Reason: {reason}"
            )
    
    async def send_dispute_created(self, dispute):
        """Send dispute creation notification."""
        buyer = await self._get_user(dispute.buyer_id)
        seller = await self._get_user(dispute.seller_id)
        
        # Notify seller
        seller_message = f"Dispute opened for order {dispute.order.order_reference}. Reason: {dispute.dispute_type.value}. Please check the app for details."
        await self.send_sms(seller.phone_number, seller_message)
        
        # Notify buyer
        buyer_message = f"Dispute #{dispute.dispute_reference} opened. We'll review and get back to you shortly."
        await self.send_sms(buyer.phone_number, buyer_message)
    
    async def send_dispute_resolved(self, dispute):
        """Send dispute resolution notification."""
        buyer = await self._get_user(dispute.buyer_id)
        seller = await self._get_user(dispute.seller_id)
        
        resolution_messages = {
            "resolved_buyer_wins": "Dispute resolved in your favor. Full refund processed.",
            "resolved_seller_wins": "Dispute resolved in seller's favor. Funds released.",
            "resolved_refund": "Dispute resolved with full refund."
        }
        
        buyer_message = resolution_messages.get(dispute.status.value, "Dispute resolved")
        seller_message = resolution_messages.get(dispute.status.value, "Dispute resolved")
        
        await self.send_sms(buyer.phone_number, f"Order {dispute.order.order_reference}: {buyer_message}")
        await self.send_sms(seller.phone_number, f"Order {dispute.order.order_reference}: {seller_message}")
    
    async def send_withdrawal_initiated(self, phone_number: str, amount: float, reference: str):
        """Send withdrawal initiation notification."""
        message = f"Withdrawal of {amount} GHS initiated. Reference: {reference}. Funds will be sent within {settings.withdrawal_delay_hours} hours."
        await self.send_sms(phone_number, message)
    
    async def send_withdrawal_completed(self, phone_number: str, amount: float, reference: str):
        """Send withdrawal completion notification."""
        message = f"Withdrawal of {amount} GHS completed. Reference: {reference}"
        await self.send_sms(phone_number, message)
    
    async def send_withdrawal_failed(self, phone_number: str, amount: float, reference: str, error: str):
        """Send withdrawal failure notification."""
        message = f"Withdrawal of {amount} GHS failed. Reference: {reference}. Error: {error}"
        await self.send_sms(phone_number, message)
    
    async def send_kyc_approved(self, phone_number: str):
        """Send KYC approval notification."""
        message = "Your KYC verification has been approved. You can now transact on Avok."
        await self.send_sms(phone_number, message)
    
    async def send_kyc_rejected(self, phone_number: str, reason: str):
        """Send KYC rejection notification."""
        message = f"Your KYC verification was rejected. Reason: {reason}. Please resubmit."
        await self.send_sms(phone_number, message)
    
    async def send_payment_failed(self, order_id: int):
        """Send payment failure notification."""
        order = await self._get_order(order_id)
        buyer = await self._get_user(order.buyer_id)
        
        message = f"Payment for order {order.order_reference} failed. Please try again."
        await self.send_sms(buyer.phone_number, message)
    
    async def send_delivery_otp(self, order: Order, otp: str):
        """Send delivery OTP to buyer."""
        buyer = await self._get_user(order.buyer_id)
        
        message = f"Delivery OTP for order {order.order_reference}: {otp}. Provide this to the delivery agent or seller."
        await self.send_sms(buyer.phone_number, message)
        
        if buyer.email:
            await self.send_email(
                buyer.email,
                f"Delivery OTP - {order.order_reference}",
                f"Your delivery OTP is: {otp}"
            )
    
    async def send_reminder(self, order: Order, days_remaining: int):
        """Send escrow release reminder."""
        buyer = await self._get_user(order.buyer_id)
        
        if days_remaining == 7:
            message = f"Reminder: Your order {order.order_reference} will auto-release in 7 days if not confirmed."
        elif days_remaining == 3:
            message = f"URGENT: Your order {order.order_reference} will auto-release in 3 days. Confirm delivery or open dispute."
        elif days_remaining == 1:
            message = f"FINAL WARNING: Your order {order.order_reference} will auto-release in 24 hours. Take action now!"
        else:
            return
        
        await self.send_sms(buyer.phone_number, message)
        
        if buyer.email:
            await self.send_email(
                buyer.email,
                f"Escrow Release Reminder - {order.order_reference}",
                message
            )
    
    async def _send_sms_provider(self, phone_number: str, message: str) -> bool:
        """Send SMS via provider (placeholder)."""
        # In production, integrate with Africa's Talking or Twilio
        logger.info(f"SMS to {phone_number}: {message}")
        return True
    
    async def _send_email_provider(self, email: str, subject: str, content: str) -> bool:
        """Send email via provider (placeholder)."""
        # In production, integrate with SendGrid
        logger.info(f"Email to {email}: {subject}")
        return True
    
    async def _get_user(self, user_id: int) -> User:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)
        return user
    
    async def _get_user_by_phone(self, phone_number: str) -> Optional[User]:
        """Get user by phone number."""
        result = await self.db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def _get_order(self, order_id: int) -> Order:
        """Get order by ID."""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order", order_id)
        return order


from app.core.exceptions import NotFoundError