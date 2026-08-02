from __future__ import annotations

from dataclasses import dataclass, replace
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
from app.services.cash_flow import cash_flow_kind, root_category_code, root_category_name
from app.services.plan_inference import PlanPreview, TransactionEvidence, infer_plan
from app.services.recurring_identity import (
    merchant_identity,
    normalise_description_identity,
    normalise_payer_identity,
)


@dataclass(frozen=True)
class PlanConfirmation:
    payment_cycle_id: int
    created_cycle: bool
    created_commitment_ids: tuple[int, ...]
    updated_commitment_ids: tuple[int, ...]
    created_allowance_ids: tuple[int, ...]
    updated_allowance_ids: tuple[int, ...]


class PlanProposalNotFoundError(ValueError):
    pass


def _existing_cycle(session: Session, preview: PlanPreview) -> PaymentCycle | None:
    return session.scalar(
        select(PaymentCycle)
        .where(
            PaymentCycle.start_date == preview.target_month,
            PaymentCycle.end_date == preview.end_date,
            PaymentCycle.currency == preview.currency,
        )
        .options(
            selectinload(PaymentCycle.commitments),
            selectinload(PaymentCycle.allowances),
        )
    )


def _with_proposal_states(preview: PlanPreview, cycle: PaymentCycle | None) -> PlanPreview:
    if cycle is None:
        return preview
    income_total = sum(item.expected_amount for item in preview.incomes)
    income_date = min(item.payment_date for item in preview.incomes)
    income_state = (
        "unchanged"
        if cycle.expected_income_amount == income_total and cycle.next_payment_date == income_date
        else "changed"
    )
    incomes = tuple(replace(item, state=income_state) for item in preview.incomes)

    commitments_by_key = {
        item.inference_identity_key: item
        for item in cycle.commitments
        if item.inference_identity_key is not None
    }
    commitments = []
    for proposal in preview.commitments:
        existing = commitments_by_key.get(proposal.identity_key)
        if existing is None:
            existing = next(
                (
                    item
                    for item in cycle.commitments
                    if item.inference_identity_key is None
                    and item.category_id == proposal.category_id
                    and item.name.casefold() == proposal.name.casefold()
                    and abs(item.amount - proposal.amount) <= max(100, proposal.amount // 10)
                    and abs((item.due_date - proposal.due_date).days) <= 3
                ),
                None,
            )
        if existing is None:
            commitments.append(proposal)
            continue
        unchanged = (
            existing.name == proposal.name
            and existing.amount == proposal.amount
            and existing.due_date == proposal.due_date
            and existing.category_id == proposal.category_id
            and existing.priority.value == proposal.priority
        )
        commitments.append(
            replace(
                proposal,
                state="unchanged" if unchanged else "changed",
                existing_id=existing.id,
            )
        )

    allowances_by_key = {
        item.inference_identity_key: item
        for item in cycle.allowances
        if item.inference_identity_key is not None
    }
    allowances = []
    for proposal in preview.allowances:
        existing = allowances_by_key.get(proposal.identity_key)
        if existing is None:
            existing = next(
                (
                    item
                    for item in cycle.allowances
                    if item.inference_identity_key is None
                    and item.category_id == proposal.category_id
                ),
                None,
            )
        if existing is None:
            allowances.append(proposal)
            continue
        unchanged = (
            existing.name == proposal.name
            and existing.amount == proposal.amount
            and existing.allowance_type.value == proposal.allowance_type
            and existing.priority.value == proposal.priority
            and existing.category_id == proposal.category_id
        )
        allowances.append(
            replace(
                proposal,
                state="unchanged" if unchanged else "changed",
                existing_id=existing.id,
            )
        )
    return replace(
        preview,
        incomes=incomes,
        commitments=tuple(commitments),
        allowances=tuple(allowances),
    )


def preview_inferred_plan(session: Session, *, target_month: date, currency: str) -> PlanPreview:
    expenses = session.scalars(
        select(Expense)
        .where(
            Expense.status == TransactionStatus.CATEGORISED,
            Expense.category_id.is_not(None),
            Expense.currency == currency.upper(),
            Expense.transaction_date < target_month.replace(day=1),
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
        description = expense.merchant.name if expense.merchant else expense.normalised_description
        identity_key = (
            merchant_identity(expense.merchant_id)
            if expense.merchant_id is not None
            else normalise_description_identity(expense.normalised_description)
        )
        payer_key = (
            merchant_identity(expense.merchant_id)
            if expense.merchant_id is not None
            else normalise_payer_identity(expense.normalised_description)
        )
        evidence.append(
            TransactionEvidence(
                transaction_id=expense.id,
                transaction_date=expense.transaction_date,
                identity_key=identity_key,
                payer_key=payer_key,
                description=description,
                amount=expense.amount,
                currency=expense.currency,
                category_id=category.id,
                category_code=category.code,
                category_name=category.name,
                root_category_code=root_category_code(category),
                root_category_name=root_category_name(category),
                priority=(expense.priority_override or category.default_priority).value,
                cash_flow_kind=cash_flow_kind(category).value,
            )
        )
    preview = infer_plan(tuple(evidence), target_month=target_month, currency=currency)
    return _with_proposal_states(preview, _existing_cycle(session, preview))


def confirm_inferred_plan(
    session: Session,
    *,
    target_month: date,
    currency: str,
    opening_balance: int,
    current_balance: int | None,
    income_proposal_ids: list[str],
    commitment_proposal_ids: list[str],
    allowance_proposal_ids: list[str],
) -> PlanConfirmation:
    preview = preview_inferred_plan(session, target_month=target_month, currency=currency)
    incomes_by_id = {item.proposal_id: item for item in preview.incomes}
    commitments_by_id = {item.proposal_id: item for item in preview.commitments}
    allowances_by_id = {item.proposal_id: item for item in preview.allowances}
    missing = (
        set(income_proposal_ids) - incomes_by_id.keys()
        | set(commitment_proposal_ids) - commitments_by_id.keys()
        | set(allowance_proposal_ids) - allowances_by_id.keys()
    )
    if missing:
        raise PlanProposalNotFoundError(
            f"Unknown or stale proposal IDs: {', '.join(sorted(missing))}"
        )
    selected_incomes = [incomes_by_id[item_id] for item_id in dict.fromkeys(income_proposal_ids)]
    if not selected_incomes:
        raise PlanProposalNotFoundError("Select at least one reliable income proposal")

    cycle = _existing_cycle(session, preview)
    created_cycle = cycle is None
    expected_income = sum(item.expected_amount for item in selected_incomes)
    payment_date = min(item.payment_date for item in selected_incomes)
    if cycle is None:
        cycle = PaymentCycle(
            name="Inferred financial plan",
            start_date=preview.target_month,
            end_date=preview.end_date,
            next_payment_date=payment_date,
            expected_income_amount=expected_income,
            currency=preview.currency,
            opening_balance=opening_balance,
            current_balance=current_balance,
            status=PaymentCycleStatus.PLANNED,
        )
        session.add(cycle)
        session.flush()
    else:
        # Providing income proposal IDs is explicit approval to refresh the aggregate income.
        cycle.next_payment_date = payment_date
        cycle.expected_income_amount = expected_income
        cycle.opening_balance = opening_balance
        cycle.current_balance = current_balance

    created_commitments: list[Commitment] = []
    updated_commitments: list[Commitment] = []
    for proposal_id in dict.fromkeys(commitment_proposal_ids):
        proposal = commitments_by_id[proposal_id]
        existing = session.get(Commitment, proposal.existing_id) if proposal.existing_id else None
        if existing is None:
            existing = Commitment(payment_cycle=cycle, currency=preview.currency)
            session.add(existing)
            created_commitments.append(existing)
        elif proposal.state == "changed":
            updated_commitments.append(existing)
        existing.name = proposal.name
        existing.amount = proposal.amount
        existing.due_date = proposal.due_date
        existing.priority = SpendingPriority(proposal.priority)
        existing.category_id = proposal.category_id
        existing.status = CommitmentStatus.PENDING
        existing.recurrence = proposal.recurrence
        existing.inference_identity_key = proposal.identity_key

    created_allowances: list[CycleAllowance] = []
    updated_allowances: list[CycleAllowance] = []
    for proposal_id in dict.fromkeys(allowance_proposal_ids):
        proposal = allowances_by_id[proposal_id]
        existing = (
            session.get(CycleAllowance, proposal.existing_id) if proposal.existing_id else None
        )
        if existing is None:
            existing = CycleAllowance(payment_cycle=cycle)
            session.add(existing)
            created_allowances.append(existing)
        elif proposal.state == "changed":
            updated_allowances.append(existing)
        existing.name = proposal.name
        existing.allowance_type = AllowanceType(proposal.allowance_type)
        existing.amount = proposal.amount
        existing.priority = SpendingPriority(proposal.priority)
        existing.category_id = proposal.category_id
        existing.inference_identity_key = proposal.identity_key

    session.commit()
    return PlanConfirmation(
        payment_cycle_id=cycle.id,
        created_cycle=created_cycle,
        created_commitment_ids=tuple(item.id for item in created_commitments),
        updated_commitment_ids=tuple(item.id for item in updated_commitments),
        created_allowance_ids=tuple(item.id for item in created_allowances),
        updated_allowance_ids=tuple(item.id for item in updated_allowances),
    )
