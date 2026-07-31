from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Expense, TransactionStatus
from app.services.cash_flow import spending_contribution


@dataclass(frozen=True)
class CategoryTotalRecord:
    category_id: int
    category_name: str
    currency: str
    total_amount: int
    transaction_count: int


@dataclass(frozen=True)
class MonthlyTotalRecord:
    month: str
    currency: str
    total_amount: int
    transaction_count: int


def validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValueError("date_from must be on or before date_to")


def report_expenses(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> list[Expense]:
    statement = (
        select(Expense)
        .where(Expense.status == TransactionStatus.CATEGORISED)
        .options(
            selectinload(Expense.category).selectinload(Category.parent),
            selectinload(Expense.merchant),
        )
    )
    if date_from is not None:
        statement = statement.where(Expense.transaction_date >= date_from)
    if date_to is not None:
        statement = statement.where(Expense.transaction_date <= date_to)
    if currency is not None:
        statement = statement.where(Expense.currency == currency.upper())
    return list(session.scalars(statement.order_by(Expense.transaction_date, Expense.id)).all())


def get_category_totals(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> list[CategoryTotalRecord]:
    validate_date_range(date_from, date_to)
    totals: defaultdict[tuple[int, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for expense in report_expenses(
        session, date_from=date_from, date_to=date_to, currency=currency
    ):
        if expense.category is None:
            continue
        contribution = spending_contribution(expense.amount, expense.category)
        if contribution is None:
            continue
        bucket = totals[(expense.category.id, expense.category.name, expense.currency)]
        bucket[0] += contribution
        bucket[1] += 1
    return [
        CategoryTotalRecord(category_id, name, row_currency, values[0], values[1])
        for (category_id, name, row_currency), values in sorted(
            totals.items(), key=lambda item: (item[0][2], item[0][1].casefold(), item[0][0])
        )
    ]


def get_monthly_totals(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> list[MonthlyTotalRecord]:
    validate_date_range(date_from, date_to)
    totals: defaultdict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for expense in report_expenses(
        session, date_from=date_from, date_to=date_to, currency=currency
    ):
        if expense.category is None:
            continue
        contribution = spending_contribution(expense.amount, expense.category)
        if contribution is None:
            continue
        bucket = totals[(expense.transaction_date.strftime("%Y-%m"), expense.currency)]
        bucket[0] += contribution
        bucket[1] += 1
    return [
        MonthlyTotalRecord(month, row_currency, values[0], values[1])
        for (month, row_currency), values in sorted(totals.items())
    ]
