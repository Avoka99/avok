import os

# Settings load at import time — set test defaults before importing the app.
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_avok_api.db")
os.environ.setdefault("PAYMENT_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("ENABLE_PAYMENT_SANDBOX", "true")
os.environ.setdefault("DEBUG", "true")

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_db
from app.core.database import Base

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_avok.db"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override database dependency for testing."""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Setup test database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client():
    """Test client fixture."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session():
    """Database session fixture."""
    async with TestingSessionLocal() as session:
        yield session
