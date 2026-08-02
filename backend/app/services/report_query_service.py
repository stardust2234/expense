from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Expense, TransactionStatus
from app.services.cash_flow import spending_contribution

PRIORITY_ORDER = {
    priority: index
    for index, priority in enumerate(
        ("protected", "essential", "adjustable", "irregular_essential", "optional", "transfer")
    )
}
MAX_REPORT_ROWS = 50_000
MAX_REPORT_RANGE_DAYS = 3660


@dataclass(frozen=True)
class CategoryTotalRecord:
    category_id: int
    category_code: str | None
    category_name: str
    currency: str
    total_amount: int
    transaction_count: int


@dataclass(frozen=True)
class PriorityTotalRecord:
    priority: str
    currency: str
    total_amount: int
    transaction_count: int


def validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValueError("date_from must be on or before date_to")
    if (
        date_from is not None
        and date_to is not None
        and (date_to - date_from).days > MAX_REPORT_RANGE_DAYS
    ):
        raise ValueError(f"Report date range must not exceed {MAX_REPORT_RANGE_DAYS} days")


def report_expenses(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> list[Expense]:
    validate_date_range(date_from, date_to)
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
    expenses = list(
        session.scalars(
            statement.order_by(Expense.transaction_date, Expense.id).limit(MAX_REPORT_ROWS + 1)
        ).all()
    )
    if len(expenses) > MAX_REPORT_ROWS:
        raise ValueError(
            f"Report contains more than {MAX_REPORT_ROWS} transactions; use a narrower date range"
        )
    return expenses


def get_category_totals(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> list[CategoryTotalRecord]:
    validate_date_range(date_from, date_to)
    totals: defaultdict[tuple[int, str | None, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for expense in report_expenses(
        session, date_from=date_from, date_to=date_to, currency=currency
    ):
        if expense.category is None:
            continue
        contribution = spending_contribution(expense.amount, expense.category)
        if contribution is None:
            continue
        bucket = totals[
            (expense.category.id, expense.category.code, expense.category.name, expense.currency)
        ]
        bucket[0] += contribution
        bucket[1] += 1
    return [
        CategoryTotalRecord(category_id, code, name, row_currency, values[0], values[1])
        for (category_id, code, name, row_currency), values in sorted(
            totals.items(), key=lambda item: (item[0][3], item[0][2].casefold(), item[0][0])
        )
    ]


def get_priority_totals(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> list[PriorityTotalRecord]:
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
        priority = (expense.priority_override or expense.category.default_priority).value
        bucket = totals[(priority, expense.currency)]
        bucket[0] += contribution
        bucket[1] += 1
    return [
        PriorityTotalRecord(priority, row_currency, values[0], values[1])
        for (priority, row_currency), values in sorted(
            totals.items(), key=lambda item: (PRIORITY_ORDER.get(item[0][0], 99), item[0][1])
        )
    ]
