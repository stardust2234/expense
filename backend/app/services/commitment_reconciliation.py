from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Commitment, CommitmentStatus, Expense, Merchant, TransactionStatus

MAX_DATE_DISTANCE_DAYS = 14
MIN_NAME_SCORE = 85


@dataclass(frozen=True)
class ReconciliationResult:
    matched: int
    ambiguous: int
    unmatched: int


@dataclass(frozen=True)
class _Candidate:
    expense: Expense
    name_score: int
    date_distance: int

    @property
    def rank(self) -> tuple[int, int]:
        return (self.name_score, -self.date_distance)


def _normalise_name(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", ascii_value.upper()).split())


def _name_score(commitment: Commitment, expense: Expense) -> int:
    expected = _normalise_name(commitment.name)
    if not expected:
        return 0

    names = [expense.description, expense.normalised_description]
    if expense.merchant is not None:
        names.append(expense.merchant.name)
        names.extend(alias.pattern for alias in expense.merchant.aliases)

    return max(
        (
            round(fuzz.WRatio(expected, candidate))
            for value in names
            if (candidate := _normalise_name(value))
        ),
        default=0,
    )


def _candidate_for(
    commitment: Commitment,
    expense: Expense,
) -> _Candidate | None:
    if expense.payment_cycle_id != commitment.payment_cycle_id:
        return None
    if expense.currency.upper() != commitment.currency.upper():
        return None
    if expense.amount >= 0 or -expense.amount != commitment.amount:
        return None

    date_distance = abs((expense.transaction_date - commitment.due_date).days)
    if date_distance > MAX_DATE_DISTANCE_DAYS:
        return None

    score = _name_score(commitment, expense)
    if commitment.category_id is not None:
        if expense.category_id != commitment.category_id:
            return None
    elif score < MIN_NAME_SCORE:
        return None

    return _Candidate(
        expense=expense,
        name_score=score,
        date_distance=date_distance,
    )


def reconcile_pending_commitments(
    session: Session,
    *,
    payment_cycle_id: int | None = None,
    import_batch_id: int | None = None,
) -> ReconciliationResult:
    """Match categorised outflows to unlinked commitments without guessing ambiguity.

    Paid-but-unlinked rows are included so older or manual status updates can gain
    an auditable expense link when an unambiguous transaction exists.
    """
    commitments_query = (
        select(Commitment)
        .where(
            Commitment.status.in_((CommitmentStatus.PENDING, CommitmentStatus.PAID)),
            Commitment.matched_expense_id.is_(None),
        )
        .order_by(Commitment.due_date, Commitment.id)
    )
    if payment_cycle_id is not None:
        commitments_query = commitments_query.where(Commitment.payment_cycle_id == payment_cycle_id)
    commitments = list(session.scalars(commitments_query))

    expenses_query = (
        select(Expense)
        .where(
            Expense.status == TransactionStatus.CATEGORISED,
            Expense.amount < 0,
            ~Expense.matched_commitment.has(),
        )
        .options(selectinload(Expense.merchant).selectinload(Merchant.aliases))
        .order_by(Expense.transaction_date, Expense.id)
    )
    if payment_cycle_id is not None:
        expenses_query = expenses_query.where(Expense.payment_cycle_id == payment_cycle_id)
    if import_batch_id is not None:
        expenses_query = expenses_query.where(Expense.import_batch_id == import_batch_id)
    expenses = list(session.scalars(expenses_query))

    matched = 0
    ambiguous = 0
    assigned_expense_ids: set[int] = set()
    for commitment in commitments:
        candidates = [
            candidate
            for expense in expenses
            if expense.id not in assigned_expense_ids
            and (candidate := _candidate_for(commitment, expense)) is not None
        ]
        candidates.sort(key=lambda candidate: candidate.rank, reverse=True)
        if not candidates:
            continue
        if len(candidates) > 1 and candidates[0].rank == candidates[1].rank:
            ambiguous += 1
            continue

        selected = candidates[0].expense
        commitment.matched_expense = selected
        commitment.status = CommitmentStatus.PAID
        assigned_expense_ids.add(selected.id)
        matched += 1

    session.commit()
    return ReconciliationResult(
        matched=matched,
        ambiguous=ambiguous,
        unmatched=len(commitments) - matched - ambiguous,
    )
