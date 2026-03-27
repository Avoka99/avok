# Avok - Secure Escrow Payment System

Avok is a production-ready escrow-based payment system designed to prevent online marketplace scams in Ghana.

## Features

- 🔒 **Secure Escrow**: Funds held securely until delivery confirmation
- 💳 **Mobile Money Integration**: MTN, Vodafone, AirtelTigo support
- 🔐 **OTP Delivery Confirmation**: Verify deliveries with OTP codes
- ⚖️ **Dispute Resolution**: Multi-admin approval system
- 🤖 **Fraud Detection**: AI-powered fraud analysis
- 📱 **Multi-channel Notifications**: SMS + Email
- 🏦 **Wallet System**: Separate main and escrow wallets
- 📊 **Audit Logs**: Complete admin action tracking

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy (async)
- **Background Jobs**: Celery + Redis
- **Authentication**: JWT
- **Storage**: AWS S3
- **Notifications**: Africa's Talking, SendGrid

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker (optional)

### Installation
## Local testing

1. Turn on local docs in `.env`:
   `DEBUG=true`
2. Start the API:
   `uvicorn app.main:app --reload`
3. Seed local accounts:
   `venv\Scripts\python.exe scripts\seed_local_data.py`
4. Open Swagger:
   `http://localhost:8000/docs`

Seeded accounts all use password `Password1`:
- Buyer: `0241111111`
- Seller: `0242222222`
- Admin: `0243333333`

Suggested local test flow:
- Login as buyer with `/api/v1/auth/login`
- Create an order with `/api/v1/orders/`
- Initiate payment with `/api/v1/payments/initiate`
- Simulate success with `/api/v1/payments/sandbox/{transaction_reference}/success`
- Check order state with `/api/v1/orders/{order_reference}`
- Login as seller and generate delivery OTP
- Confirm delivery and verify escrow release
