from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
import uuid
import secrets

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError, PermissionDeniedError
from app.core.config import settings
from app.core.finance import calculate_capped_fee, is_verified_account
from app.core.security import generate_otp
from app.models.guest_checkout import GuestCheckoutSession
from app.models.order import Order, OrderStatus, DeliveryMethod
from app.models.order_item import OrderItem
from app.models.user import User, UserRole, UserStatus
from app.models.wallet import Wallet, WalletType
from app.models.otp_delivery import OTPDelivery
from app.models.transaction import Transaction
from app.schemas.order import OrderCreate
from app.services.notification import NotificationService
from app.services.fraud_detection import FraudDetectionService
from app.services.product_import import ProductImportService

logger = logging.getLogger(__name__)


class OrderService:
    """Service for managing checkout sessions and delivery confirmations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_service = NotificationService(db)
        self.fraud_service = FraudDetectionService(db)
        self.product_import_service = ProductImportService()
    
    async def create_order(
        self,
        buyer_id: Optional[int],
        recipient_id: Optional[int],
        product_name: Optional[str],
        product_price: Optional[float],
        delivery_method: DeliveryMethod,
        product_description: Optional[str] = None,
        shipping_address: Optional[str] = None,
        recipient_display_name: Optional[str] = None,
        recipient_contact: Optional[str] = None,
        payout_destination: str = "avok_account",
        payout_reference: Optional[str] = None,
        payout_account_name: Optional[str] = None,
        payout_bank_name: Optional[str] = None,
        product_url: Optional[str] = None,
        auto_import_product_details: bool = True,
        payment_source: str = "verified_account",
        checkout_context: Optional[Dict] = None,
        guest_checkout_session_id: Optional[int] = None,
        items: Optional[List[Dict]] = None,
    ) -> Order:
        """
        Create a new checkout session.
        
        Args:
            buyer_id: ID of the payer
            recipient_id: ID of the payout recipient
            product_name: Name of the product
            product_price: Price of the product in GHS
            delivery_method: How the product will be delivered
            product_description: Optional description
            shipping_address: Required if delivery_method is SHIPPING
            
        Returns:
            Created Order object
        """
        # Validate payer and payout recipient
        buyer = None
        guest_checkout_session = None

        if buyer_id is not None:
            buyer = await self._get_user(buyer_id)

            if buyer.status != UserStatus.ACTIVE:
                raise ValidationError("Payer account is not active")
        elif guest_checkout_session_id is not None:
            guest_checkout_session = await self._get_guest_checkout_session(guest_checkout_session_id)
            if guest_checkout_session.is_expired:
                raise ValidationError("Guest checkout session has expired. Please start a new checkout or register.")
        else:
            raise ValidationError("A payer account or guest checkout session is required")

        recipient = None
        if recipient_id is not None:
            recipient = await self._get_user(recipient_id)
            if recipient.status != UserStatus.ACTIVE:
                raise ValidationError("Recipient account is not active")
            recipient_display_name = recipient.full_name
            recipient_contact = recipient.phone_number
            payout_destination = "avok_account"
            payout_reference = str(recipient.id)
            payout_account_name = recipient.full_name

        recipient = None
        if recipient_id is not None:
            recipient = await self._get_user(recipient_id)
            if recipient.status != UserStatus.ACTIVE:
                raise ValidationError("Recipient account is not active")
            recipient_display_name = recipient.full_name
            recipient_contact = recipient.phone_number
            payout_destination = "avok_account"
            payout_reference = str(recipient.id)
            payout_account_name = recipient.full_name
        elif payout_destination == "avok_account":
            raise ValidationError("External recipients cannot use avok_account payout without an Avok user account")
        
        # Validate shipping address if required
        if delivery_method == DeliveryMethod.SHIPPING and not shipping_address:
            raise ValidationError("Shipping address is required for shipping delivery")
        
        # Enrichment moved to background to avoid freezing the checkout request
        imported_payload = None
        if not product_name:
            product_name = "Checkout session"

        normalized_items = self._normalize_order_items(
            items=items,
            product_name=product_name,
            product_description=product_description,
            product_price=product_price,
            product_url=product_url,
        )
        product_price = sum(item["line_total"] for item in normalized_items)

        if product_price <= 0:
            raise ValidationError("Product price must be greater than 0")
        
        if product_price < 1.0:
            raise ValidationError("Minimum product price is 1.00 GHS")

        primary_item_name = normalized_items[0]["item_name"]
        product_name = (
            f"{primary_item_name} + {len(normalized_items) - 1} more items"
            if len(normalized_items) > 1
            else primary_item_name
        )
        if not product_description:
            product_description = normalized_items[0].get("item_description")

        if payment_source == "verified_account" and buyer is None:
            raise ValidationError("Guest checkout can only be funded through mobile money or bank transfer")

        entry_fee = 0.0 if buyer and payment_source == "verified_account" and is_verified_account(buyer) else calculate_capped_fee(
            product_price,
            percent=settings.platform_fee_percent,
            cap_amount=settings.external_transfer_fee_cap,
        )
        total_amount = product_price + entry_fee
        
        # Check if buyer has sufficient balance (for future feature - if they pre-fund wallet)
        # For now, we'll allow orders even without balance since they'll pay via MoMo
        
        # Generate unique checkout session reference
        order_reference = self._generate_order_reference()
        
        # Create order
        order = Order(
            order_reference=order_reference,
            buyer_id=buyer_id,
            guest_checkout_session_id=guest_checkout_session_id,
            guest_checkout_session=guest_checkout_session,
            seller_id=recipient_id,
            seller_display_name=recipient_display_name,
            seller_contact=recipient_contact,
            payout_destination=payout_destination,
            payout_reference=payout_reference,
            payout_account_name=payout_account_name,
            payout_bank_name=payout_bank_name,
            product_name=product_name,
            product_description=product_description,
            product_price=product_price,
            platform_fee=entry_fee,
            entry_fee=entry_fee,
            release_fee=0.0,
            total_amount=total_amount,
            escrow_status=OrderStatus.PENDING_PAYMENT,
            delivery_method=delivery_method,
            shipping_address=shipping_address if delivery_method == DeliveryMethod.SHIPPING else shipping_address,
            product_url=product_url,
            source_site_name=imported_payload.get("source_site_name") if imported_payload else None,
            imported_media=imported_payload.get("media") if imported_payload else None,
            import_snapshot=imported_payload.get("snapshot") if imported_payload else None,
            payment_source=payment_source,
            payout_metadata={
                "recipient_type": "registered_user" if recipient_id is not None else "external_recipient",
                **(checkout_context or {}),
            },
        )
        
        self.db.add(order)
        await self.db.flush()

        order_items = [
            OrderItem(
                order_id=order.id,
                item_name=item["item_name"],
                item_description=item.get("item_description"),
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                line_total=item["line_total"],
                product_url=item.get("product_url"),
            )
            for item in normalized_items
        ]
        self.db.add_all(order_items)
        await self.db.flush()
        
        fraud_check = await self._check_order_fraud(order)
        order_requires_review = False
        
        if fraud_check.get("is_suspicious"):
            risk_score = fraud_check.get("risk_score", 0)
            flags = fraud_check.get("flags", [])
            
            if risk_score >= settings.fraud_high_risk_threshold:
                order.payout_metadata = order.payout_metadata or {}
                order.payout_metadata["fraud_review"] = {
                    "risk_score": risk_score,
                    "flags": flags,
                    "review_status": "pending",
                    "flagged_at": datetime.utcnow().isoformat()
                }
                order_requires_review = True
                logger.warning(f"High-risk order flagged for review: {order_reference}, risk_score: {risk_score}, flags: {flags}")
            else:
                logger.warning(f"Suspicious order detected: {order_reference}, risk_score: {risk_score}, flags: {flags}")
        
        await self.db.commit()
        
        payer_identifier = buyer_id if buyer_id is not None else f"guest:{guest_checkout_session_id}"
        logger.info(f"Checkout session created: {order_reference} by payer {payer_identifier} for payout destination {payout_destination}")
        
        # Send notifications
        await self.notification_service.send_order_confirmation(order)

        return await self.get_order(order_reference)

    async def enrich_order_metadata(self, order_id: int):
        """Enrich existing order with metadata from product URLs in the background."""
        order = await self.get_order_by_id(order_id)
        if not order.product_url and not order.items:
            return

        # 1. Main Order URL Enrichment
        if order.product_url:
            payload = await self.product_import_service.extract(order.product_url)
            if payload:
                # Only overwrite if currently using generic placeholder
                if order.product_name == "Checkout session":
                    order.product_name = payload.get("product_name", order.product_name)
                    
                if not order.product_description:
                    order.product_description = payload.get("product_description")
                
                order.source_site_name = payload.get("source_site_name")
                order.imported_media = payload.get("media")
                order.import_snapshot = payload.get("snapshot")

        # 2. Per-Item URL Enrichment (Cart Fix Compatibility)
        for item in order.items:
            if item.product_url:
                payload = await self.product_import_service.extract(item.product_url)
                if payload:
                    if not item.item_description:
                        item.item_description = payload.get("product_description")
                    # Optionally update item name if empty or generic
                    if not item.item_name or item.item_name == "Product item":
                        item.item_name = payload.get("product_name") or item.item_name

        await self.db.commit()
        logger.info(f"Order enrichment complete for {order.order_reference}")
    
    async def get_order(self, order_reference: str) -> Order:
        """
        Get order by reference.
        
        Args:
            order_reference: Unique order reference
            
        Returns:
            Order object
        """
        result = await self.db.execute(
            select(Order)
            .options(
                selectinload(Order.buyer),
                selectinload(Order.guest_checkout_session),
                selectinload(Order.seller),
                selectinload(Order.items),
                selectinload(Order.transactions),
                selectinload(Order.dispute),
                selectinload(Order.otp_delivery)
            )
            .where(Order.order_reference == order_reference)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise NotFoundError("Order", order_reference)
        
        return order
    
    async def get_order_by_id(self, order_id: int) -> Order:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order object
        """
        result = await self.db.execute(
            select(Order)
            .options(
                selectinload(Order.buyer),
                selectinload(Order.guest_checkout_session),
                selectinload(Order.seller),
                selectinload(Order.items),
                selectinload(Order.transactions),
                selectinload(Order.dispute),
                selectinload(Order.otp_delivery)
            )
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise NotFoundError("Order", order_id)
        
        return order
    
    async def get_user_orders(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        status: Optional[OrderStatus] = None
    ) -> List[Order]:
        """
        Get orders for a user (both as buyer and seller).
        
        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum records to return
            status: Filter by order status
            
        Returns:
            List of orders
        """
        query = select(Order).options(selectinload(Order.items)).where(
            or_(
                Order.buyer_id == user_id,
                Order.seller_id == user_id
            )
        )
        
        if status:
            query = query.where(Order.escrow_status == status)
        
        query = query.order_by(desc(Order.created_at)).offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_seller_orders(
        self,
        seller_id: int,
        skip: int = 0,
        limit: int = 50,
        status: Optional[OrderStatus] = None
    ) -> List[Order]:
        """
        Get orders for a seller.
        
        Args:
            seller_id: Seller user ID
            skip: Number of records to skip
            limit: Maximum records to return
            status: Filter by order status
            
        Returns:
            List of orders
        """
        query = select(Order).options(selectinload(Order.items)).where(Order.seller_id == seller_id)
        
        if status:
            query = query.where(Order.escrow_status == status)
        
        query = query.order_by(desc(Order.created_at)).offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_buyer_orders(
        self,
        buyer_id: int,
        skip: int = 0,
        limit: int = 50,
        status: Optional[OrderStatus] = None
    ) -> List[Order]:
        """
        Get orders for a buyer.
        
        Args:
            buyer_id: Buyer user ID
            skip: Number of records to skip
            limit: Maximum records to return
            status: Filter by order status
            
        Returns:
            List of orders
        """
        query = select(Order).options(selectinload(Order.items)).where(Order.buyer_id == buyer_id)
        
        if status:
            query = query.where(Order.escrow_status == status)
        
        query = query.order_by(desc(Order.created_at)).offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_order_status(
        self,
        order_id: int,
        new_status: OrderStatus,
        user_id: int,
        reason: Optional[str] = None
    ) -> Order:
        """
        Update order status with validation.
        
        Args:
            order_id: Order ID
            new_status: New status to set
            user_id: User performing the update
            reason: Optional reason for status change
            
        Returns:
            Updated order
        """
        order = await self.get_order_by_id(order_id)
        
        # Validate status transition
        valid_transitions = self._get_valid_status_transitions(order.escrow_status)
        
        if new_status not in valid_transitions:
            raise ValidationError(
                f"Cannot transition from {order.escrow_status} to {new_status}"
            )
        
        # Check permissions
        await self._check_status_update_permission(order, user_id, new_status)
        
        # Update status
        old_status = order.escrow_status
        order.escrow_status = new_status
        
        # Update timestamps based on status
        if new_status == OrderStatus.DELIVERED:
            order.delivered_at = datetime.utcnow()
        elif new_status == OrderStatus.COMPLETED:
            order.completed_at = datetime.utcnow()
        elif new_status == OrderStatus.CANCELLED:
            order.completed_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info(f"Order {order.order_reference} status updated: {old_status} -> {new_status}")
        
        return order
    
    async def generate_delivery_otp(self, order_id: int) -> str:
        """
        Generate OTP for delivery confirmation.
        
        Args:
            order_id: Order ID
            
        Returns:
            Generated OTP code
        """
        order = await self.get_order_by_id(order_id)
        
        # Only seller can generate OTP
        if order.escrow_status not in [OrderStatus.PAYMENT_CONFIRMED, OrderStatus.PROCESSING, OrderStatus.SHIPPED]:
            raise ValidationError(f"Cannot generate OTP for order in status: {order.escrow_status}")
        
        # Check if OTP already exists and not expired
        result = await self.db.execute(
            select(OTPDelivery).where(OTPDelivery.order_id == order_id)
        )
        existing_otp = result.scalar_one_or_none()
        
        if existing_otp and not existing_otp.is_expired() and not existing_otp.is_verified:
            # Reuse existing valid OTP
            otp_code = existing_otp.otp_code
            if order.escrow_status == OrderStatus.PAYMENT_CONFIRMED:
                order.escrow_status = OrderStatus.SHIPPED
                order.start_auto_release_window(settings.escrow_release_days)
                await self.db.commit()
            logger.info(f"Reusing existing OTP for order {order.order_reference}")
        else:
            # Generate new OTP
            otp_code = generate_otp()
            
            # Delete old OTP if exists
            if existing_otp:
                await self.db.delete(existing_otp)
            
            # Create new OTP
            otp_delivery = OTPDelivery(
                order_id=order_id,
                otp_code=otp_code,
                expires_at=datetime.utcnow() + timedelta(hours=24),  # Valid for 24 hours
                max_attempts=5
            )
            self.db.add(otp_delivery)
            
            # Delivery-phase countdown starts only after the recipient actually ships.
            if order.escrow_status in {OrderStatus.PAYMENT_CONFIRMED, OrderStatus.PROCESSING}:
                order.escrow_status = OrderStatus.SHIPPED
            order.start_auto_release_window(settings.escrow_release_days)
            
            await self.db.commit()
            logger.info(f"Generated new OTP for order {order.order_reference}")
        
        # Send OTP to buyer via SMS and email
        await self.notification_service.send_delivery_otp(order, otp_code)
        
        return otp_code
    
    async def confirm_delivery_manually(self, order_id: int) -> Order:
        """
        Manually confirm delivery (buyer confirms receipt).
        
        Args:
            order_id: Order ID
            
        Returns:
            Updated order
        """
        order = await self.get_order_by_id(order_id)
        
        if order.escrow_status != OrderStatus.SHIPPED:
            raise ValidationError(f"Cannot confirm delivery for order in status: {order.escrow_status}")
        
        # Update order
        order.escrow_status = OrderStatus.DELIVERED
        order.delivered_at = datetime.utcnow()
        if order.escrow_release_date is None:
            order.start_auto_release_window(settings.escrow_release_days)
        
        await self.db.commit()
        
        logger.info(f"Delivery manually confirmed for order {order.order_reference}")
        
        return order
    
    async def cancel_order(
        self,
        order_id: int,
        user_id: int,
        reason: str
    ) -> Order:
        """
        Cancel an order before payment or during dispute.
        
        Args:
            order_id: Order ID
            user_id: User requesting cancellation
            reason: Reason for cancellation
            
        Returns:
            Updated order
        """
        order = await self.get_order_by_id(order_id)
        
        # Check if order can be cancelled
        cancellable_statuses = [
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.DISPUTED
        ]
        
        if order.escrow_status not in cancellable_statuses:
            raise ValidationError(f"Cannot cancel order in status: {order.escrow_status}")
        
        # Check permissions
        if user_id not in [order.buyer_id, order.seller_id]:
            # Only admins can cancel other people's orders
            user = await self._get_user(user_id)
            if user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
                raise PermissionDeniedError("Only buyer, seller, or admin can cancel orders")
        
        # Update order
        order.escrow_status = OrderStatus.CANCELLED
        order.completed_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info(f"Order {order.order_reference} cancelled by user {user_id}: {reason}")
        
        # Send notification
        await self._notify_cancellation(order, reason)
        
        return order
    
    async def mark_order_as_shipped(
        self,
        order_id: int,
        seller_id: int,
        tracking_number: Optional[str] = None
    ) -> Order:
        """
        Mark order as shipped (seller action).
        
        Args:
            order_id: Order ID
            seller_id: Seller ID
            tracking_number: Optional tracking number
            
        Returns:
            Updated order
        """
        order = await self.get_order_by_id(order_id)
        
        # Verify seller
        if order.seller_id != seller_id:
            raise PermissionDeniedError("Only the seller can mark order as shipped")
        
        # Check if order can be shipped
        if order.escrow_status not in {OrderStatus.PAYMENT_CONFIRMED, OrderStatus.PROCESSING}:
            raise ValidationError(f"Cannot ship order in status: {order.escrow_status}")
        
        # Update order
        order.escrow_status = OrderStatus.SHIPPED
        order.start_auto_release_window(settings.escrow_release_days)
        if tracking_number:
            order.tracking_number = tracking_number
        
        await self.db.commit()
        
        logger.info(f"Order {order.order_reference} marked as shipped")
        
        # Send notification to buyer
        await self.notification_service.send_sms(
            order.buyer.phone_number,
            f"Your order {order.order_reference} has been shipped. You'll receive an OTP for delivery confirmation."
        )
        
        # Generate OTP for delivery
        await self.generate_delivery_otp(order_id)
        
        return order
    
    async def get_order_statistics(self, user_id: int) -> Dict:
        '''Get order statistics for a user.'''
        buyer_stats_query = select(
            Order.escrow_status,
            func.count(Order.id).label('count'),
            func.sum(Order.total_amount).label('spent')
        ).where(Order.buyer_id == user_id).group_by(Order.escrow_status)
        
        buyer_result = await self.db.execute(buyer_stats_query)
        buyer_rows = buyer_result.all()
        
        buyer_stats = {
            "total": 0, "pending_payment": 0, "in_escrow": 0, "delivered": 0,
            "completed": 0, "disputed": 0, "cancelled": 0, "total_spent": 0.0
        }
        for status, count, spent in buyer_rows:
            buyer_stats["total"] += count
            if status == OrderStatus.PENDING_PAYMENT: buyer_stats["pending_payment"] = count
            elif status == OrderStatus.PAYMENT_CONFIRMED: buyer_stats["in_escrow"] = count
            elif status == OrderStatus.DELIVERED: buyer_stats["delivered"] = count
            elif status == OrderStatus.COMPLETED: 
                buyer_stats["completed"] = count
                buyer_stats["total_spent"] = float(spent or 0.0)
            elif status == OrderStatus.DISPUTED: buyer_stats["disputed"] = count
            elif status == OrderStatus.CANCELLED: buyer_stats["cancelled"] = count

        seller_stats_query = select(
            Order.escrow_status,
            func.count(Order.id).label('count'),
            func.sum(Order.product_price).label('earned')
        ).where(Order.seller_id == user_id).group_by(Order.escrow_status)
        
        seller_result = await self.db.execute(seller_stats_query)
        seller_rows = seller_result.all()

        seller_stats = {
            "total": 0, "pending_payment": 0, "in_escrow": 0, "shipped": 0,
            "completed": 0, "disputed": 0, "cancelled": 0, "total_earned": 0.0
        }
        for status, count, earned in seller_rows:
            seller_stats["total"] += count
            if status == OrderStatus.PENDING_PAYMENT: seller_stats["pending_payment"] = count
            elif status == OrderStatus.PAYMENT_CONFIRMED: seller_stats["in_escrow"] = count
            elif status == OrderStatus.SHIPPED: seller_stats["shipped"] = count
            elif status == OrderStatus.COMPLETED: 
                seller_stats["completed"] = count
                seller_stats["total_earned"] = float(earned or 0.0)
            elif status == OrderStatus.DISPUTED: seller_stats["disputed"] = count
            elif status == OrderStatus.CANCELLED: seller_stats["cancelled"] = count
        
        return {
            "as_buyer": buyer_stats,
            "as_seller": seller_stats
        }

    async def search_orders(
        self,
        query: str,
        skip: int = 0,
        limit: int = 20
    ) -> List[Order]:
        """
        Search orders by product name or reference.
        
        Args:
            query: Search query string
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of matching orders
        """
        search_term = f"%{query}%"
        
        result = await self.db.execute(
            select(Order)
            .where(
                or_(
                    Order.order_reference.ilike(search_term),
                    Order.product_name.ilike(search_term)
                )
            )
            .order_by(desc(Order.created_at))
            .offset(skip)
            .limit(limit)
        )
        
        return result.scalars().all()
    
    async def get_expiring_orders(self, days_threshold: int = 3) -> List[Order]:
        """
        Get orders that will auto-release soon.
        
        Args:
            days_threshold: Number of days threshold
            
        Returns:
            List of orders expiring soon
        """
        threshold_date = datetime.utcnow() + timedelta(days=days_threshold)
        
        result = await self.db.execute(
            select(Order)
            .where(
                and_(
                    Order.escrow_status.in_([OrderStatus.SHIPPED, OrderStatus.DELIVERED]),
                    Order.escrow_release_date <= threshold_date,
                    Order.escrow_release_date > datetime.utcnow()
                )
            )
        )
        
        return result.scalars().all()
    
    async def _check_order_fraud(self, order: Order) -> Dict:
        """Check if order shows signs of fraud."""
        flags = []
        risk_score = 0
        
        if order.product_price > settings.fraud_high_value_threshold * 5:
            flags.append("high_value")
            risk_score += 20
        
        if order.buyer_id is not None:
            buyer_orders = await self.get_buyer_orders(order.buyer_id, limit=100)
            if len(buyer_orders) == 0:
                flags.append("new_buyer")
                risk_score += 10

            buyer = await self._get_user(order.buyer_id)
            if buyer.dispute_count > settings.fraud_max_dispute_count:
                flags.append("buyer_high_disputes")
                risk_score += 30
        else:
            flags.append("guest_payer")
            risk_score += 5
        
        if order.seller_id is not None:
            seller = await self._get_user(order.seller_id)
            if seller.dispute_count > settings.fraud_max_dispute_count + 2:
                flags.append("seller_high_disputes")
                risk_score += 30
        else:
            flags.append("external_recipient")
            risk_score += 5
        
        if order.buyer_id is not None:
            recent_orders = await self.get_buyer_orders(
                order.buyer_id,
                limit=10
            )
            if len(recent_orders) > 5:
                time_diff = (datetime.utcnow() - recent_orders[0].created_at).total_seconds() / 3600
                if time_diff < 24:
                    flags.append("rapid_ordering")
                    risk_score += 15
        
        return {
            "is_suspicious": risk_score > settings.fraud_low_risk_threshold,
            "risk_score": risk_score,
            "flags": flags,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _check_status_update_permission(
        self,
        order: Order,
        user_id: int,
        new_status: OrderStatus
    ):
        """Check if user has permission to update order status."""
        user = await self._get_user(user_id)
        
        # Admin can do anything
        if user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            return
        
        # Buyer permissions
        if user_id == order.buyer_id:
            allowed_for_buyer = [
                OrderStatus.CANCELLED,  # Buyer can cancel before payment
                OrderStatus.DISPUTED,   # Buyer can open dispute
                OrderStatus.DELIVERED   # Buyer can confirm delivery
            ]
            if new_status not in allowed_for_buyer:
                raise PermissionDeniedError(f"Buyer cannot change status to {new_status}")
            return
        
        # Seller permissions
        if user_id == order.seller_id:
            allowed_for_seller = [
                OrderStatus.PROCESSING,  # Seller can mark as processing
                OrderStatus.SHIPPED,     # Seller can mark as shipped
                OrderStatus.CANCELLED    # Seller can cancel before payment
            ]
            if new_status not in allowed_for_seller:
                raise PermissionDeniedError(f"Seller cannot change status to {new_status}")
            return
        
        raise PermissionDeniedError("User is not involved in this order")
    
    async def _notify_cancellation(self, order: Order, reason: str):
        """Send cancellation notifications to both parties."""
        buyer_contact = self.notification_service._get_buyer_contact(order)

        # Notify buyer
        if buyer_contact["phone_number"]:
            await self.notification_service.send_sms(
                buyer_contact["phone_number"],
                f"Order {order.order_reference} has been cancelled. Reason: {reason}"
            )
        
        recipient_contact = self._get_recipient_contact(order)
        if recipient_contact["phone_number"]:
            await self.notification_service.send_sms(
                recipient_contact["phone_number"],
                f"Order {order.order_reference} has been cancelled. Reason: {reason}"
            )
        
        # Send email if available
        if buyer_contact["email"]:
            await self.notification_service.send_email(
                buyer_contact["email"],
                f"Order Cancelled - {order.order_reference}",
                f"Your order has been cancelled.\nReason: {reason}"
            )
    
    def _generate_order_reference(self) -> str:
        """Generate unique order reference."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_part = secrets.token_hex(4).upper()
        return f"AVOK-{timestamp}-{random_part}"
    
    def _get_valid_status_transitions(self, current_status: OrderStatus) -> List[OrderStatus]:
        """Get valid next statuses from current status."""
        transitions = {
            OrderStatus.PENDING_PAYMENT: [
                OrderStatus.PAYMENT_CONFIRMED,
                OrderStatus.CANCELLED
            ],
            OrderStatus.PAYMENT_CONFIRMED: [
                OrderStatus.PROCESSING,
                OrderStatus.SHIPPED,
                OrderStatus.DISPUTED,
                OrderStatus.CANCELLED
            ],
            OrderStatus.PROCESSING: [
                OrderStatus.SHIPPED,
                OrderStatus.DISPUTED
            ],
            OrderStatus.SHIPPED: [
                OrderStatus.DELIVERED,
                OrderStatus.COMPLETED,
                OrderStatus.DISPUTED
            ],
            OrderStatus.DELIVERED: [
                OrderStatus.COMPLETED,
                OrderStatus.DISPUTED
            ],
            OrderStatus.DISPUTED: [
                OrderStatus.CANCELLED,
                OrderStatus.REFUNDED
            ],
            OrderStatus.COMPLETED: [],  # Terminal state
            OrderStatus.CANCELLED: [],  # Terminal state
            OrderStatus.REFUNDED: []    # Terminal state
        }
        
        return transitions.get(current_status, [])
    
    async def _get_user(self, user_id: int) -> User:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def _get_guest_checkout_session(self, session_id: int) -> GuestCheckoutSession:
        result = await self.db.execute(
            select(GuestCheckoutSession).where(GuestCheckoutSession.id == session_id)
        )
        guest_checkout_session = result.scalar_one_or_none()
        if not guest_checkout_session:
            raise NotFoundError("Guest checkout session", session_id)
        return guest_checkout_session

    def _get_recipient_contact(self, order: Order) -> Dict[str, Optional[str]]:
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

    def _normalize_order_items(
        self,
        items: Optional[List[Dict]],
        product_name: Optional[str],
        product_description: Optional[str],
        product_price: Optional[float],
        product_url: Optional[str],
    ) -> List[Dict]:
        if items:
            normalized_items = []
            for item in items:
                quantity = int(item.get("quantity", 1) or 1)
                unit_price = float(item.get("unit_price", 0) or 0)
                line_total = round(quantity * unit_price, 2)
                if quantity < 1:
                    raise ValidationError("Item quantity must be at least 1")
                if unit_price < 1.0:
                    raise ValidationError("Item unit price must be at least 1.00 GHS")

                item_name = (item.get("item_name") or "").strip()
                if not item_name:
                    raise ValidationError("Each item must include an item_name")

                normalized_items.append(
                    {
                        "item_name": item_name,
                        "item_description": item.get("item_description"),
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "line_total": line_total,
                        "product_url": item.get("product_url"),
                    }
                )
            return normalized_items

        if not product_name:
            raise ValidationError("Product name is required")
        if product_price is None:
            raise ValidationError("Product price is required")

        return [
            {
                "item_name": product_name,
                "item_description": product_description,
                "quantity": 1,
                "unit_price": float(product_price),
                "line_total": round(float(product_price), 2),
                "product_url": product_url,
            }
        ]
