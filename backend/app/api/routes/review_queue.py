from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.review_queue import ReviewQueueItem, ReviewQueueResponse
from app.schemas.review_resolution import (
    ReviewResolutionRequest,
    ReviewResolutionResponse,
)
from app.services.review_queue_service import get_review_queue
from app.services.review_resolution_service import (
    CategoryNotFoundError,
    ExpenseNotFoundError,
    ExpenseNotReviewableError,
    resolve_review,
)

router = APIRouter(tags=["review"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


@router.get("/review-queue", response_model=ReviewQueueResponse)
async def list_review_queue(
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReviewQueueResponse:
    page = get_review_queue(session, limit=limit, offset=offset)
    return ReviewQueueResponse(
        items=[ReviewQueueItem.from_expense(expense) for expense in page.items],
        total=page.total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/review-queue/{expense_id}/resolve",
    response_model=ReviewResolutionResponse,
)
async def resolve_review_item(
    expense_id: int,
    request: ReviewResolutionRequest,
    session: DatabaseSession,
) -> ReviewResolutionResponse:
    try:
        resolution = resolve_review(
            session,
            expense_id=expense_id,
            category_id=request.category_id,
            save_rule=request.save_rule,
            match_pattern=request.match_pattern,
            priority=request.priority,
        )
    except (ExpenseNotFoundError, CategoryNotFoundError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ExpenseNotReviewableError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ReviewResolutionResponse(
        expense_id=resolution.expense_id,
        category_id=resolution.category_id,
        rule_id=resolution.rule_id,
        status=resolution.status,
    )
