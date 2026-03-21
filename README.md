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
