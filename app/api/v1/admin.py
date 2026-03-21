from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.api.dependencies import get_db, get_current_admin
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)."""
    from sqlalchemy import select
    from app.models.user import User
    
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return {"users": users, "count": len(users)}


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get user details (admin only)."""
    from sqlalchemy import select
    from app.models.user import User
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/dashboard")
async def admin_dashboard(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin dashboard statistics."""
    from sqlalchemy import select, func
    from app.models.user import User
    from app.models.order import Order
    
    # Get user count
    user_count_result = await db.execute(select(func.count()).select_from(User))
    total_users = user_count_result.scalar()
    
    # Get order count
    order_count_result = await db.execute(select(func.count()).select_from(Order))
    total_orders = order_count_result.scalar()
    
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "admin": current_user.email
    }


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend a user (admin only)."""
    from sqlalchemy import select, update
    from app.models.user import User
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    await db.commit()
    
    return {"message": f"User {user_id} suspended"}