import sys

with open('c:/Users/User/Desktop/AvokProject/app/services/order.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('    async def get_order_statistics(self, user_id: int) -> Dict:')
end_idx = content.find('    async def search_orders(')

if start_idx == -1 or end_idx == -1:
    print('Could not find start or end index')
    sys.exit(1)

new_func = """    async def get_order_statistics(self, user_id: int) -> Dict:
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

"""

new_content = content[:start_idx] + new_func + content[end_idx:]

with open('c:/Users/User/Desktop/AvokProject/app/services/order.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Successfully patched order.py')
