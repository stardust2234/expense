from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AllowanceType,
    Category,
    Commitment,
    CommitmentStatus,
    CycleAllowance,
    Expense,
    PaymentCycle,
    SpendingPriority,
    TransactionStatus,
)
from app.services.cash_flow import CashFlowKind, cash_flow_kind
from app.services.funding_window import (
    FundingWindow,
    IncomeScheduleItem,
    resolve_funding_window,
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


@dataclass(frozen=True)
class BuiltCycleForecast:
    forecast: SafeSpendingForecast
    balance_source: str
    currency: str
    funding_window: FundingWindow


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
) -> BuiltCycleForecast:
    cycle = get_payment_cycle(session, payment_cycle_id)
    today = datetime.now(ZoneInfo("Europe/London")).date()
    window_reference_date, requested_effective_date = _forecast_dates(
        cycle,
        requested_date=as_of_date,
        today=today,
    )
    income_cycles = tuple(
        session.scalars(
            select(PaymentCycle)
            .where(PaymentCycle.currency == cycle.currency)
            .order_by(PaymentCycle.next_payment_date, PaymentCycle.id)
        ).all()
    )
    funding_window = resolve_funding_window(
        _income_schedule(session, cycles=income_cycles, currency=cycle.currency),
        as_of_date=window_reference_date,
    )
    effective_date = min(
        max(requested_effective_date, funding_window.start_date),
        funding_window.end_date - timedelta(days=1),
    )
    expenses = list(
        session.scalars(
            select(Expense)
            .where(
                Expense.currency == cycle.currency,
                Expense.transaction_date >= funding_window.start_date,
                Expense.transaction_date <= effective_date,
            )
            .options(selectinload(Expense.category).selectinload(Category.parent))
        ).all()
    )
    if cycle.current_balance is not None:
        usable_balance = cycle.current_balance
        balance_source = "current"
    else:
        imported_funding_income = any(
            expense.amount > 0
            and expense.category is not None
            and cash_flow_kind(expense.category) is CashFlowKind.INCOME
            and expense.transaction_date <= funding_window.start_date + timedelta(days=3)
            and abs(expense.amount - funding_window.funding_amount)
            <= max(100, funding_window.funding_amount // 20)
            for expense in expenses
        )
        usable_balance = sum(expense.amount for expense in expenses)
        if not imported_funding_income:
            usable_balance += funding_window.funding_amount
        balance_source = "funding_income"
    commitment_rows = session.scalars(
        select(Commitment).where(
            Commitment.currency == cycle.currency,
            Commitment.status == CommitmentStatus.PENDING,
            Commitment.due_date >= funding_window.start_date,
            Commitment.due_date < funding_window.end_date,
        )
    ).all()
    pending_commitments = tuple(
        ForecastCommitment(
            amount=commitment.amount,
            priority=commitment.priority.value,
        )
        for commitment in commitment_rows
    )
    allowance_plan_date = (
        funding_window.start_date + (funding_window.end_date - funding_window.start_date) // 2
    )
    allowance_rows = session.scalars(
        select(CycleAllowance)
        .join(PaymentCycle)
        .where(
            PaymentCycle.currency == cycle.currency,
            PaymentCycle.start_date <= allowance_plan_date,
            PaymentCycle.end_date > allowance_plan_date,
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
        next_payment_date=funding_window.end_date,
        usable_balance=usable_balance,
        expected_income_amount=funding_window.funding_amount,
        pending_commitments=pending_commitments,
        allowances=forecast_allowances,
    )
    return BuiltCycleForecast(forecast, balance_source, cycle.currency, funding_window)


def _income_schedule(
    session: Session,
    *,
    cycles: tuple[PaymentCycle, ...],
    currency: str,
) -> tuple[IncomeScheduleItem, ...]:
    planned = {
        cycle.next_payment_date: IncomeScheduleItem(
            cycle.id,
            cycle.next_payment_date,
            cycle.expected_income_amount,
        )
        for cycle in cycles
    }
    income_rows = session.scalars(
        select(Expense)
        .where(
            Expense.currency == currency,
            Expense.amount > 0,
            Expense.status == TransactionStatus.CATEGORISED,
            Expense.category_id.is_not(None),
        )
        .options(selectinload(Expense.category).selectinload(Category.parent))
        .order_by(Expense.transaction_date, Expense.id)
        .limit(1000)
    ).all()
    for expense in income_rows:
        if expense.category is None or cash_flow_kind(expense.category) is not CashFlowKind.INCOME:
            continue
        closest_cycle = min(
            cycles, key=lambda item: abs(item.expected_income_amount - expense.amount)
        )
        tolerance = max(100, closest_cycle.expected_income_amount // 20)
        if abs(closest_cycle.expected_income_amount - expense.amount) > tolerance:
            continue
        planned[expense.transaction_date] = IncomeScheduleItem(
            expense.payment_cycle_id or closest_cycle.id,
            expense.transaction_date,
            expense.amount,
        )
    return tuple(planned.values())


def _forecast_dates(
    cycle: PaymentCycle,
    *,
    requested_date: date | None,
    today: date,
) -> tuple[date, date]:
    if requested_date is not None:
        return requested_date, requested_date
    if today < cycle.start_date:
        return cycle.start_date, cycle.start_date
    if today >= cycle.end_date:
        return cycle.start_date, cycle.end_date - timedelta(days=1)
    return today, today


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
