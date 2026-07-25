from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import Expense


class ReviewQueueItem(BaseModel):
    id: int
    transaction_date: date
    description: str
    normalised_description: str
    amount: int
    currency: str
    merchant_id: int | None
    merchant_name: str | None
    category_id: int | None
    category_name: str | None
    confidence_score: Decimal | None
    source_filename: str | None
    source_row_number: int | None
    raw_data: dict[str, str | None] | None
    created_at: datetime

    @classmethod
    def from_expense(cls, expense: Expense) -> "ReviewQueueItem":
        raw_transaction = expense.raw_transaction
        return cls(
            id=expense.id,
            transaction_date=expense.transaction_date,
            description=expense.description,
            normalised_description=expense.normalised_description,
            amount=expense.amount,
            currency=expense.currency,
            merchant_id=expense.merchant_id,
            merchant_name=expense.merchant.name if expense.merchant else None,
            category_id=expense.category_id,
            category_name=expense.category.name if expense.category else None,
            confidence_score=expense.confidence_score,
            source_filename=(
                raw_transaction.import_batch.source_filename if raw_transaction else None
            ),
            source_row_number=(raw_transaction.source_row_number if raw_transaction else None),
            raw_data=raw_transaction.raw_data if raw_transaction else None,
            created_at=expense.created_at,
        )


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
