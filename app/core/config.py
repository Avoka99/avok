from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # Application
    app_name: str = Field(default="Avok", env="APP_NAME")
    app_env: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=False, env="DEBUG")
    frontend_base_url: str = Field(default="http://localhost:3000", env="FRONTEND_BASE_URL")
    enable_openapi_docs: bool = Field(
        default=False,
        env="ENABLE_OPENAPI_DOCS",
        description="Expose /docs and /redoc even when DEBUG is false (e.g. internal staging).",
    )
    secret_key: str = Field(..., env="SECRET_KEY")
    api_v1_prefix: str = Field(default="/api/v1", env="API_V1_PREFIX")
    
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    database_pool_size: int = Field(default=20, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=40, env="DATABASE_MAX_OVERFLOW")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_max_connections: int = Field(default=50, env="REDIS_MAX_CONNECTIONS")
    
    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/1", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", env="CELERY_RESULT_BACKEND")
    
    # JWT
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=30, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    
    # AWS S3
    aws_access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    aws_s3_bucket: Optional[str] = Field(default=None, env="AWS_S3_BUCKET")
    aws_s3_region: str = Field(default="us-east-1", env="AWS_S3_REGION")
    
    # SMS
    africastalking_username: str = Field(default="sandbox", env="AFRICASTALKING_USERNAME")
    africastalking_api_key: Optional[str] = Field(default=None, env="AFRICASTALKING_API_KEY")
    africastalking_sender_id: str = Field(default="AVOK", env="AFRICASTALKING_SENDER_ID")
    
    # Email
    sendgrid_api_key: Optional[str] = Field(default=None, env="SENDGRID_API_KEY")
    sendgrid_from_email: str = Field(default="noreply@avok.com", env="SENDGRID_FROM_EMAIL")
    
    # Escrow
    escrow_release_days: int = Field(default=14, env="ESCROW_RELEASE_DAYS")
    escrow_reminder_day_1: int = Field(default=7, env="ESCROW_REMINDER_DAY_1")
    escrow_reminder_day_2: int = Field(default=10, env="ESCROW_REMINDER_DAY_2")
    escrow_reminder_day_3: int = Field(default=13, env="ESCROW_REMINDER_DAY_3")
    platform_fee_percent: float = Field(default=1.0, env="PLATFORM_FEE_PERCENT")
    seller_withdrawal_fee_percent: float = Field(default=1.0, env="SELLER_WITHDRAWAL_FEE_PERCENT")
    external_transfer_fee_cap: float = Field(default=30.0, env="EXTERNAL_TRANSFER_FEE_CAP")
    withdrawal_delay_hours: int = Field(default=24, env="WITHDRAWAL_DELAY_HOURS")
    
    # Admin
    min_admin_approvals: int = Field(default=2, env="MIN_ADMIN_APPROVALS")
    
    # Fraud Detection
    fraud_high_risk_threshold: int = Field(default=70, env="FRAUD_HIGH_RISK_THRESHOLD")
    fraud_medium_risk_threshold: int = Field(default=50, env="FRAUD_MEDIUM_RISK_THRESHOLD")
    fraud_low_risk_threshold: int = Field(default=40, env="FRAUD_LOW_RISK_THRESHOLD")
    fraud_max_dispute_count: int = Field(default=3, env="FRAUD_MAX_DISPUTE_COUNT")
    fraud_high_value_threshold: float = Field(default=1000.0, env="FRAUD_HIGH_VALUE_THRESHOLD")
    fraud_new_account_days: int = Field(default=7, env="FRAUD_NEW_ACCOUNT_DAYS")
    fraud_auto_flag_threshold: int = Field(default=80, env="FRAUD_AUTO_FLAG_THRESHOLD")
    fraud_completion_rate_threshold: float = Field(default=0.5, env="FRAUD_COMPLETION_RATE_THRESHOLD")
    fraud_max_orders_per_day: int = Field(default=5, env="FRAUD_MAX_ORDERS_PER_DAY")
    
    # Security
    allowed_origins: List[str] = Field(default=["*"], env="ALLOWED_ORIGINS")
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, env="RATE_LIMIT_PERIOD")
    payment_webhook_secret: Optional[str] = Field(default=None, env="PAYMENT_WEBHOOK_SECRET")
    enable_payment_sandbox: bool = Field(default=False, env="ENABLE_PAYMENT_SANDBOX")

    # MTN MoMo Collection (optional — when all set, MTN request-to-pay is used for provider mtn)
    mtn_momo_base_url: Optional[str] = Field(default=None, env="MTN_MOMO_BASE_URL")
    mtn_momo_subscription_key: Optional[str] = Field(default=None, env="MTN_MOMO_SUBSCRIPTION_KEY")
    mtn_momo_api_user: Optional[str] = Field(default=None, env="MTN_MOMO_API_USER")
    mtn_momo_api_key: Optional[str] = Field(default=None, env="MTN_MOMO_API_KEY")
    mtn_momo_target_environment: str = Field(default="sandbox", env="MTN_MOMO_TARGET_ENVIRONMENT")
    mtn_momo_currency: str = Field(default="EUR", env="MTN_MOMO_CURRENCY")
    
    # MTN MoMo Disbursement (payout to users — separate API from Collection)
    mtn_momo_disbursement_base_url: Optional[str] = Field(default=None, env="MTN_MOMO_DISBURSEMENT_BASE_URL")
    mtn_momo_disbursement_subscription_key: Optional[str] = Field(default=None, env="MTN_MOMO_DISBURSEMENT_SUBSCRIPTION_KEY")
    mtn_momo_disbursement_api_user: Optional[str] = Field(default=None, env="MTN_MOMO_DISBURSEMENT_API_USER")
    mtn_momo_disbursement_api_key: Optional[str] = Field(default=None, env="MTN_MOMO_DISBURSEMENT_API_KEY")
    
    # Wallet payout simulation (set true to simulate payouts without real provider)
    wallet_payout_simulate: bool = Field(default=False, env="WALLET_PAYOUT_SIMULATE")
    
    # Telecel Cash (optional)
    telecel_base_url: Optional[str] = Field(default=None, env="TELECEL_BASE_URL")
    telecel_api_key: Optional[str] = Field(default=None, env="TELECEL_API_KEY")
    telecel_api_secret: Optional[str] = Field(default=None, env="TELECEL_API_SECRET")
    
    # AirtelTigo Money (optional)
    airteltigo_base_url: Optional[str] = Field(default=None, env="AIRTELTIGO_BASE_URL")
    airteltigo_api_key: Optional[str] = Field(default=None, env="AIRTELTIGO_API_KEY")
    airteltigo_api_secret: Optional[str] = Field(default=None, env="AIRTELTIGO_API_SECRET")
    
    # Direct Bank Integration via Sponsor Bank (GhIPSS)
    sponsor_bank_api_url: Optional[str] = Field(default=None, env="SPONSOR_BANK_API_URL")
    sponsor_bank_api_key: Optional[str] = Field(default=None, env="SPONSOR_BANK_API_KEY")
    sponsor_bank_api_secret: Optional[str] = Field(default=None, env="SPONSOR_BANK_API_SECRET")
    avok_settlement_account: Optional[str] = Field(default=None, env="AVOK_SETTLEMENT_ACCOUNT")
    avok_virtual_account: Optional[str] = Field(default=None, env="AVOK_VIRTUAL_ACCOUNT")
    bank_collection_method: str = Field(default="virtual_account", env="BANK_COLLECTION_METHOD")
    bank_disbursement_method: str = Field(default="ghipss", env="BANK_DISBURSEMENT_METHOD")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v):
        if not v:
            raise ValueError("DATABASE_URL must be set")
        return v

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v):
        if not v or v == "your-jwt-secret-key":
            raise ValueError("JWT_SECRET_KEY must be set to a strong secret")
        return v


settings = Settings()
