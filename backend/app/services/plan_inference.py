from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from statistics import median
from typing import Literal

from app.services.recurrence_detection import (
    RecurrenceObservation,
    RecurrencePattern,
    detect_recurrence,
)
from app.services.uk_calendar import previous_uk_banking_day

MIN_OCCURRENCES = 2
INFERENCE_LOOKBACK_MONTHS = 6
MAX_RECURRENCE_AGE_DAYS = 62
ESSENTIAL_PRIORITIES = {"protected", "essential", "irregular_essential"}
ProposalState = Literal["new", "unchanged", "changed"]


@dataclass(frozen=True)
class TransactionEvidence:
    transaction_id: int
    transaction_date: date
    identity_key: str
    payer_key: str
    description: str
    amount: int
    currency: str
    category_id: int
    category_code: str | None
    category_name: str
    root_category_code: str | None
    root_category_name: str
    priority: str
    cash_flow_kind: str


@dataclass(frozen=True)
class IncomeProposal:
    proposal_id: str
    identity_key: str
    description: str
    expected_amount: int
    nominal_payment_date: date
    payment_date: date
    date_adjusted: bool
    occurrence_count: int
    confidence: float
    evidence_transaction_ids: tuple[int, ...]
    state: ProposalState = "new"


@dataclass(frozen=True)
class CommitmentProposal:
    proposal_id: str
    identity_key: str
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
    state: ProposalState = "new"
    existing_id: int | None = None


@dataclass(frozen=True)
class AllowanceProposal:
    proposal_id: str
    identity_key: str
    name: str
    allowance_type: str
    amount: int
    category_id: int
    category_name: str
    priority: str
    months_observed: int
    confidence: float
    evidence_transaction_ids: tuple[int, ...]
    state: ProposalState = "new"
    existing_id: int | None = None


@dataclass(frozen=True)
class PlanImpact:
    expected_income: int
    commitments: int
    essential_allowances: int
    net_before_balance: int
    period_days: int


@dataclass(frozen=True)
class PlanPreview:
    target_month: date
    end_date: date
    currency: str
    incomes: tuple[IncomeProposal, ...]
    commitments: tuple[CommitmentProposal, ...]
    allowances: tuple[AllowanceProposal, ...]
    impact: PlanImpact


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
    return date(month.year, month.month, min(day, calendar.monthrange(month.year, month.month)[1]))


def _proposal_id(kind: str, identity_key: str) -> str:
    digest = sha256(identity_key.encode()).hexdigest()[:16]
    return f"{kind}:{digest}"


def _pattern_rows(
    rows: list[TransactionEvidence], pattern: RecurrencePattern
) -> list[TransactionEvidence]:
    by_id = {row.transaction_id: row for row in rows}
    return [by_id[item_id] for item_id in pattern.occurrence_ids]


def _monthly_patterns(
    rows: list[TransactionEvidence], *, minimum_occurrences: int
) -> tuple[RecurrencePattern, ...]:
    """Return distinct stable amount/cadence clusters from one identity."""
    patterns: dict[tuple[int, ...], RecurrencePattern] = {}
    for seed in rows:
        seed_amount = abs(seed.amount)
        tolerance = max(100, round(seed_amount * 0.10))
        candidates = [row for row in rows if abs(abs(row.amount) - seed_amount) <= tolerance]
        pattern = detect_recurrence(
            tuple(
                RecurrenceObservation(row.transaction_id, row.transaction_date, abs(row.amount))
                for row in candidates
            ),
            minimum_occurrences=minimum_occurrences,
            allowed_cadences=frozenset({"monthly"}),
        )
        if pattern is not None:
            patterns[pattern.occurrence_ids] = pattern
    return tuple(
        sorted(
            patterns.values(),
            key=lambda item: (item.confidence, len(item.occurrence_ids), item.typical_amount),
            reverse=True,
        )
    )


def infer_plan(
    evidence: tuple[TransactionEvidence, ...], *, target_month: date, currency: str
) -> PlanPreview:
    """Infer a reviewable plan without reading or mutating application state."""
    target_month = target_month.replace(day=1)
    end_date = _add_month(target_month)
    currency = currency.upper()
    evidence_start = _shift_month(target_month, -INFERENCE_LOOKBACK_MONTHS)
    relevant = tuple(
        row
        for row in evidence
        if row.currency.upper() == currency
        and evidence_start <= row.transaction_date < target_month
    )

    income_groups: defaultdict[tuple[str, str], list[TransactionEvidence]] = defaultdict(list)
    for row in relevant:
        if row.cash_flow_kind == "income" and row.amount > 0:
            category_key = row.category_code or f"category:{row.category_id}"
            income_groups[(category_key, row.payer_key)].append(row)

    incomes: list[IncomeProposal] = []
    used_income_evidence: set[int] = set()
    for (category_key, payer_key), rows in income_groups.items():
        for pattern in _monthly_patterns(rows, minimum_occurrences=2):
            if used_income_evidence.intersection(pattern.occurrence_ids):
                continue
            stable_rows = _pattern_rows(rows, pattern)
            if (
                target_month - max(row.transaction_date for row in stable_rows)
            ).days > MAX_RECURRENCE_AGE_DAYS:
                continue
            nominal_day = round(median(row.transaction_date.day for row in stable_rows))
            nominal_date = _date_in_month(target_month, nominal_day)
            payment_date = previous_uk_banking_day(nominal_date)
            identity_key = (
                f"{category_key}|{payer_key}|monthly|{round(pattern.typical_amount / 500) * 500}"
            )
            incomes.append(
                IncomeProposal(
                    proposal_id=_proposal_id("income", identity_key),
                    identity_key=identity_key,
                    description=stable_rows[-1].description,
                    expected_amount=pattern.typical_amount,
                    nominal_payment_date=nominal_date,
                    payment_date=payment_date,
                    date_adjusted=payment_date != nominal_date,
                    occurrence_count=len(pattern.occurrence_ids),
                    confidence=pattern.confidence,
                    evidence_transaction_ids=pattern.occurrence_ids,
                )
            )
            used_income_evidence.update(pattern.occurrence_ids)
    if not incomes:
        raise InsufficientPlanEvidenceError(
            f"At least two recurring {currency} income transactions before the selected plan month are required"
        )

    spending_groups: defaultdict[tuple[str, str], list[TransactionEvidence]] = defaultdict(list)
    for row in relevant:
        if row.cash_flow_kind == "spending" and row.amount < 0:
            category_key = row.category_code or f"category:{row.category_id}"
            spending_groups[(row.identity_key, category_key)].append(row)

    recurring_transaction_ids: set[int] = set()
    commitments: list[CommitmentProposal] = []
    for (base_identity, category_key), rows in spending_groups.items():
        used_group_evidence: set[int] = set()
        for pattern in _monthly_patterns(rows, minimum_occurrences=3):
            if used_group_evidence.intersection(pattern.occurrence_ids):
                continue
            stable_rows = _pattern_rows(rows, pattern)
            recurring_transaction_ids.update(pattern.occurrence_ids)
            used_group_evidence.update(pattern.occurrence_ids)
            if (
                target_month - max(row.transaction_date for row in stable_rows)
            ).days > MAX_RECURRENCE_AGE_DAYS:
                continue
            due_day = round(median(row.transaction_date.day for row in stable_rows))
            identity_key = f"{base_identity}|{category_key}|monthly|{round(pattern.typical_amount / 500) * 500}"
            sample = stable_rows[-1]
            commitments.append(
                CommitmentProposal(
                    proposal_id=_proposal_id("commitment", identity_key),
                    identity_key=identity_key,
                    name=sample.description,
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

    monthly_totals: defaultdict[tuple[int, str, str, str], defaultdict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    monthly_evidence: defaultdict[tuple[int, str, str, str], list[int]] = defaultdict(list)
    for row in relevant:
        if row.cash_flow_kind != "spending" or row.priority not in ESSENTIAL_PRIORITIES:
            continue
        if row.transaction_id in recurring_transaction_ids:
            continue
        root_key = row.root_category_code or row.root_category_name.casefold()
        key = (row.category_id, row.category_name, root_key, row.priority)
        monthly_totals[key][row.transaction_date.strftime("%Y-%m")] += -row.amount
        monthly_evidence[key].append(row.transaction_id)

    allowances: list[AllowanceProposal] = []
    for key, totals in monthly_totals.items():
        category_id, category_name, root_key, priority = key
        if len(totals) < MIN_OCCURRENCES:
            continue
        values = [max(value, 0) for value in totals.values()]
        allowance_type = (
            "food"
            if root_key == "groceries"
            else "transport"
            if root_key == "transport"
            else "irregular_cost"
            if priority == "irregular_essential"
            else "custom"
        )
        identity_key = f"allowance:category:{category_id}"
        allowances.append(
            AllowanceProposal(
                proposal_id=identity_key,
                identity_key=identity_key,
                name=category_name,
                allowance_type=allowance_type,
                amount=round(median(values)),
                category_id=category_id,
                category_name=category_name,
                priority=priority,
                months_observed=len(totals),
                confidence=round(min(len(totals) / 4, 1), 4),
                evidence_transaction_ids=tuple(monthly_evidence[key]),
            )
        )

    incomes.sort(key=lambda item: (item.payment_date, -item.expected_amount, item.description))
    commitments.sort(key=lambda item: (item.due_date, item.name))
    allowances.sort(key=lambda item: item.name.casefold())
    expected_income = sum(item.expected_amount for item in incomes)
    commitment_total = sum(item.amount for item in commitments)
    allowance_total = sum(item.amount for item in allowances)
    return PlanPreview(
        target_month=target_month,
        end_date=end_date,
        currency=currency,
        incomes=tuple(incomes),
        commitments=tuple(commitments),
        allowances=tuple(allowances),
        impact=PlanImpact(
            expected_income=expected_income,
            commitments=commitment_total,
            essential_allowances=allowance_total,
            net_before_balance=expected_income - commitment_total - allowance_total,
            period_days=(end_date - target_month).days,
        ),
    )
