import csv
from datetime import date
from io import BytesIO, StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.models import Expense, TransactionStatus
from app.schemas.reports import (
    CategoryTotal,
    CategoryTotalsResponse,
    MonthlyReportResponse,
    MonthlyTotal,
    RecurringExpense,
    RecurringReportResponse,
)
from app.services.report_service import (
    get_category_totals,
    get_monthly_totals,
    get_recurring_expenses,
)

router = APIRouter(prefix="/reports", tags=["reports"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]
CurrencyQuery = Annotated[str | None, Query(min_length=3, max_length=3)]
SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _bad_date_range(error: ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(error),
    )


def _safe_spreadsheet_text(value: str) -> str:
    if value.lstrip().startswith(SPREADSHEET_FORMULA_PREFIXES):
        return f"'{value}"
    return value


@router.get("/category-totals", response_model=CategoryTotalsResponse)
async def category_totals(
    session: DatabaseSession,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: CurrencyQuery = None,
) -> CategoryTotalsResponse:
    try:
        records = get_category_totals(
            session,
            date_from=date_from,
            date_to=date_to,
            currency=currency,
        )
    except ValueError as error:
        raise _bad_date_range(error) from error
    return CategoryTotalsResponse(
        date_from=date_from,
        date_to=date_to,
        items=[CategoryTotal(**record.__dict__) for record in records],
    )


@router.get("/monthly", response_model=MonthlyReportResponse)
async def monthly_totals(
    session: DatabaseSession,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: CurrencyQuery = None,
) -> MonthlyReportResponse:
    try:
        records = get_monthly_totals(
            session,
            date_from=date_from,
            date_to=date_to,
            currency=currency,
        )
    except ValueError as error:
        raise _bad_date_range(error) from error
    return MonthlyReportResponse(
        date_from=date_from,
        date_to=date_to,
        items=[MonthlyTotal(**record.__dict__) for record in records],
    )


@router.get("/recurring", response_model=RecurringReportResponse)
async def recurring_expenses(
    session: DatabaseSession,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: CurrencyQuery = None,
) -> RecurringReportResponse:
    try:
        records = get_recurring_expenses(
            session,
            date_from=date_from,
            date_to=date_to,
            currency=currency,
        )
    except ValueError as error:
        raise _bad_date_range(error) from error
    return RecurringReportResponse(
        items=[RecurringExpense(**record.__dict__) for record in records]
    )


@router.get("/export")
async def export_transactions(
    session: DatabaseSession,
    export_format: Annotated[str, Query(alias="format", pattern="^(csv|xlsx)$")] = "csv",
    date_from: date | None = None,
    date_to: date | None = None,
    currency: CurrencyQuery = None,
) -> Response:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise _bad_date_range(ValueError("date_from must be on or before date_to"))
    statement = select(Expense).where(Expense.status == TransactionStatus.CATEGORISED)
    if date_from is not None:
        statement = statement.where(Expense.transaction_date >= date_from)
    if date_to is not None:
        statement = statement.where(Expense.transaction_date <= date_to)
    if currency is not None:
        statement = statement.where(Expense.currency == currency.upper())
    expenses = session.scalars(statement.order_by(Expense.transaction_date, Expense.id)).all()
    headers = ["date", "description", "amount_minor", "currency", "category_id", "merchant_id"]
    rows = [
        [
            expense.transaction_date.isoformat(),
            _safe_spreadsheet_text(expense.description),
            expense.amount,
            expense.currency,
            expense.category_id or "",
            expense.merchant_id or "",
        ]
        for expense in expenses
    ]
    if export_format == "xlsx":
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Transactions"
        worksheet.append(headers)
        for row in rows:
            worksheet.append(row)
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": 'attachment; filename="transactions.xlsx"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    output_text = StringIO()
    writer = csv.writer(output_text)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        content=output_text.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="transactions.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
