from fastapi import APIRouter

from app.api.v1 import auth, orders, payments, disputes, wallet, admin, checkout_sessions

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(orders.router)
api_router.include_router(checkout_sessions.router)
api_router.include_router(payments.router)
api_router.include_router(disputes.router)
api_router.include_router(wallet.router)
api_router.include_router(admin.router)
