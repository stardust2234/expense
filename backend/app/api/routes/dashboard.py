from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.dashboard import DashboardSummary
from app.schemas.reports import CategoryTotal
from app.services.dashboard_service import get_dashboard

router = APIRouter(tags=["dashboard"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard(
    session: DatabaseSession,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "GBP",
    month: Annotated[date | None, Query(description="Any date in the month to display")] = None,
) -> DashboardSummary:
    record = get_dashboard(session, currency=currency, month=month)
    return DashboardSummary(
        month=record.month,
        spending=record.spending,
        income=record.income,
        net=record.net,
        currency=record.currency,
        review_count=record.review_count,
        transaction_count=record.transaction_count,
        category_totals=[CategoryTotal(**item.__dict__) for item in record.category_totals],
    )
