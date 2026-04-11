from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import json
import logging
from pydantic import ValidationError as PydanticValidationError

from app.api.dependencies import get_db, get_current_admin
from app.core.exceptions import NotFoundError, ValidationError
from app.models.user import User
from app.schemas.merchant import (
    MerchantCreate,
    MerchantIntentCreate,
    MerchantIntentResponse,
    MerchantResponse
)
from app.services.merchant import MerchantService

router = APIRouter(prefix="/merchants", tags=["merchants"])
logger = logging.getLogger(__name__)

@router.post("/", response_model=MerchantResponse)
async def create_merchant(
    merchant_data: MerchantCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: Create a new merchant integration with API credentials."""
    service = MerchantService(db)
    return await service.create_merchant(merchant_data)

@router.post("/intents", response_model=MerchantIntentResponse)
async def create_checkout_intent(
    request: Request,
    merchant_id: str = Header(..., alias="X-Avok-Merchant-Id"),
    merchant_signature: str = Header(..., alias="X-Avok-Signature"),
    merchant_secret: Optional[str] = Header(None, alias="X-Avok-Merchant-Secret"),
    db: AsyncSession = Depends(get_db),
):
    """
    Merchant API: Create a signed checkout intent.
    Expects JSON body and HMAC-SHA256 signature in headers.
    """
    service = MerchantService(db)
    try:
        raw_body = await request.body()
        payload_data = json.loads(raw_body.decode("utf-8"))
        intent_data = MerchantIntentCreate.model_validate(payload_data)
        
        canonical_payload = MerchantService._canonicalize_payload(payload_data)
        
        return await service.create_checkout_intent(
            merchant_id=merchant_id,
            signature=merchant_signature,
            payload=intent_data,
            canonical_payload=canonical_payload,
            provided_secret_key=merchant_secret,
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")
    except PydanticValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors())
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
