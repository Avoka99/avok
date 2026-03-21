from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.dependencies import get_db, get_current_user
from app.schemas.wallet import WalletBalance, TransactionResponse, WithdrawalRequest
from app.services.wallet import WalletService
from app.models.user import User

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/balance", response_model=WalletBalance)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's wallet balance."""
    wallet_service = WalletService(db)
    balance = await wallet_service.get_balance(current_user.id)
    return balance


@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get transaction history."""
    wallet_service = WalletService(db)
    transactions = await wallet_service.get_transactions(current_user.id, skip, limit)
    return transactions


@router.post("/withdraw")
async def withdraw(
    withdrawal: WithdrawalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Request withdrawal."""
    wallet_service = WalletService(db)
    
    # Only sellers can withdraw (buyers can't withdraw escrow funds directly)
    if current_user.role not in ["seller", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only sellers can withdraw funds")
    
    transaction = await wallet_service.initiate_withdrawal(
        user_id=current_user.id,
        amount=withdrawal.amount,
        momo_number=withdrawal.momo_number,
        momo_provider=withdrawal.momo_provider
    )
    
    return {
        "message": "Withdrawal initiated",
        "transaction_reference": transaction.reference,
        "amount": transaction.amount,
        "net_amount": transaction.net_amount,
        "fee": transaction.fee_amount,
        "status": transaction.status,
        "estimated_processing_time": f"{24} hours"
    }