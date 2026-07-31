from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Expense,
    OpportunityDecision,
    OpportunityDifficulty,
    RecurringCostOpportunity,
)
from app.services.cash_flow import spending_contribution
from app.services.recurrence_detection import RecurrenceObservation, detect_recurrence
from app.services.recurring_identity import (
    merchant_identity,
    normalise_description_identity,
    normalise_recurring_identity,
)
from app.services.report_query_service import report_expenses, validate_date_range


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


def get_recurring_expenses(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> list[RecurringExpenseRecord]:
    validate_date_range(date_from, date_to)
    groups: defaultdict[tuple[str, int | str, str], list[Expense]] = defaultdict(list)
    for expense in report_expenses(
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
    pattern = detect_recurrence(
        tuple(
            RecurrenceObservation(
                observation_id=expense.id,
                observed_on=expense.transaction_date,
                amount=-expense.amount,
            )
            for expense in expenses
        )
    )
    if pattern is None:
        return None
    expenses_by_id = {expense.id: expense for expense in expenses}
    stable = [expenses_by_id[item_id] for item_id in pattern.occurrence_ids]

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
        average_amount=pattern.typical_amount,
        occurrence_count=len(stable),
        cadence=pattern.cadence,
        typical_interval_days=pattern.typical_interval_days,
        last_seen=stable[-1].transaction_date,
    )
