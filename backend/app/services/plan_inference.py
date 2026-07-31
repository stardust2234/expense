from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import median

from app.services.recurrence_detection import RecurrenceObservation, detect_recurrence

MIN_OCCURRENCES = 2
INFERENCE_LOOKBACK_MONTHS = 6
MAX_RECURRENCE_AGE_DAYS = 62
ESSENTIAL_PRIORITIES = {"protected", "essential", "irregular_essential"}


@dataclass(frozen=True)
class TransactionEvidence:
    transaction_id: int
    transaction_date: date
    identity_key: str
    description: str
    amount: int
    currency: str
    category_id: int
    category_name: str
    root_category_name: str
    priority: str
    cash_flow_kind: str


@dataclass(frozen=True)
class IncomeProposal:
    proposal_id: str
    description: str
    expected_amount: int
    payment_date: date
    occurrence_count: int
    confidence: float
    evidence_transaction_ids: tuple[int, ...]


@dataclass(frozen=True)
class CommitmentProposal:
    proposal_id: str
    name: str
    amount: int
    due_date: date
    category_id: int
    category_name: str
    priority: str
    recurrence: str
    occurrence_count: int
    confidence: float
    evidence_transaction_ids: tuple[int, ...]


@dataclass(frozen=True)
class AllowanceProposal:
    proposal_id: str
    name: str
    allowance_type: str
    amount: int
    category_id: int
    category_name: str
    priority: str
    months_observed: int
    confidence: float
    evidence_transaction_ids: tuple[int, ...]


@dataclass(frozen=True)
class PlanPreview:
    target_month: date
    end_date: date
    currency: str
    income: IncomeProposal
    commitments: tuple[CommitmentProposal, ...]
    allowances: tuple[AllowanceProposal, ...]


class InsufficientPlanEvidenceError(ValueError):
    pass


def _add_month(value: date) -> date:
    month_index = value.month
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _shift_month(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def _date_in_month(month: date, day: int) -> date:
    return date(
        month.year,
        month.month,
        min(day, calendar.monthrange(month.year, month.month)[1]),
    )


def _monthly_pattern(rows: list[TransactionEvidence], *, minimum_occurrences: int):
    return detect_recurrence(
        tuple(
            RecurrenceObservation(
                observation_id=row.transaction_id,
                observed_on=row.transaction_date,
                amount=abs(row.amount),
            )
            for row in rows
        ),
        minimum_occurrences=minimum_occurrences,
        allowed_cadences=frozenset({"monthly"}),
    )


def infer_plan(
    evidence: tuple[TransactionEvidence, ...],
    *,
    target_month: date,
    currency: str,
) -> PlanPreview:
    """Infer a reviewable plan without reading or mutating application state."""
    target_month = target_month.replace(day=1)
    currency = currency.upper()
    evidence_start = _shift_month(target_month, -INFERENCE_LOOKBACK_MONTHS)
    relevant = tuple(
        row
        for row in evidence
        if row.currency.upper() == currency
        and evidence_start <= row.transaction_date < target_month
    )

    grouped: defaultdict[str, list[TransactionEvidence]] = defaultdict(list)
    for row in relevant:
        grouped[row.identity_key].append(row)

    income_groups = [
        (rows, pattern)
        for rows in grouped.values()
        if rows[0].cash_flow_kind == "income"
        and all(row.amount > 0 for row in rows)
        and (pattern := _monthly_pattern(rows, minimum_occurrences=2)) is not None
        and (target_month - max(row.transaction_date for row in rows)).days
        <= MAX_RECURRENCE_AGE_DAYS
    ]
    if not income_groups:
        raise InsufficientPlanEvidenceError(
            f"At least two monthly {currency} income transactions are required"
        )
    income_rows, income_pattern = max(
        income_groups,
        key=lambda item: (item[1].confidence, len(item[1].occurrence_ids), item[1].typical_amount),
    )
    payment_day = round(median(row.transaction_date.day for row in income_rows))
    income = IncomeProposal(
        proposal_id=f"income:{income_rows[0].identity_key}",
        description=income_rows[-1].description,
        expected_amount=income_pattern.typical_amount,
        payment_date=_date_in_month(target_month, payment_day),
        occurrence_count=len(income_pattern.occurrence_ids),
        confidence=income_pattern.confidence,
        evidence_transaction_ids=income_pattern.occurrence_ids,
    )

    recurring_keys: set[str] = set()
    commitments: list[CommitmentProposal] = []
    for identity_key, rows in grouped.items():
        sample = rows[0]
        pattern = _monthly_pattern(rows, minimum_occurrences=3)
        if (
            sample.cash_flow_kind != "spending"
            or not all(row.amount < 0 for row in rows)
            or pattern is None
        ):
            continue
        recurring_keys.add(identity_key)
        if (
            target_month - max(row.transaction_date for row in rows)
        ).days > MAX_RECURRENCE_AGE_DAYS:
            continue
        due_day = round(median(row.transaction_date.day for row in rows))
        commitments.append(
            CommitmentProposal(
                proposal_id=f"commitment:{identity_key}",
                name=rows[-1].description,
                amount=pattern.typical_amount,
                due_date=_date_in_month(target_month, due_day),
                category_id=sample.category_id,
                category_name=sample.category_name,
                priority=sample.priority,
                recurrence="monthly",
                occurrence_count=len(pattern.occurrence_ids),
                confidence=pattern.confidence,
                evidence_transaction_ids=pattern.occurrence_ids,
            )
        )

    monthly_category_totals: defaultdict[tuple[int, str, str, str], defaultdict[str, int]] = (
        defaultdict(lambda: defaultdict(int))
    )
    monthly_category_evidence: defaultdict[tuple[int, str, str, str], list[int]] = defaultdict(list)
    for row in relevant:
        if (
            row.cash_flow_kind != "spending"
            or row.priority not in ESSENTIAL_PRIORITIES
            or row.identity_key in recurring_keys
        ):
            continue
        key = (row.category_id, row.category_name, row.root_category_name, row.priority)
        monthly_category_totals[key][row.transaction_date.strftime("%Y-%m")] += -row.amount
        monthly_category_evidence[key].append(row.transaction_id)

    allowances: list[AllowanceProposal] = []
    for key, totals in monthly_category_totals.items():
        category_id, category_name, root_name, priority = key
        if len(totals) < MIN_OCCURRENCES:
            continue
        values = [max(value, 0) for value in totals.values()]
        root_key = root_name.casefold()
        allowance_type = (
            "food"
            if root_key == "groceries"
            else "transport"
            if root_key == "transport"
            else "irregular_cost"
            if priority == "irregular_essential"
            else "custom"
        )
        allowances.append(
            AllowanceProposal(
                proposal_id=f"allowance:category:{category_id}",
                name=category_name,
                allowance_type=allowance_type,
                amount=round(median(values)),
                category_id=category_id,
                category_name=category_name,
                priority=priority,
                months_observed=len(totals),
                confidence=round(min(len(totals) / 4, 1), 4),
                evidence_transaction_ids=tuple(monthly_category_evidence[key]),
            )
        )

    return PlanPreview(
        target_month=target_month,
        end_date=_add_month(target_month),
        currency=currency,
        income=income,
        commitments=tuple(sorted(commitments, key=lambda item: (item.due_date, item.name))),
        allowances=tuple(sorted(allowances, key=lambda item: item.name.casefold())),
    )
