from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models.notification import Notification, NotificationStatus, NotificationType
from app.models.order import Order
from app.models.user import User, UserRole, UserStatus

logger = logging.getLogger(__name__)


class NotificationService:
    """Persist in-app notifications and fan out SMS/email when configured."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_notifications_for_actor(self, actor, limit: int = 50) -> List[Notification]:
        query = (
            select(Notification)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )

        if getattr(actor, "is_guest", False):
            query = query.where(Notification.guest_checkout_session_id == actor.guest_session_id)
        else:
            query = query.where(Notification.user_id == actor.id)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def send_sms(
        self,
        phone_number: str,
        message: str,
        *,
        title: str = "SMS Notification",
        order_reference: Optional[str] = None,
        action_url: Optional[str] = None,
        user_id: Optional[int] = None,
        guest_checkout_session_id: Optional[int] = None,
    ) -> Optional[Notification]:
        if not phone_number:
            return None

        notification = await self._create_channel_notification(
            notification_type=NotificationType.SMS,
            recipient=phone_number,
            title=title,
            content=message,
            order_reference=order_reference,
            action_url=action_url,
            user_id=user_id,
            guest_checkout_session_id=guest_checkout_session_id,
        )

        provider_result = await self._send_sms_provider(phone_number, message)
        await self._finalize_channel_notification(notification, provider_result)
        return notification

    async def send_email(
        self,
        email: str,
        subject: str,
        content: str,
        *,
        order_reference: Optional[str] = None,
        action_url: Optional[str] = None,
        user_id: Optional[int] = None,
        guest_checkout_session_id: Optional[int] = None,
    ) -> Optional[Notification]:
        if not email:
            return None

        notification = await self._create_channel_notification(
            notification_type=NotificationType.EMAIL,
            recipient=email,
            title=subject,
            content=content,
            order_reference=order_reference,
            action_url=action_url,
            user_id=user_id,
            guest_checkout_session_id=guest_checkout_session_id,
        )

        provider_result = await self._send_email_provider(email, subject, content)
        await self._finalize_channel_notification(notification, provider_result)
        return notification

    async def create_in_app_notification(
        self,
        *,
        title: str,
        content: str,
        recipient: str,
        order_reference: Optional[str],
        action_url: Optional[str],
        user_id: Optional[int] = None,
        guest_checkout_session_id: Optional[int] = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            guest_checkout_session_id=guest_checkout_session_id,
            notification_type=NotificationType.IN_APP,
            status=NotificationStatus.SENT,
            title=title,
            content=content,
            recipient=recipient,
            order_reference=order_reference,
            action_url=action_url,
            sent_at=datetime.now(timezone.utc),
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def notify_contact(
        self,
        *,
        title: str,
        message: str,
        contact: Dict[str, Optional[str]],
        order_reference: Optional[str],
        action_url: Optional[str],
        email_subject: Optional[str] = None,
        user_id: Optional[int] = None,
        guest_checkout_session_id: Optional[int] = None,
    ) -> None:
        recipient_label = contact.get("full_name") or contact.get("phone_number") or contact.get("email") or "Unknown recipient"

        if user_id is not None or guest_checkout_session_id is not None:
            await self.create_in_app_notification(
                title=title,
                content=message,
                recipient=recipient_label,
                order_reference=order_reference,
                action_url=action_url,
                user_id=user_id,
                guest_checkout_session_id=guest_checkout_session_id,
            )

        if contact.get("phone_number"):
            await self.send_sms(
                contact["phone_number"],
                message,
                title=title,
                order_reference=order_reference,
                action_url=action_url,
                user_id=user_id,
                guest_checkout_session_id=guest_checkout_session_id,
            )

        if contact.get("email"):
            await self.send_email(
                contact["email"],
                email_subject or title,
                message,
                order_reference=order_reference,
                action_url=action_url,
                user_id=user_id,
                guest_checkout_session_id=guest_checkout_session_id,
            )

    async def send_order_confirmation(self, order: Order):
        order = await self._get_order(order.id)
        action_url = self._build_checkout_link(order.order_reference)
        buyer_contact = self._get_buyer_contact(order)
        recipient_contact = await self._get_recipient_contact(order)

        await self.notify_contact(
            title="Checkout session created",
            message=(
                f"Checkout session {order.order_reference} is ready for {order.product_name}. "
                f"Avok will hold the funds in escrow after payment. Monitor it here: {action_url}"
            ),
            contact=buyer_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Checkout Session Created - {order.order_reference}",
            user_id=order.buyer_id,
            guest_checkout_session_id=order.guest_checkout_session_id,
        )

        await self.notify_contact(
            title="New escrow session to monitor",
            message=(
                f"Avok opened escrow for checkout session {order.order_reference}. "
                f"Prepare for delivery and monitor the funds here: {action_url}"
            ),
            contact=recipient_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"New Escrow Session - {order.order_reference}",
            user_id=order.seller_id,
        )

    async def send_payment_confirmation(self, order_id: int):
        order = await self._get_order(order_id)
        action_url = self._build_checkout_link(order.order_reference)
        buyer_contact = self._get_buyer_contact(order)
        recipient_contact = await self._get_recipient_contact(order)

        await self.notify_contact(
            title="Funds secured in escrow",
            message=(
                f"Payment for checkout session {order.order_reference} is confirmed. "
                f"Avok now holds {order.total_amount:.2f} GHS in escrow. Monitor it here: {action_url}"
            ),
            contact=buyer_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Funds Held In Escrow - {order.order_reference}",
            user_id=order.buyer_id,
            guest_checkout_session_id=order.guest_checkout_session_id,
        )

        await self.notify_contact(
            title="Escrow funded",
            message=(
                f"Checkout session {order.order_reference} is funded and ready for delivery. "
                f"Monitor the escrow status here: {action_url}"
            ),
            contact=recipient_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Escrow Funded - {order.order_reference}",
            user_id=order.seller_id,
        )

    async def send_payment_release(self, order: Order):
        order = await self._get_order(order.id)
        action_url = self._build_checkout_link(order.order_reference)
        buyer_contact = self._get_buyer_contact(order)
        recipient_contact = await self._get_recipient_contact(order)

        await self.notify_contact(
            title="Escrow released",
            message=(
                f"Checkout session {order.order_reference} is complete. "
                f"Avok released the escrow funds. Review the final status here: {action_url}"
            ),
            contact=buyer_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Escrow Released - {order.order_reference}",
            user_id=order.buyer_id,
            guest_checkout_session_id=order.guest_checkout_session_id,
        )

        await self.notify_contact(
            title="Payout released",
            message=(
                f"Avok released payout for checkout session {order.order_reference}. "
                f"Net payout: {(order.product_price - order.release_fee):.2f} GHS. Monitor the session here: {action_url}"
            ),
            contact=recipient_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Payout Released - {order.order_reference}",
            user_id=order.seller_id,
        )

    async def send_refund_notification(self, order: Order, reason: str):
        order = await self._get_order(order.id)
        action_url = self._build_checkout_link(order.order_reference)
        buyer_contact = self._get_buyer_contact(order)
        recipient_contact = await self._get_recipient_contact(order)

        await self.notify_contact(
            title="Refund processed",
            message=(
                f"Avok refunded checkout session {order.order_reference}. "
                f"Refund amount: {order.total_amount:.2f} GHS. Reason: {reason}. Monitor here: {action_url}"
            ),
            contact=buyer_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Refund Processed - {order.order_reference}",
            user_id=order.buyer_id,
            guest_checkout_session_id=order.guest_checkout_session_id,
        )

        await self.notify_contact(
            title="Escrow refunded",
            message=(
                f"Checkout session {order.order_reference} was refunded to the payer. "
                f"Reason: {reason}. Review the final status here: {action_url}"
            ),
            contact=recipient_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Escrow Refunded - {order.order_reference}",
            user_id=order.seller_id,
        )

    async def send_dispute_created(self, dispute):
        order = dispute.order if dispute.order is not None else await self._get_order(dispute.order_id)
        action_url = self._build_checkout_link(order.order_reference)
        buyer_contact = self._get_buyer_contact(order)
        recipient_contact = await self._get_dispute_recipient_contact(dispute)

        await self.notify_contact(
            title="Dispute opened",
            message=(
                f"Dispute {dispute.dispute_reference} was opened for checkout session {order.order_reference}. "
                f"Avok is reviewing it now. Monitor updates here: {action_url}"
            ),
            contact=buyer_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Dispute Opened - {order.order_reference}",
            user_id=order.buyer_id,
            guest_checkout_session_id=order.guest_checkout_session_id,
        )

        await self.notify_contact(
            title="Dispute requires attention",
            message=(
                f"A dispute was opened for checkout session {order.order_reference}. "
                f"Please monitor the session and admin updates here: {action_url}"
            ),
            contact=recipient_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Dispute Alert - {order.order_reference}",
            user_id=order.seller_id,
        )

    async def send_dispute_resolved(self, dispute):
        order = dispute.order if dispute.order is not None else await self._get_order(dispute.order_id)
        action_url = self._build_checkout_link(order.order_reference)
        buyer_contact = self._get_buyer_contact(order)
        recipient_contact = await self._get_dispute_recipient_contact(dispute)

        resolution_messages = {
            "resolved_buyer_wins": "Dispute resolved in the payer's favor. Refund completed.",
            "resolved_seller_wins": "Dispute resolved in the recipient's favor. Funds released.",
            "resolved_refund": "Dispute resolved with a refund.",
        }
        resolution_message = resolution_messages.get(dispute.status.value, "Dispute resolved.")

        await self.notify_contact(
            title="Dispute resolved",
            message=f"{resolution_message} Monitor the final escrow status here: {action_url}",
            contact=buyer_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Dispute Resolved - {order.order_reference}",
            user_id=order.buyer_id,
            guest_checkout_session_id=order.guest_checkout_session_id,
        )

        await self.notify_contact(
            title="Dispute update",
            message=f"{resolution_message} Monitor the final escrow status here: {action_url}",
            contact=recipient_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Dispute Updated - {order.order_reference}",
            user_id=order.seller_id,
        )

    async def send_withdrawal_initiated(self, phone_number: str, amount: float, reference: str):
        await self.send_sms(
            phone_number,
            f"Withdrawal of {amount:.2f} GHS initiated. Reference: {reference}. Funds will be sent within {settings.withdrawal_delay_hours} hours.",
            title="Withdrawal initiated",
        )

    async def send_withdrawal_completed(self, phone_number: str, amount: float, reference: str):
        await self.send_sms(
            phone_number,
            f"Withdrawal of {amount:.2f} GHS completed. Reference: {reference}.",
            title="Withdrawal completed",
        )

    async def send_withdrawal_failed(self, phone_number: str, amount: float, reference: str, error: str):
        await self.send_sms(
            phone_number,
            f"Withdrawal of {amount:.2f} GHS failed. Reference: {reference}. Error: {error}",
            title="Withdrawal failed",
        )

    async def send_kyc_approved(self, phone_number: str):
        await self.send_sms(phone_number, "Your KYC verification has been approved. You can now transact on Avok.", title="KYC approved")

    async def send_kyc_rejected(self, phone_number: str, reason: str):
        await self.send_sms(phone_number, f"Your KYC verification was rejected. Reason: {reason}. Please resubmit.", title="KYC rejected")

    async def send_payment_failed(self, order_id: int):
        order = await self._get_order(order_id)
        action_url = self._build_checkout_link(order.order_reference)
        buyer_contact = self._get_buyer_contact(order)
        await self.notify_contact(
            title="Payment failed",
            message=(
                f"Payment for checkout session {order.order_reference} failed. "
                f"Please retry funding and monitor the session here: {action_url}"
            ),
            contact=buyer_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Payment Failed - {order.order_reference}",
            user_id=order.buyer_id,
            guest_checkout_session_id=order.guest_checkout_session_id,
        )

    async def send_delivery_otp(self, order: Order, otp: str):
        order = await self._get_order(order.id)
        action_url = self._build_checkout_link(order.order_reference)
        buyer_contact = self._get_buyer_contact(order)
        recipient_contact = await self._get_recipient_contact(order)

        await self.notify_contact(
            title="Delivery OTP ready",
            message=(
                f"Delivery OTP for checkout session {order.order_reference}: {otp}. "
                f"Use it after handover and monitor the session here: {action_url}"
            ),
            contact=buyer_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Delivery OTP - {order.order_reference}",
            user_id=order.buyer_id,
            guest_checkout_session_id=order.guest_checkout_session_id,
        )

        await self.notify_contact(
            title="OTP generated for handover",
            message=(
                f"The payer can now confirm delivery for checkout session {order.order_reference}. "
                f"Monitor the handover stage here: {action_url}"
            ),
            contact=recipient_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Delivery OTP Generated - {order.order_reference}",
            user_id=order.seller_id,
        )

    async def send_reminder(self, order: Order, days_remaining: int):
        order = await self._get_order(order.id)
        action_url = self._build_checkout_link(order.order_reference)
        buyer_contact = self._get_buyer_contact(order)

        if days_remaining == 7:
            message = f"Reminder: checkout session {order.order_reference} will auto-release in 7 days if not confirmed. Monitor it here: {action_url}"
        elif days_remaining == 3:
            message = f"Urgent: checkout session {order.order_reference} will auto-release in 3 days. Confirm delivery or open dispute here: {action_url}"
        elif days_remaining == 1:
            message = f"Final warning: checkout session {order.order_reference} will auto-release in 24 hours. Review it here now: {action_url}"
        else:
            return

        await self.notify_contact(
            title="Escrow release reminder",
            message=message,
            contact=buyer_contact,
            order_reference=order.order_reference,
            action_url=action_url,
            email_subject=f"Escrow Reminder - {order.order_reference}",
            user_id=order.buyer_id,
            guest_checkout_session_id=order.guest_checkout_session_id,
        )

    async def notify_admins(
        self,
        *,
        title: str,
        message: str,
        action_url: Optional[str] = None,
        order_reference: Optional[str] = None,
    ) -> None:
        admins = await self._get_active_admins()
        for admin in admins:
            await self.notify_contact(
                title=title,
                message=message,
                contact={
                    "phone_number": admin.phone_number,
                    "email": admin.email,
                    "full_name": admin.full_name,
                },
                order_reference=order_reference,
                action_url=action_url,
                email_subject=title,
                user_id=admin.id,
            )

    async def _create_channel_notification(
        self,
        *,
        notification_type: NotificationType,
        recipient: str,
        title: str,
        content: str,
        order_reference: Optional[str],
        action_url: Optional[str],
        user_id: Optional[int],
        guest_checkout_session_id: Optional[int],
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            guest_checkout_session_id=guest_checkout_session_id,
            notification_type=notification_type,
            status=NotificationStatus.PENDING,
            title=title,
            content=content,
            recipient=recipient,
            order_reference=order_reference,
            action_url=action_url,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def _finalize_channel_notification(self, notification: Notification, provider_result: Dict[str, Optional[str]]) -> None:
        if provider_result.get("success"):
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now(timezone.utc)
            notification.external_id = provider_result.get("external_id")
        else:
            notification.status = NotificationStatus.FAILED
            notification.error_message = provider_result.get("error_message") or "Provider returned an error"
        await self.db.commit()

    async def _send_sms_provider(self, phone_number: str, message: str) -> Dict[str, Optional[str]]:
        if settings.debug or settings.app_env != "production":
            logger.info("Simulated SMS delivery in %s mode; %s", settings.app_env, message)
            return {"success": True, "external_id": "debug-simulated"}

        if settings.africastalking_api_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "https://api.africastalking.com/version1/messaging",
                        data={
                            "username": settings.africastalking_username,
                            "to": phone_number,
                            "message": message,
                            "from": settings.africastalking_sender_id,
                        },
                        headers={"apiKey": settings.africastalking_api_key},
                    )
                if response.is_success:
                    return {"success": True, "external_id": "africastalking"}
                return {"success": False, "error_message": response.text}
            except Exception as exc:
                logger.error("Africa's Talking SMS send failed: %s", exc)
                return {"success": False, "error_message": str(exc)}

        logger.info("SMS provider not configured; %s", message)
        return {"success": False, "error_message": "SMS provider is not configured"}

    async def _send_email_provider(self, email: str, subject: str, content: str) -> Dict[str, Optional[str]]:
        if settings.debug or settings.app_env != "production":
            logger.info("Simulated email delivery in %s mode; %s", settings.app_env, subject)
            return {"success": True, "external_id": "debug-simulated"}

        if settings.sendgrid_api_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "https://api.sendgrid.com/v3/mail/send",
                        headers={
                            "Authorization": f"Bearer {settings.sendgrid_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "personalizations": [{"to": [{"email": email}]}],
                            "from": {"email": settings.sendgrid_from_email},
                            "subject": subject,
                            "content": [{"type": "text/plain", "value": content}],
                        },
                    )
                if response.status_code in {200, 202}:
                    return {"success": True, "external_id": "sendgrid"}
                return {"success": False, "error_message": response.text}
            except Exception as exc:
                logger.error("SendGrid email send failed: %s", exc)
                return {"success": False, "error_message": str(exc)}

        logger.info("Email provider not configured; %s", subject)
        return {"success": False, "error_message": "Email provider is not configured"}

    def _build_checkout_link(self, order_reference: str) -> str:
        base_url = settings.frontend_base_url.rstrip("/")
        return f"{base_url}/checkout/{order_reference}"

    async def _get_user(self, user_id: int) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def _get_active_admins(self) -> List[User]:
        result = await self.db.execute(
            select(User).where(
                User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]),
                User.status == UserStatus.ACTIVE,
            )
        )
        return result.scalars().all()

    async def _get_order(self, order_id: int) -> Order:
        result = await self.db.execute(
            select(Order)
            .options(
                selectinload(Order.buyer),
                selectinload(Order.guest_checkout_session),
                selectinload(Order.seller),
            )
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order", order_id)
        return order

    def _get_buyer_contact(self, order: Order) -> Dict[str, Optional[str]]:
        if order.buyer:
            return {
                "phone_number": order.buyer.phone_number,
                "email": order.buyer.email,
                "full_name": order.buyer.full_name,
            }
        if order.guest_checkout_session:
            return {
                "phone_number": order.guest_checkout_session.phone_number,
                "email": order.guest_checkout_session.email,
                "full_name": order.guest_checkout_session.full_name,
            }
        metadata = order.payout_metadata or {}
        return {
            "phone_number": metadata.get("guest_phone_number"),
            "email": metadata.get("guest_email"),
            "full_name": metadata.get("guest_full_name"),
        }

    async def _get_recipient_contact(self, order: Order) -> Dict[str, Optional[str]]:
        if order.seller:
            return {
                "phone_number": order.seller.phone_number,
                "email": order.seller.email,
                "full_name": order.seller.full_name,
            }
        return {
            "phone_number": order.seller_contact,
            "email": None,
            "full_name": order.seller_display_name,
        }

    async def _get_dispute_recipient_contact(self, dispute) -> Dict[str, Optional[str]]:
        if dispute.seller_id:
            seller = await self._get_user(dispute.seller_id)
            return {
                "phone_number": seller.phone_number,
                "email": seller.email,
                "full_name": seller.full_name,
            }

        order = dispute.order if dispute.order is not None else await self._get_order(dispute.order_id)
        return {
            "phone_number": order.seller_contact,
            "email": None,
            "full_name": order.seller_display_name,
        }
