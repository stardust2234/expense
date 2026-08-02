from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Expense, PaymentCycle, SpendingPriority, TransactionStatus
from app.services.cash_flow import CashFlowKind, cash_flow_kind, spending_contribution
from app.services.report_query_service import MAX_REPORT_ROWS

MAX_PAYMENT_PERIODS = 240


@dataclass(frozen=True)
class PaymentPeriodRecord:
    payment_cycle_id: int
    name: str | None
    start_date: date
    end_date: date
    next_payment_date: date
    currency: str
    status: str
    income: int
    spending: int
    net: int
    transaction_count: int
    protected_spending: int
    essential_spending: int
    adjustable_spending: int
    optional_spending: int
    irregular_essential_spending: int


def get_payment_periods(
    session: Session, *, currency: str | None = None
) -> list[PaymentPeriodRecord]:
    cycle_filter = []
    if currency is not None:
        cycle_filter.append(PaymentCycle.currency == currency.upper())
    cycle_count = session.scalar(select(func.count(PaymentCycle.id)).where(*cycle_filter)) or 0
    if cycle_count > MAX_PAYMENT_PERIODS:
        raise ValueError(f"Payment-period report contains more than {MAX_PAYMENT_PERIODS} periods")
    expense_count = (
        session.scalar(
            select(func.count(Expense.id))
            .join(PaymentCycle, Expense.payment_cycle_id == PaymentCycle.id)
            .where(*cycle_filter)
        )
        or 0
    )
    if expense_count > MAX_REPORT_ROWS:
        raise ValueError(f"Payment-period report contains more than {MAX_REPORT_ROWS} transactions")
    statement = select(PaymentCycle).options(
        selectinload(PaymentCycle.expenses)
        .selectinload(Expense.category)
        .selectinload(Category.parent)
    )
    statement = statement.where(*cycle_filter)
    records: list[PaymentPeriodRecord] = []
    for cycle in session.scalars(
        statement.order_by(PaymentCycle.start_date, PaymentCycle.id)
    ).all():
        income = spending = transaction_count = 0
        priority_totals: defaultdict[SpendingPriority, int] = defaultdict(int)
        for expense in cycle.expenses:
            if expense.status is not TransactionStatus.CATEGORISED or expense.category is None:
                continue
            kind = cash_flow_kind(expense.category)
            if kind is CashFlowKind.TRANSFER:
                continue
            transaction_count += 1
            if kind is CashFlowKind.INCOME:
                income += expense.amount
                continue
            contribution = spending_contribution(expense.amount, expense.category)
            if contribution is None:
                continue
            spending += contribution
            priority_totals[expense.priority_override or expense.category.default_priority] += (
                contribution
            )
        records.append(
            PaymentPeriodRecord(
                cycle.id,
                cycle.name,
                cycle.start_date,
                cycle.end_date,
                cycle.next_payment_date,
                cycle.currency,
                cycle.status.value,
                income,
                spending,
                income - spending,
                transaction_count,
                priority_totals[SpendingPriority.PROTECTED],
                priority_totals[SpendingPriority.ESSENTIAL],
                priority_totals[SpendingPriority.ADJUSTABLE],
                priority_totals[SpendingPriority.OPTIONAL],
                priority_totals[SpendingPriority.IRREGULAR_ESSENTIAL],
            )
        )
    return records
