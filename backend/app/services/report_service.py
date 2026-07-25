from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Category,
    Expense,
    OpportunityDecision,
    OpportunityDifficulty,
    PaymentCycle,
    RecurringCostOpportunity,
    SpendingPriority,
    TransactionStatus,
)
from app.services.cash_flow import CashFlowKind, cash_flow_kind, spending_contribution
from app.services.recurring_identity import (
    merchant_identity,
    normalise_description_identity,
    normalise_recurring_identity,
)


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
    identity_key: str
    description: str
    currency: str
    average_amount: int
    occurrence_count: int
    cadence: str
    typical_interval_days: int
    last_seen: date


@dataclass(frozen=True)
class PaymentPeriodRecord:
    payment_cycle_id: int
    name: str | None
    start_date: date
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


@dataclass(frozen=True)
class RecurringOpportunityRecord:
    opportunity_id: int | None
    identity_key: str
    description: str
    currency: str
    cadence: str
    occurrence_count: int
    last_seen: date
    current_monthly_cost: int
    replacement_monthly_cost: int | None
    one_off_switching_cost: int
    monthly_saving: int | None
    first_year_saving: int | None
    difficulty: str
    decision: str
    notes: str | None


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


def get_payment_periods(
    session: Session,
    *,
    currency: str | None = None,
) -> list[PaymentPeriodRecord]:
    statement = select(PaymentCycle).options(
        selectinload(PaymentCycle.expenses)
        .selectinload(Expense.category)
        .selectinload(Category.parent)
    )
    if currency is not None:
        statement = statement.where(PaymentCycle.currency == currency.upper())
    cycles = session.scalars(statement.order_by(PaymentCycle.start_date, PaymentCycle.id)).all()
    records: list[PaymentPeriodRecord] = []
    for cycle in cycles:
        income = 0
        spending = 0
        transaction_count = 0
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
            priority = expense.priority_override or expense.category.default_priority
            priority_totals[priority] += contribution
        records.append(
            PaymentPeriodRecord(
                payment_cycle_id=cycle.id,
                name=cycle.name,
                start_date=cycle.start_date,
                next_payment_date=cycle.next_payment_date,
                currency=cycle.currency,
                status=cycle.status.value,
                income=income,
                spending=spending,
                net=income - spending,
                transaction_count=transaction_count,
                protected_spending=priority_totals[SpendingPriority.PROTECTED],
                essential_spending=priority_totals[SpendingPriority.ESSENTIAL],
                adjustable_spending=priority_totals[SpendingPriority.ADJUSTABLE],
                optional_spending=priority_totals[SpendingPriority.OPTIONAL],
                irregular_essential_spending=priority_totals[SpendingPriority.IRREGULAR_ESSENTIAL],
            )
        )
    return records


def get_recurring_opportunities(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> list[RecurringOpportunityRecord]:
    recurring = get_recurring_expenses(
        session,
        date_from=date_from,
        date_to=date_to,
        currency=currency,
    )
    saved = {
        (item.identity_key, item.currency): item
        for item in session.scalars(select(RecurringCostOpportunity)).all()
    }
    records: list[RecurringOpportunityRecord] = []
    for item in recurring:
        opportunity = saved.get((item.identity_key, item.currency))
        current_monthly_cost = _monthly_cost(item.average_amount, item.cadence)
        replacement = opportunity.replacement_monthly_cost if opportunity is not None else None
        one_off = opportunity.one_off_switching_cost if opportunity is not None else 0
        monthly_saving = (
            max(current_monthly_cost - replacement, 0) if replacement is not None else None
        )
        records.append(
            RecurringOpportunityRecord(
                opportunity_id=opportunity.id if opportunity is not None else None,
                identity_key=item.identity_key,
                description=item.description,
                currency=item.currency,
                cadence=item.cadence,
                occurrence_count=item.occurrence_count,
                last_seen=item.last_seen,
                current_monthly_cost=current_monthly_cost,
                replacement_monthly_cost=replacement,
                one_off_switching_cost=one_off,
                monthly_saving=monthly_saving,
                first_year_saving=(
                    monthly_saving * 12 - one_off if monthly_saving is not None else None
                ),
                difficulty=(
                    opportunity.difficulty.value if opportunity is not None else "moderate"
                ),
                decision=opportunity.decision.value if opportunity is not None else "review",
                notes=opportunity.notes if opportunity is not None else None,
            )
        )
    return sorted(
        records,
        key=lambda item: (
            item.monthly_saving is None,
            -(item.monthly_saving or 0),
            -item.current_monthly_cost,
            item.description.casefold(),
        ),
    )


def save_recurring_opportunity(
    session: Session,
    *,
    description: str,
    identity_key: str | None,
    currency: str,
    current_monthly_cost: int,
    replacement_monthly_cost: int | None,
    one_off_switching_cost: int,
    difficulty: OpportunityDifficulty,
    decision: OpportunityDecision,
    notes: str | None,
) -> RecurringCostOpportunity:
    canonical_identity = normalise_recurring_identity(identity_key, description)
    opportunity = session.scalar(
        select(RecurringCostOpportunity).where(
            RecurringCostOpportunity.identity_key == canonical_identity,
            RecurringCostOpportunity.currency == currency,
        )
    )
    if opportunity is None:
        opportunity = RecurringCostOpportunity(
            identity_key=canonical_identity,
            description=description,
            currency=currency,
            current_monthly_cost=current_monthly_cost,
        )
        session.add(opportunity)
    opportunity.description = description
    opportunity.current_monthly_cost = current_monthly_cost
    opportunity.replacement_monthly_cost = replacement_monthly_cost
    opportunity.one_off_switching_cost = one_off_switching_cost
    opportunity.difficulty = difficulty
    opportunity.decision = decision
    opportunity.notes = notes
    session.commit()
    return opportunity


def delete_recurring_opportunity(session: Session, opportunity_id: int) -> None:
    opportunity = session.get(RecurringCostOpportunity, opportunity_id)
    if opportunity is None:
        raise LookupError(f"Recurring opportunity {opportunity_id} was not found")
    session.delete(opportunity)
    session.commit()


def _monthly_cost(average_amount: int, cadence: str) -> int:
    factors = {
        "weekly": 52 / 12,
        "fortnightly": 26 / 12,
        "monthly": 1,
        "annual": 1 / 12,
    }
    return round(average_amount * factors[cadence])


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
        identity_key=(
            merchant_identity(stable[0].merchant_id)
            if stable[0].merchant_id is not None
            else normalise_description_identity(stable[0].normalised_description)
        ),
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
