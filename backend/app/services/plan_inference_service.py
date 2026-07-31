from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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
    PaymentCycleStatus,
    SpendingPriority,
    TransactionStatus,
)
from app.services.cash_flow import cash_flow_kind, root_category_name
from app.services.plan_inference import (
    PlanPreview,
    TransactionEvidence,
    infer_plan,
)
from app.services.recurring_identity import (
    merchant_identity,
    normalise_description_identity,
)


@dataclass(frozen=True)
class PlanConfirmation:
    payment_cycle_id: int
    created_cycle: bool
    created_commitment_ids: tuple[int, ...]
    created_allowance_ids: tuple[int, ...]


class PlanProposalNotFoundError(ValueError):
    pass


def preview_inferred_plan(
    session: Session,
    *,
    target_month: date,
    currency: str,
) -> PlanPreview:
    expenses = session.scalars(
        select(Expense)
        .where(
            Expense.status == TransactionStatus.CATEGORISED,
            Expense.category_id.is_not(None),
        )
        .options(
            selectinload(Expense.category).selectinload(Category.parent),
            selectinload(Expense.merchant),
        )
        .order_by(Expense.transaction_date, Expense.id)
    ).all()
    evidence: list[TransactionEvidence] = []
    for expense in expenses:
        category = expense.category
        if category is None:
            continue
        description = (
            expense.merchant.name
            if expense.merchant is not None
            else expense.normalised_description
        )
        identity_key = (
            merchant_identity(expense.merchant_id)
            if expense.merchant_id is not None
            else normalise_description_identity(expense.normalised_description)
        )
        evidence.append(
            TransactionEvidence(
                transaction_id=expense.id,
                transaction_date=expense.transaction_date,
                identity_key=identity_key,
                description=description,
                amount=expense.amount,
                currency=expense.currency,
                category_id=category.id,
                category_name=category.name,
                root_category_name=root_category_name(category),
                priority=(expense.priority_override or category.default_priority).value,
                cash_flow_kind=cash_flow_kind(category).value,
            )
        )
    return infer_plan(
        tuple(evidence),
        target_month=target_month,
        currency=currency,
    )


def confirm_inferred_plan(
    session: Session,
    *,
    target_month: date,
    currency: str,
    opening_balance: int,
    current_balance: int | None,
    commitment_proposal_ids: list[str],
    allowance_proposal_ids: list[str],
) -> PlanConfirmation:
    preview = preview_inferred_plan(
        session,
        target_month=target_month,
        currency=currency,
    )
    commitments_by_id = {item.proposal_id: item for item in preview.commitments}
    allowances_by_id = {item.proposal_id: item for item in preview.allowances}
    missing = (set(commitment_proposal_ids) - commitments_by_id.keys()) | (
        set(allowance_proposal_ids) - allowances_by_id.keys()
    )
    if missing:
        raise PlanProposalNotFoundError(
            f"Unknown or stale proposal IDs: {', '.join(sorted(missing))}"
        )

    cycle = session.scalar(
        select(PaymentCycle).where(
            PaymentCycle.start_date == preview.target_month,
            PaymentCycle.end_date == preview.end_date,
            PaymentCycle.currency == preview.currency,
        )
    )
    created_cycle = cycle is None
    if cycle is None:
        cycle = PaymentCycle(
            name="Inferred benefit plan",
            start_date=preview.target_month,
            end_date=preview.end_date,
            next_payment_date=preview.income.payment_date,
            expected_income_amount=preview.income.expected_amount,
            currency=preview.currency,
            opening_balance=opening_balance,
            current_balance=current_balance,
            status=PaymentCycleStatus.PLANNED,
        )
        session.add(cycle)
        session.flush()
    # Confirmation is additive. A previously confirmed cycle is authoritative:
    # inferred evidence must never silently replace its income or balances.

    existing_commitments = {
        (item.name.casefold(), item.due_date, item.category_id) for item in cycle.commitments
    }
    created_commitments: list[Commitment] = []
    for proposal_id in dict.fromkeys(commitment_proposal_ids):
        proposal = commitments_by_id[proposal_id]
        identity = (
            proposal.name.casefold(),
            proposal.due_date,
            proposal.category_id,
        )
        if identity in existing_commitments:
            continue
        commitment = Commitment(
            payment_cycle=cycle,
            name=proposal.name,
            amount=proposal.amount,
            currency=preview.currency,
            due_date=proposal.due_date,
            priority=SpendingPriority(proposal.priority),
            category_id=proposal.category_id,
            status=CommitmentStatus.PENDING,
            recurrence=proposal.recurrence,
        )
        session.add(commitment)
        created_commitments.append(commitment)
        existing_commitments.add(identity)

    existing_allowance_categories = {
        allowance.category_id for allowance in cycle.allowances if allowance.category_id is not None
    }
    created_allowances: list[CycleAllowance] = []
    for proposal_id in dict.fromkeys(allowance_proposal_ids):
        proposal = allowances_by_id[proposal_id]
        if proposal.category_id in existing_allowance_categories:
            continue
        allowance = CycleAllowance(
            payment_cycle=cycle,
            name=proposal.name,
            allowance_type=AllowanceType(proposal.allowance_type),
            amount=proposal.amount,
            priority=SpendingPriority(proposal.priority),
            category_id=proposal.category_id,
        )
        session.add(allowance)
        created_allowances.append(allowance)
        existing_allowance_categories.add(proposal.category_id)

    session.commit()
    return PlanConfirmation(
        payment_cycle_id=cycle.id,
        created_cycle=created_cycle,
        created_commitment_ids=tuple(item.id for item in created_commitments),
        created_allowance_ids=tuple(item.id for item in created_allowances),
    )
