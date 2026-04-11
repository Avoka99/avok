import os
from pathlib import Path
import importlib
from uuid import uuid4

# Settings load at import time — set test defaults before importing the app.
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-at-least-32-characters-long")
TEST_DB_PATH = Path(__file__).resolve().parent.parent / "test_avok_api.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}")
os.environ.setdefault("PAYMENT_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("ENABLE_PAYMENT_SANDBOX", "true")
os.environ.setdefault("DEBUG", "true")

import httpx
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.exc import OperationalError
from fastapi.testclient import TestClient

import app.models  # noqa: F401


_original_httpx_client_init = httpx.Client.__init__


def _patched_httpx_client_init(self, *args, **kwargs):
    kwargs.pop("app", None)
    return _original_httpx_client_init(self, *args, **kwargs)


httpx.Client.__init__ = _patched_httpx_client_init

from app.main import app
from app.api.dependencies import get_db
from app.core.database import Base

app.state.skip_startup_db_init = True

engine = None
TestingSessionLocal = None


def _load_all_models() -> None:
    import app.models  # noqa: F401
    for module_name in (
        "app.models.user",
        "app.models.wallet",
        "app.models.transaction",
        "app.models.order",
        "app.models.order_item",
        "app.models.dispute",
        "app.models.notification",
        "app.models.otp_delivery",
        "app.models.admin_action",
        "app.models.guest_checkout",
        "app.models.merchant",
        "app.models.merchant_checkout_intent",
    ):
        importlib.import_module(module_name)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override database dependency for testing."""
    if TestingSessionLocal is None:
        raise RuntimeError("Test database session factory is not initialized")
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Setup test database."""
    global engine, TestingSessionLocal
    _load_all_models()
    db_path = TEST_DB_PATH.with_name(f"test_avok_api_{uuid4().hex}.db")
    db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    TestingSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        try:
            await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, checkfirst=True))
        except OperationalError:
            pass
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
    yield
    await engine.dispose()
    TestingSessionLocal = None
    engine = None
    if db_path.exists():
        db_path.unlink()


@pytest.fixture(autouse=True)
def override_app_db_dependency():
    """Ensure every test client request uses the same test database session factory."""
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    """Test client fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def db_session(setup_db):
    """Database session fixture."""
    if TestingSessionLocal is None:
        raise RuntimeError("Test database session factory is not initialized")
    async with TestingSessionLocal() as session:
        yield session
