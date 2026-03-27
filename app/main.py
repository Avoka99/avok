from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import init_db, close_db, get_db
from app.core.exceptions import AvokException
from app.api.v1.router import api_router
from app.api.middleware.audit_log import AuditLogMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

_openapi = settings.debug or settings.enable_openapi_docs
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs" if _openapi else None,
    redoc_url="/redoc" if _openapi else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditLogMiddleware)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    await init_db()
    logger.info("Application started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    await close_db()
    logger.info("Application shutdown")


@app.exception_handler(AvokException)
async def avok_exception_handler(request: Request, exc: AvokException):
    """Handle custom exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    )

# Add these test endpoints
@app.get("/")
async def root():
    """Root endpoint for quick server checks."""
    return {
        "message": f"{settings.app_name} API is running",
        "status": "ok",
        "health": "/health",
        "api_prefix": settings.api_v1_prefix,
        "docs": "/docs" if (settings.debug or settings.enable_openapi_docs) else None,
    }


@app.get("/test")
async def test():
    return {"message": "Test endpoint working!", "status": "ok"}

@app.get("/test/db")
async def test_db(db: AsyncSession = Depends(get_db)):
    """Test database connection"""
    try:
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1"))
        return {"status": "success", "message": "Database connected"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
# Include API routes
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": settings.app_name}


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
