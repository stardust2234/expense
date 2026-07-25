from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import TransactionStatus


class TransactionItem(BaseModel):
    id: int
    transaction_date: date
    description: str
    normalised_description: str
    amount: int
    currency: str
    status: TransactionStatus
    merchant_id: int | None
    merchant_name: str | None
    category_id: int | None
    category_name: str | None
    confidence_score: Decimal | None


class TransactionListResponse(BaseModel):
    items: list[TransactionItem]
    total: int
    limit: int
    offset: int


class TransactionBulkUpdateRequest(BaseModel):
    transaction_ids: list[int] = Field(min_length=1, max_length=500)
    category_id: int = Field(gt=0)


class TransactionBulkUpdateResponse(BaseModel):
    updated: int
