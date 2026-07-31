import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AllowanceType,
    Category,
    Commitment,
    CommitmentStatus,
    CycleAllowance,
    Expense,
    PaymentCycle,
    SpendingPriority,
)
from app.services.payment_cycle_service import (
    FinancialPlanConflictError,
    get_payment_cycle,
)
from app.services.safe_spending_forecast import (
    ForecastAllowance,
    ForecastCommitment,
    SafeSpendingForecast,
    calculate_safe_spending,
)


class AllowanceNotFoundError(LookupError):
    pass


def get_allowance(session: Session, allowance_id: int) -> CycleAllowance:
    allowance = session.get(CycleAllowance, allowance_id)
    if allowance is None:
        raise AllowanceNotFoundError(f"Allowance {allowance_id} was not found")
    return allowance


def list_allowances(session: Session, *, payment_cycle_id: int) -> list[CycleAllowance]:
    get_payment_cycle(session, payment_cycle_id)
    return list(
        session.scalars(
            select(CycleAllowance)
            .where(CycleAllowance.payment_cycle_id == payment_cycle_id)
            .order_by(CycleAllowance.id)
        ).all()
    )


def create_allowance(
    session: Session,
    *,
    payment_cycle_id: int,
    name: str,
    allowance_type: AllowanceType,
    amount: int,
    priority: SpendingPriority,
    category_id: int | None,
) -> CycleAllowance:
    cycle = get_payment_cycle(session, payment_cycle_id)
    _validate_category(session, category_id)
    _ensure_available_slot(
        session,
        payment_cycle_id=cycle.id,
        allowance_type=allowance_type,
        category_id=category_id,
    )
    allowance = CycleAllowance(
        payment_cycle=cycle,
        name=name,
        allowance_type=allowance_type,
        amount=amount,
        priority=priority,
        category_id=category_id,
    )
    session.add(allowance)
    session.commit()
    return allowance


def update_allowance(
    session: Session,
    *,
    allowance_id: int,
    changes: dict[str, object],
) -> CycleAllowance:
    allowance = get_allowance(session, allowance_id)
    allowance_type = changes.get("allowance_type", allowance.allowance_type)
    category_id = changes.get("category_id", allowance.category_id)
    assert isinstance(allowance_type, AllowanceType)
    assert category_id is None or isinstance(category_id, int)
    _validate_category(session, category_id)
    _ensure_available_slot(
        session,
        payment_cycle_id=allowance.payment_cycle_id,
        allowance_type=allowance_type,
        category_id=category_id,
        exclude_allowance_id=allowance.id,
    )
    for field, value in changes.items():
        setattr(allowance, field, value)
    session.commit()
    return allowance


def delete_allowance(session: Session, *, allowance_id: int) -> None:
    allowance = get_allowance(session, allowance_id)
    session.delete(allowance)
    session.commit()


def build_cycle_forecast(
    session: Session,
    *,
    payment_cycle_id: int,
    as_of_date: date | None = None,
) -> tuple[SafeSpendingForecast, str, str]:
    cycle = get_payment_cycle(session, payment_cycle_id)
    effective_date = as_of_date or datetime.now(ZoneInfo("Europe/London")).date()
    next_income_date = _next_income_date(
        cycle.next_payment_date,
        effective_date,
        period_end=cycle.end_date,
    )
    income_cycle = session.scalar(
        select(PaymentCycle).where(
            PaymentCycle.currency == cycle.currency,
            PaymentCycle.next_payment_date == next_income_date,
        )
    )
    expected_income_amount = (
        income_cycle.expected_income_amount
        if income_cycle is not None
        else cycle.expected_income_amount
    )
    balance_source = "current" if cycle.current_balance is not None else "opening"
    expenses = list(
        session.scalars(
            select(Expense).where(
                Expense.payment_cycle_id == cycle.id,
                Expense.transaction_date <= effective_date,
            )
        ).all()
    )
    usable_balance = (
        cycle.current_balance
        if cycle.current_balance is not None
        else cycle.opening_balance + sum(expense.amount for expense in expenses)
    )
    commitment_rows = session.scalars(
        select(Commitment).where(
            Commitment.currency == cycle.currency,
            Commitment.status == CommitmentStatus.PENDING,
            Commitment.due_date >= cycle.start_date,
            Commitment.due_date < next_income_date,
        )
    ).all()
    pending_commitments = tuple(
        ForecastCommitment(
            amount=commitment.amount,
            priority=commitment.priority.value,
        )
        for commitment in commitment_rows
    )
    allowance_rows = session.scalars(
        select(CycleAllowance)
        .join(PaymentCycle)
        .where(
            PaymentCycle.currency == cycle.currency,
            PaymentCycle.start_date < next_income_date,
            PaymentCycle.end_date > effective_date,
        )
    ).all()
    forecast_allowances = tuple(
        ForecastAllowance(
            id=allowance.id,
            name=allowance.name,
            allowance_type=allowance.allowance_type.value,
            priority=allowance.priority.value,
            amount=allowance.amount,
            spent_amount=_allowance_spending(allowance, expenses),
        )
        for allowance in allowance_rows
    )
    forecast = calculate_safe_spending(
        as_of_date=effective_date,
        next_payment_date=next_income_date,
        usable_balance=usable_balance,
        expected_income_amount=expected_income_amount,
        pending_commitments=pending_commitments,
        allowances=forecast_allowances,
    )
    return forecast, balance_source, cycle.currency


def _next_income_date(scheduled_date: date, as_of_date: date, *, period_end: date) -> date:
    if as_of_date >= period_end:
        return scheduled_date
    candidate = scheduled_date
    while candidate < as_of_date:
        next_month = candidate.month % 12 + 1
        next_year = candidate.year + (1 if candidate.month == 12 else 0)
        candidate = date(
            next_year,
            next_month,
            min(candidate.day, calendar.monthrange(next_year, next_month)[1]),
        )
    return candidate


def _allowance_spending(
    allowance: CycleAllowance,
    expenses: list[Expense],
) -> int:
    if allowance.category_id is None:
        return 0
    net_outflow = sum(
        -expense.amount for expense in expenses if expense.category_id == allowance.category_id
    )
    return max(net_outflow, 0)


def _validate_category(session: Session, category_id: int | None) -> None:
    if category_id is not None and session.get(Category, category_id) is None:
        raise FinancialPlanConflictError(f"Category {category_id} was not found")


def _ensure_available_slot(
    session: Session,
    *,
    payment_cycle_id: int,
    allowance_type: AllowanceType,
    category_id: int | None,
    exclude_allowance_id: int | None = None,
) -> None:
    statement = select(CycleAllowance.id).where(CycleAllowance.payment_cycle_id == payment_cycle_id)
    if category_id is None:
        statement = statement.where(
            CycleAllowance.category_id.is_(None),
            CycleAllowance.allowance_type == allowance_type,
        )
    else:
        statement = statement.where(CycleAllowance.category_id == category_id)
    if exclude_allowance_id is not None:
        statement = statement.where(CycleAllowance.id != exclude_allowance_id)
    if session.scalar(statement) is not None:
        target = (
            f"category {category_id}"
            if category_id is not None
            else f"type {allowance_type.value!r}"
        )
        raise FinancialPlanConflictError(f"Payment cycle already has an allowance for {target}")
