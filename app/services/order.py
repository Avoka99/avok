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
from app.core.security import generate_otp
from app.models.order import Order, OrderStatus, DeliveryMethod
from app.models.user import User
from app.models.wallet import Wallet
from app.models.otp_delivery import OTPDelivery
from app.models.transaction import Transaction
from app.schemas.order import OrderCreate
from app.services.notification import NotificationService
from app.services.fraud_detection import FraudDetectionService

logger = logging.getLogger(__name__)


class OrderService:
    """Service for managing orders and deliveries."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_service = NotificationService(db)
        self.fraud_service = FraudDetectionService(db)
    
    async def create_order(
        self,
        buyer_id: int,
        seller_id: int,
        product_name: str,
        product_price: float,
        delivery_method: DeliveryMethod,
        product_description: Optional[str] = None,
        shipping_address: Optional[str] = None
    ) -> Order:
        """
        Create a new order.
        
        Args:
            buyer_id: ID of the buyer
            seller_id: ID of the seller
            product_name: Name of the product
            product_price: Price of the product in GHS
            delivery_method: How the product will be delivered
            product_description: Optional description
            shipping_address: Required if delivery_method is SHIPPING
            
        Returns:
            Created Order object
        """
        # Validate buyer and seller
        buyer = await self._get_user(buyer_id)
        seller = await self._get_user(seller_id)
        
        if not buyer.is_active:
            raise ValidationError("Buyer account is not active")
        
        if not seller.is_active:
            raise ValidationError("Seller account is not active")
        
        # Validate seller is actually a seller
        if seller.role not in ["seller", "admin", "super_admin"]:
            raise ValidationError("User is not a registered seller")
        
        # Validate price
        if product_price <= 0:
            raise ValidationError("Product price must be greater than 0")
        
        if product_price < 1.0:
            raise ValidationError("Minimum product price is 1.00 GHS")
        
        # Validate shipping address if required
        if delivery_method == DeliveryMethod.SHIPPING and not shipping_address:
            raise ValidationError("Shipping address is required for shipping delivery")
        
        # Calculate fees
        platform_fee = product_price * (settings.platform_fee_percent / 100)
        total_amount = product_price + platform_fee
        
        # Check if buyer has sufficient balance (for future feature - if they pre-fund wallet)
        # For now, we'll allow orders even without balance since they'll pay via MoMo
        
        # Generate unique order reference
        order_reference = self._generate_order_reference()
        
        # Create order
        order = Order(
            order_reference=order_reference,
            buyer_id=buyer_id,
            seller_id=seller_id,
            product_name=product_name,
            product_description=product_description,
            product_price=product_price,
            platform_fee=platform_fee,
            total_amount=total_amount,
            escrow_status=OrderStatus.PENDING_PAYMENT,
            delivery_method=delivery_method,
            shipping_address=shipping_address if delivery_method == DeliveryMethod.SHIPPING else None
        )
        
        self.db.add(order)
        await self.db.flush()
        
        # Run fraud detection on new order
        fraud_check = await self._check_order_fraud(order)
        if fraud_check.get("is_suspicious"):
            logger.warning(f"Suspicious order detected: {order_reference}, flags: {fraud_check.get('flags')}")
            # Don't block order, just log for now
            order.metadata = {"fraud_flags": fraud_check.get("flags")}
        
        await self.db.commit()
        
        logger.info(f"Order created: {order_reference} by buyer {buyer_id} from seller {seller_id}")
        
        # Send notifications
        await self.notification_service.send_order_confirmation(order)
        
        return order
    
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
                selectinload(Order.seller),
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
                selectinload(Order.seller),
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
        query = select(Order).where(
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
        query = select(Order).where(Order.seller_id == seller_id)
        
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
        query = select(Order).where(Order.buyer_id == buyer_id)
        
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
        
        # Store status change metadata
        if not hasattr(order, 'metadata') or not order.metadata:
            order.metadata = {}
        
        if 'status_history' not in order.metadata:
            order.metadata['status_history'] = []
        
        order.metadata['status_history'].append({
            'from': old_status.value,
            'to': new_status.value,
            'by': user_id,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        })
        
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
            
            # Update order status to SHIPPED if it was in PROCESSING
            if order.escrow_status == OrderStatus.PAYMENT_CONFIRMED:
                order.escrow_status = OrderStatus.SHIPPED
            
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
            if user.role not in ["admin", "super_admin"]:
                raise PermissionDeniedError("Only buyer, seller, or admin can cancel orders")
        
        # Update order
        order.escrow_status = OrderStatus.CANCELLED
        order.completed_at = datetime.utcnow()
        
        # Store cancellation reason
        if not hasattr(order, 'metadata') or not order.metadata:
            order.metadata = {}
        order.metadata['cancellation_reason'] = reason
        order.metadata['cancelled_by'] = user_id
        
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
        if order.escrow_status != OrderStatus.PAYMENT_CONFIRMED:
            raise ValidationError(f"Cannot ship order in status: {order.escrow_status}")
        
        # Update order
        order.escrow_status = OrderStatus.SHIPPED
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
        """
        Get order statistics for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with order statistics
        """
        # Orders as buyer
        buyer_orders_query = select(Order).where(Order.buyer_id == user_id)
        buyer_orders_result = await self.db.execute(buyer_orders_query)
        buyer_orders = buyer_orders_result.scalars().all()
        
        # Orders as seller
        seller_orders_query = select(Order).where(Order.seller_id == user_id)
        seller_orders_result = await self.db.execute(seller_orders_query)
        seller_orders = seller_orders_result.scalars().all()
        
        # Calculate statistics
        buyer_stats = {
            "total": len(buyer_orders),
            "pending_payment": sum(1 for o in buyer_orders if o.escrow_status == OrderStatus.PENDING_PAYMENT),
            "in_escrow": sum(1 for o in buyer_orders if o.escrow_status == OrderStatus.PAYMENT_CONFIRMED),
            "delivered": sum(1 for o in buyer_orders if o.escrow_status == OrderStatus.DELIVERED),
            "completed": sum(1 for o in buyer_orders if o.escrow_status == OrderStatus.COMPLETED),
            "disputed": sum(1 for o in buyer_orders if o.escrow_status == OrderStatus.DISPUTED),
            "cancelled": sum(1 for o in buyer_orders if o.escrow_status == OrderStatus.CANCELLED),
            "total_spent": sum(o.total_amount for o in buyer_orders if o.escrow_status == OrderStatus.COMPLETED)
        }
        
        seller_stats = {
            "total": len(seller_orders),
            "pending_payment": sum(1 for o in seller_orders if o.escrow_status == OrderStatus.PENDING_PAYMENT),
            "in_escrow": sum(1 for o in seller_orders if o.escrow_status == OrderStatus.PAYMENT_CONFIRMED),
            "shipped": sum(1 for o in seller_orders if o.escrow_status == OrderStatus.SHIPPED),
            "completed": sum(1 for o in seller_orders if o.escrow_status == OrderStatus.COMPLETED),
            "disputed": sum(1 for o in seller_orders if o.escrow_status == OrderStatus.DISPUTED),
            "cancelled": sum(1 for o in seller_orders if o.escrow_status == OrderStatus.CANCELLED),
            "total_earned": sum(o.product_price for o in seller_orders if o.escrow_status == OrderStatus.COMPLETED)
        }
        
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
                    Order.escrow_status == OrderStatus.PAYMENT_CONFIRMED,
                    Order.escrow_release_date <= threshold_date,
                    Order.escrow_release_date > datetime.utcnow()
                )
            )
        )
        
        return result.scalars().all()
    
    async def _check_order_fraud(self, order: Order) -> Dict:
        """
        Check if order shows signs of fraud.
        
        Args:
            order: Order to check
            
        Returns:
            Dictionary with fraud check results
        """
        flags = []
        risk_score = 0
        
        # Check for unusually high value
        if order.product_price > 5000:
            flags.append("high_value")
            risk_score += 20
        
        # Check buyer's order history
        buyer_orders = await self.get_buyer_orders(order.buyer_id, limit=100)
        if len(buyer_orders) == 0:
            flags.append("new_buyer")
            risk_score += 10
        
        # Check if buyer has disputes
        buyer = await self._get_user(order.buyer_id)
        if buyer.dispute_count > 3:
            flags.append("buyer_high_disputes")
            risk_score += 30
        
        # Check seller's reputation
        seller = await self._get_user(order.seller_id)
        if seller.dispute_count > 5:
            flags.append("seller_high_disputes")
            risk_score += 30
        
        # Check for rapid ordering
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
            "is_suspicious": risk_score > 40,
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
        if user.role in ["admin", "super_admin"]:
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
        # Notify buyer
        await self.notification_service.send_sms(
            order.buyer.phone_number,
            f"Order {order.order_reference} has been cancelled. Reason: {reason}"
        )
        
        # Notify seller
        await self.notification_service.send_sms(
            order.seller.phone_number,
            f"Order {order.order_reference} has been cancelled. Reason: {reason}"
        )
        
        # Send email if available
        if order.buyer.email:
            await self.notification_service.send_email(
                order.buyer.email,
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
                OrderStatus.DISPUTED
            ],
            OrderStatus.DELIVERED: [
                OrderStatus.COMPLETED,
                OrderStatus.DISPUTED
            ],
            OrderStatus.DISPUTED: [
                OrderStatus.COMPLETED,
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