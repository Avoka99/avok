import sys

def patch_escrow():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/services/escrow.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replacements for `hold_funds_in_escrow`
    old_tx_code = """        # Create transaction record
        transaction = Transaction(
            wallet_id=buyer_wallet.id,
            order_id=order.id,
            transaction_type=TransactionType.ESCROW_HOLD,
            status=TransactionStatus.COMPLETED,
            amount=gross_amount,
            fee_amount=fee_amount,
            net_amount=order.product_price,
            reference=transaction_reference,
            description=f"Escrow hold for checkout session {order.order_reference}",
            extra_data={"payment_source": payment_source},
        )
        
        self.db.add(transaction)"""
        
    new_tx_code = """        # Fetch existing or create transaction record
        result = await self.db.execute(
            select(Transaction).where(Transaction.reference == transaction_reference)
        )
        transaction = result.scalar_one_or_none()
        
        if transaction:
            transaction.wallet_id = buyer_wallet.id
            transaction.transaction_type = TransactionType.ESCROW_HOLD
            transaction.status = TransactionStatus.COMPLETED
            transaction.amount = gross_amount
            transaction.fee_amount = fee_amount
            transaction.net_amount = order.product_price
            transaction.description = f"Escrow hold for checkout session {order.order_reference}"
            if not transaction.extra_data:
                transaction.extra_data = {}
            transaction.extra_data["payment_source"] = payment_source
        else:
            transaction = Transaction(
                wallet_id=buyer_wallet.id,
                order_id=order.id,
                transaction_type=TransactionType.ESCROW_HOLD,
                status=TransactionStatus.COMPLETED,
                amount=gross_amount,
                fee_amount=fee_amount,
                net_amount=order.product_price,
                reference=transaction_reference,
                description=f"Escrow hold for checkout session {order.order_reference}",
                extra_data={"payment_source": payment_source},
            )
            self.db.add(transaction)"""
            
    if old_tx_code not in content:
        print("Could not find old tx code in escrow.py")
        sys.exit(1)
        
    content = content.replace(old_tx_code, new_tx_code)
    
    # Remove duplicate notification
    old_notif = """        # Send notification
        await self.notification_service.send_order_confirmation(order)"""
    new_notif = """        # Notification removed to prevent duplicates"""
    
    if old_notif in content:
        content = content.replace(old_notif, new_notif)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
def patch_wallet_model():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/models/wallet.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    old = "return self.available_balance + self.pending_balance + self.escrow_balance"
    new = "return self.available_balance + self.pending_balance"
    
    if old not in content:
        print("Could not find old total_balance in wallet_model")
        sys.exit(1)
        
    content = content.replace(old, new)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def patch_wallet_service():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/services/wallet.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    old = '"total_balance": wallet.available_balance + wallet.pending_balance + wallet.escrow_balance,'
    new = '"total_balance": wallet.available_balance + wallet.pending_balance,'
    
    if old not in content:
        print("Could not find old total_balance in wallet_service")
        sys.exit(1)
        
    content = content.replace(old, new)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    patch_escrow()
    patch_wallet_model()
    patch_wallet_service()
    print("Patched all.")
