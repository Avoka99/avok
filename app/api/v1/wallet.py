from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from app.api.dependencies import get_db, get_current_user
from app.schemas.wallet import WalletBalance, TransactionResponse, WithdrawalRequest, DepositRequest
from app.services.wallet import WalletService
from app.models.user import User, UserRole

router = APIRouter(prefix="/wallet", tags=["wallet"])


class PaginatedTransactions(BaseModel):
    items: List[TransactionResponse]
    total: int
    skip: int
    limit: int
    has_more: bool


@router.get("/balance", response_model=WalletBalance)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's wallet balance."""
    wallet_service = WalletService(db)
    balance = await wallet_service.get_balance(current_user.id)
    return balance


@router.get("/transactions", response_model=PaginatedTransactions)
async def get_transactions(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get transaction history."""
    wallet_service = WalletService(db)
    transactions = await wallet_service.get_transactions(current_user.id, skip, limit)
    return PaginatedTransactions(
        items=transactions,
        total=len(transactions),
        skip=skip,
        limit=limit,
        has_more=len(transactions) >= limit
    )


@router.post("/deposit")
async def deposit(
    deposit_request: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Deposit money from mobile money or bank into a verified Avok account."""
    wallet_service = WalletService(db)
    transaction = await wallet_service.deposit(
        user_id=current_user.id,
        amount=deposit_request.amount,
        source_type=deposit_request.source_type,
        source_reference=deposit_request.source_reference,
    )

    return {
        "message": "Deposit completed",
        "transaction_reference": transaction.reference,
        "amount": transaction.amount,
        "net_amount": transaction.net_amount,
        "fee": transaction.fee_amount,
        "status": transaction.status,
    }


@router.post("/withdraw")
async def withdraw(
    withdrawal: WithdrawalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Request withdrawal."""
    wallet_service = WalletService(db)
    
    transaction = await wallet_service.initiate_withdrawal(
        user_id=current_user.id,
        amount=withdrawal.amount,
        destination_type=withdrawal.destination_type,
        destination_reference=withdrawal.destination_reference,
        momo_provider=withdrawal.momo_provider,
        bank_name=withdrawal.bank_name,
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
