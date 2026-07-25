import calendar
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    Category,
    Commitment,
    CommitmentStatus,
    Expense,
    PaymentCycle,
    PaymentCycleStatus,
    SpendingPriority,
)


class PaymentCycleNotFoundError(LookupError):
    pass


class CommitmentNotFoundError(LookupError):
    pass


class FinancialPlanConflictError(ValueError):
    pass


def list_payment_cycles(
    session: Session,
    *,
    limit: int,
    offset: int,
    status: PaymentCycleStatus | None,
) -> tuple[list[PaymentCycle], int]:
    filters = [PaymentCycle.status == status] if status is not None else []
    total = session.scalar(select(func.count(PaymentCycle.id)).where(*filters)) or 0
    cycles = list(
        session.scalars(
            select(PaymentCycle)
            .where(*filters)
            .order_by(PaymentCycle.start_date.desc(), PaymentCycle.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return cycles, total


def get_payment_cycle(session: Session, payment_cycle_id: int) -> PaymentCycle:
    cycle = session.get(PaymentCycle, payment_cycle_id)
    if cycle is None:
        raise PaymentCycleNotFoundError(f"Payment cycle {payment_cycle_id} was not found")
    return cycle


def create_payment_cycle(
    session: Session,
    *,
    name: str | None,
    start_date: date,
    next_payment_date: date,
    expected_income_amount: int,
    currency: str,
    opening_balance: int,
    current_balance: int | None,
    status: PaymentCycleStatus,
) -> PaymentCycle:
    _ensure_no_overlap(
        session,
        start_date=start_date,
        next_payment_date=next_payment_date,
        currency=currency,
    )
    cycle = PaymentCycle(
        name=name,
        start_date=start_date,
        next_payment_date=next_payment_date,
        expected_income_amount=expected_income_amount,
        currency=currency,
        opening_balance=opening_balance,
        current_balance=current_balance,
        status=status,
    )
    session.add(cycle)
    session.flush()
    _sync_cycle_expenses(session, cycle)
    _generate_recurring_commitments(session, cycle)
    session.commit()
    return cycle


def update_payment_cycle(
    session: Session,
    *,
    payment_cycle_id: int,
    changes: dict[str, object],
) -> PaymentCycle:
    cycle = get_payment_cycle(session, payment_cycle_id)
    start_date = changes.get("start_date", cycle.start_date)
    next_payment_date = changes.get("next_payment_date", cycle.next_payment_date)
    currency = changes.get("currency", cycle.currency)
    assert isinstance(start_date, date)
    assert isinstance(next_payment_date, date)
    assert isinstance(currency, str)
    if next_payment_date <= start_date:
        raise FinancialPlanConflictError("next_payment_date must be after start_date")
    _ensure_no_overlap(
        session,
        start_date=start_date,
        next_payment_date=next_payment_date,
        currency=currency,
        exclude_cycle_id=cycle.id,
    )
    if currency != cycle.currency and cycle.commitments:
        raise FinancialPlanConflictError("A payment cycle with commitments cannot change currency")
    if any(
        not start_date <= commitment.due_date < next_payment_date
        for commitment in cycle.commitments
    ):
        raise FinancialPlanConflictError(
            "Payment cycle dates must continue to include every commitment"
        )
    for field, value in changes.items():
        setattr(cycle, field, value)
    _sync_cycle_expenses(session, cycle)
    session.commit()
    return cycle


def delete_payment_cycle(session: Session, *, payment_cycle_id: int) -> None:
    cycle = get_payment_cycle(session, payment_cycle_id)
    session.delete(cycle)
    session.commit()


def list_commitments(session: Session, *, payment_cycle_id: int) -> list[Commitment]:
    get_payment_cycle(session, payment_cycle_id)
    return list(
        session.scalars(
            select(Commitment)
            .where(Commitment.payment_cycle_id == payment_cycle_id)
            .order_by(Commitment.due_date, Commitment.id)
        ).all()
    )


def create_commitment(
    session: Session,
    *,
    payment_cycle_id: int,
    name: str,
    amount: int,
    currency: str | None,
    due_date: date,
    priority: SpendingPriority,
    category_id: int | None,
    status: CommitmentStatus,
    recurrence: str | None,
) -> Commitment:
    hinted_cycle = get_payment_cycle(session, payment_cycle_id)
    commitment_currency = currency or hinted_cycle.currency
    cycle = _cycle_for_due_date(
        session,
        due_date=due_date,
        currency=commitment_currency,
    )
    _validate_commitment(
        session,
        cycle=cycle,
        due_date=due_date,
        currency=commitment_currency,
        category_id=category_id,
    )
    commitment = Commitment(
        payment_cycle=cycle,
        name=name,
        amount=amount,
        currency=commitment_currency,
        due_date=due_date,
        priority=priority,
        category_id=category_id,
        status=status,
        recurrence=recurrence,
    )
    session.add(commitment)
    session.commit()
    return commitment


def update_commitment(
    session: Session,
    *,
    commitment_id: int,
    changes: dict[str, object],
) -> Commitment:
    commitment = session.get(Commitment, commitment_id)
    if commitment is None:
        raise CommitmentNotFoundError(f"Commitment {commitment_id} was not found")
    due_date = changes.get("due_date", commitment.due_date)
    currency = changes.get("currency", commitment.currency)
    category_id = changes.get("category_id", commitment.category_id)
    assert isinstance(due_date, date)
    assert isinstance(currency, str)
    assert category_id is None or isinstance(category_id, int)
    cycle = _cycle_for_due_date(
        session,
        due_date=due_date,
        currency=currency,
    )
    _validate_commitment(
        session,
        cycle=cycle,
        due_date=due_date,
        currency=currency,
        category_id=category_id,
    )
    commitment.payment_cycle = cycle
    for field, value in changes.items():
        setattr(commitment, field, value)
    session.commit()
    return commitment


def delete_commitment(session: Session, *, commitment_id: int) -> None:
    commitment = session.get(Commitment, commitment_id)
    if commitment is None:
        raise CommitmentNotFoundError(f"Commitment {commitment_id} was not found")
    session.delete(commitment)
    session.commit()


def _ensure_no_overlap(
    session: Session,
    *,
    start_date: date,
    next_payment_date: date,
    currency: str,
    exclude_cycle_id: int | None = None,
) -> None:
    statement = select(PaymentCycle.id).where(
        PaymentCycle.currency == currency,
        PaymentCycle.start_date < next_payment_date,
        PaymentCycle.next_payment_date > start_date,
    )
    if exclude_cycle_id is not None:
        statement = statement.where(PaymentCycle.id != exclude_cycle_id)
    if session.scalar(statement) is not None:
        raise FinancialPlanConflictError(f"Payment cycle overlaps another {currency} cycle")


def _validate_commitment(
    session: Session,
    *,
    cycle: PaymentCycle,
    due_date: date,
    currency: str,
    category_id: int | None,
) -> None:
    if not cycle.start_date <= due_date < cycle.next_payment_date:
        raise FinancialPlanConflictError("Commitment due_date must fall within its payment cycle")
    if currency != cycle.currency:
        raise FinancialPlanConflictError("Commitment currency must match its payment cycle")
    if category_id is not None and session.get(Category, category_id) is None:
        raise FinancialPlanConflictError(f"Category {category_id} was not found")


def _cycle_for_due_date(
    session: Session,
    *,
    due_date: date,
    currency: str,
) -> PaymentCycle:
    cycle = session.scalar(
        select(PaymentCycle)
        .where(
            PaymentCycle.currency == currency,
            PaymentCycle.start_date <= due_date,
            PaymentCycle.next_payment_date > due_date,
        )
        .order_by(PaymentCycle.start_date.desc())
    )
    if cycle is None:
        raise FinancialPlanConflictError(
            f"No {currency} payment cycle covers commitment due date {due_date.isoformat()}"
        )
    return cycle


def _add_month(value: date) -> date:
    month_index = value.month
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _generate_recurring_commitments(session: Session, cycle: PaymentCycle) -> None:
    previous_cycle = session.scalar(
        select(PaymentCycle).where(
            PaymentCycle.currency == cycle.currency,
            PaymentCycle.next_payment_date == cycle.start_date,
            PaymentCycle.id != cycle.id,
        )
    )
    if previous_cycle is None:
        return

    recurring = session.scalars(
        select(Commitment)
        .where(
            Commitment.payment_cycle_id == previous_cycle.id,
            func.lower(Commitment.recurrence) == "monthly",
        )
        .order_by(Commitment.id)
    )
    for source in recurring:
        next_due_date = _add_month(source.due_date)
        while next_due_date < cycle.start_date:
            next_due_date = _add_month(next_due_date)
        if next_due_date >= cycle.next_payment_date:
            continue
        session.add(
            Commitment(
                payment_cycle=cycle,
                name=source.name,
                amount=source.amount,
                currency=source.currency,
                due_date=next_due_date,
                priority=source.priority,
                category_id=source.category_id,
                status=CommitmentStatus.PENDING,
                recurrence=source.recurrence,
            )
        )


def _sync_cycle_expenses(session: Session, cycle: PaymentCycle) -> None:
    session.execute(
        update(Expense)
        .where(
            Expense.payment_cycle_id == cycle.id,
            (
                (Expense.currency != cycle.currency)
                | (Expense.transaction_date < cycle.start_date)
                | (Expense.transaction_date >= cycle.next_payment_date)
            ),
        )
        .values(payment_cycle_id=None)
    )
    session.execute(
        update(Expense)
        .where(
            Expense.payment_cycle_id.is_(None),
            Expense.currency == cycle.currency,
            Expense.transaction_date >= cycle.start_date,
            Expense.transaction_date < cycle.next_payment_date,
        )
        .values(payment_cycle_id=cycle.id)
    )
