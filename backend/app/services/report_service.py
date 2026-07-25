from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from statistics import median

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


@dataclass(frozen=True)
class RecurringExpenseRecord:
    description: str
    currency: str
    average_amount: int
    occurrence_count: int
    cadence: str
    typical_interval_days: int
    last_seen: date


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValueError("date_from must be on or before date_to")


def _report_expenses(
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
    _validate_date_range(date_from, date_to)
    totals: defaultdict[tuple[int, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for expense in _report_expenses(
        session,
        date_from=date_from,
        date_to=date_to,
        currency=currency,
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
        CategoryTotalRecord(
            category_id=category_id,
            category_name=category_name,
            currency=row_currency,
            total_amount=values[0],
            transaction_count=values[1],
        )
        for (category_id, category_name, row_currency), values in sorted(
            totals.items(),
            key=lambda item: (item[0][2], item[0][1].casefold(), item[0][0]),
        )
    ]


def get_monthly_totals(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> list[MonthlyTotalRecord]:
    _validate_date_range(date_from, date_to)
    totals: defaultdict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for expense in _report_expenses(
        session,
        date_from=date_from,
        date_to=date_to,
        currency=currency,
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
        MonthlyTotalRecord(
            month=month,
            currency=row_currency,
            total_amount=values[0],
            transaction_count=values[1],
        )
        for (month, row_currency), values in sorted(totals.items())
    ]


def get_recurring_expenses(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> list[RecurringExpenseRecord]:
    _validate_date_range(date_from, date_to)
    groups: defaultdict[tuple[str, int | str, str], list[Expense]] = defaultdict(list)
    for expense in _report_expenses(
        session,
        date_from=date_from,
        date_to=date_to,
        currency=currency,
    ):
        if expense.category is None or expense.amount >= 0:
            continue
        if spending_contribution(expense.amount, expense.category) is None:
            continue
        identity: int | str = (
            expense.merchant_id
            if expense.merchant_id is not None
            else expense.normalised_description
        )
        identity_type = "merchant" if expense.merchant_id is not None else "description"
        groups[(identity_type, identity, expense.currency)].append(expense)

    records: list[RecurringExpenseRecord] = []
    for expenses in groups.values():
        record = _recurring_record(expenses)
        if record is not None:
            records.append(record)
    return sorted(records, key=lambda item: (-item.occurrence_count, item.description))


def _recurring_record(expenses: list[Expense]) -> RecurringExpenseRecord | None:
    if len(expenses) < 3:
        return None

    median_amount = median(-expense.amount for expense in expenses)
    amount_tolerance = max(100, median_amount * 0.10)
    stable = [
        expense
        for expense in expenses
        if abs((-expense.amount) - median_amount) <= amount_tolerance
    ]

    by_date: dict[date, Expense] = {}
    for expense in stable:
        existing = by_date.get(expense.transaction_date)
        if existing is None or abs((-expense.amount) - median_amount) < abs(
            (-existing.amount) - median_amount
        ):
            by_date[expense.transaction_date] = expense
    stable = [by_date[row_date] for row_date in sorted(by_date)]
    if len(stable) < 3:
        return None

    intervals = [
        (current.transaction_date - previous.transaction_date).days
        for previous, current in pairwise(stable)
    ]
    typical_interval = round(median(intervals))
    cadence = _cadence(intervals, typical_interval)
    if cadence is None:
        return None

    description = (
        stable[0].merchant.name
        if stable[0].merchant is not None
        else stable[0].normalised_description
    )
    return RecurringExpenseRecord(
        description=description,
        currency=stable[0].currency,
        average_amount=round(sum(-expense.amount for expense in stable) / len(stable)),
        occurrence_count=len(stable),
        cadence=cadence,
        typical_interval_days=typical_interval,
        last_seen=stable[-1].transaction_date,
    )


def _cadence(intervals: list[int], typical_interval: int) -> str | None:
    candidates = (
        ("weekly", 6, 8, 5, 10),
        ("fortnightly", 13, 15, 11, 18),
        ("monthly", 25, 35, 21, 40),
        ("annual", 350, 380, 330, 400),
    )
    for name, typical_min, typical_max, interval_min, interval_max in candidates:
        if typical_min <= typical_interval <= typical_max and all(
            interval_min <= interval <= interval_max for interval in intervals
        ):
            return name
    return None
