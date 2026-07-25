from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Expense, TransactionStatus
from app.services.cash_flow import CashFlowKind, cash_flow_kind, spending_contribution
from app.services.report_service import CategoryTotalRecord


@dataclass(frozen=True)
class DashboardRecord:
    month: str
    spending: int
    income: int
    net: int
    currency: str
    review_count: int
    transaction_count: int
    category_totals: list[CategoryTotalRecord]


def get_dashboard(
    session: Session,
    *,
    currency: str = "GBP",
    month: date | None = None,
) -> DashboardRecord:
    current = month or datetime.now(UTC).date()
    month_start = current.replace(day=1)
    next_month = (
        month_start.replace(year=month_start.year + 1, month=1)
        if month_start.month == 12
        else month_start.replace(month=month_start.month + 1)
    )
    currency = currency.upper()
    expenses = session.scalars(
        select(Expense)
        .where(
            Expense.status == TransactionStatus.CATEGORISED,
            Expense.currency == currency,
            Expense.transaction_date >= month_start,
            Expense.transaction_date < next_month,
        )
        .options(
            selectinload(Expense.category).selectinload(Category.parent),
        )
    ).all()

    income = 0
    spending = 0
    totals: defaultdict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0])
    transaction_count = 0
    for expense in expenses:
        category = expense.category
        if category is None:
            continue
        kind = cash_flow_kind(category)
        if kind is CashFlowKind.TRANSFER:
            continue
        transaction_count += 1
        if kind is CashFlowKind.INCOME:
            income += expense.amount
        else:
            contribution = spending_contribution(expense.amount, category)
            if contribution is not None:
                spending += contribution
                bucket = totals[(category.id, category.name)]
                bucket[0] += contribution
                bucket[1] += 1

    review_count = (
        session.scalar(
            select(func.count())
            .select_from(Expense)
            .where(
                Expense.status == TransactionStatus.NEEDS_REVIEW,
                Expense.currency == currency,
                Expense.transaction_date >= month_start,
                Expense.transaction_date < next_month,
            )
        )
        or 0
    )
    category_totals = [
        CategoryTotalRecord(
            category_id=category_id,
            category_name=name,
            currency=currency,
            total_amount=values[0],
            transaction_count=values[1],
        )
        for (category_id, name), values in sorted(
            totals.items(), key=lambda item: item[1][0], reverse=True
        )
    ]
    return DashboardRecord(
        month=month_start.strftime("%Y-%m"),
        spending=spending,
        income=income,
        net=income - spending,
        currency=currency,
        review_count=review_count,
        transaction_count=transaction_count,
        category_totals=category_totals,
    )
