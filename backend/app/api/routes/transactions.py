from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.models import Expense, TransactionStatus
from app.schemas.transactions import (
    TransactionBulkUpdateRequest,
    TransactionBulkUpdateResponse,
    TransactionItem,
    TransactionListResponse,
)
from app.services.transaction_service import (
    TransactionConflictError,
    bulk_assign_category,
    list_transactions,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _item(expense: Expense) -> TransactionItem:
    return TransactionItem(
        id=expense.id,
        transaction_date=expense.transaction_date,
        description=expense.description,
        normalised_description=expense.normalised_description,
        amount=expense.amount,
        currency=expense.currency,
        status=expense.status,
        merchant_id=expense.merchant_id,
        merchant_name=expense.merchant.name if expense.merchant else None,
        category_id=expense.category_id,
        category_name=expense.category.name if expense.category else None,
        confidence_score=expense.confidence_score,
    )


@router.get("", response_model=TransactionListResponse)
async def get_transactions(
    session: DatabaseSession,
    search: str | None = None,
    transaction_status: Annotated[
        TransactionStatus | None,
        Query(alias="status"),
    ] = None,
    category_id: Annotated[int | None, Query(gt=0)] = None,
    merchant_id: Annotated[int | None, Query(gt=0)] = None,
    import_batch_id: Annotated[int | None, Query(gt=0)] = None,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionListResponse:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from must be on or before date_to",
        )
    page = list_transactions(
        session,
        search=search,
        status=transaction_status,
        category_id=category_id,
        merchant_id=merchant_id,
        import_batch_id=import_batch_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return TransactionListResponse(
        items=[_item(expense) for expense in page.items],
        total=page.total,
        limit=limit,
        offset=offset,
    )


@router.patch("/bulk", response_model=TransactionBulkUpdateResponse)
async def patch_transactions(
    request: TransactionBulkUpdateRequest,
    session: DatabaseSession,
) -> TransactionBulkUpdateResponse:
    try:
        updated = bulk_assign_category(
            session,
            transaction_ids=request.transaction_ids,
            category_id=request.category_id,
        )
    except TransactionConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return TransactionBulkUpdateResponse(updated=updated)
