from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ForecastCommitment:
    amount: int
    priority: str


@dataclass(frozen=True)
class ForecastAllowance:
    id: int
    name: str
    allowance_type: str
    priority: str
    amount: int
    spent_amount: int


@dataclass(frozen=True)
class AllowanceForecast:
    id: int
    name: str
    allowance_type: str
    priority: str
    amount: int
    spent_amount: int
    remaining_amount: int


@dataclass(frozen=True)
class SafeSpendingForecast:
    as_of_date: date
    next_payment_date: date
    usable_balance: int
    pending_commitments: int
    allowance_reserves: int
    safe_to_spend: int
    shortfall: int
    projected_balance: int
    days_remaining: int
    safe_daily_amount: int
    safe_weekly_amount: int
    essential_cost_coverage: float | None
    allowances: tuple[AllowanceForecast, ...]
    risks: tuple[str, ...]


def calculate_safe_spending(
    *,
    as_of_date: date,
    next_payment_date: date,
    usable_balance: int,
    expected_income_amount: int,
    pending_commitments: tuple[ForecastCommitment, ...],
    allowances: tuple[ForecastAllowance, ...],
) -> SafeSpendingForecast:
    if expected_income_amount < 0:
        raise ValueError("expected_income_amount must not be negative")
    if any(commitment.amount < 0 for commitment in pending_commitments):
        raise ValueError("commitment amounts must not be negative")

    allowance_results = tuple(_calculate_allowance(item) for item in allowances)
    pending_commitment_total = sum(commitment.amount for commitment in pending_commitments)
    allowance_reserves = sum(item.remaining_amount for item in allowance_results)
    projected_balance = usable_balance - pending_commitment_total - allowance_reserves
    safe_to_spend = max(projected_balance, 0)
    shortfall = max(-projected_balance, 0)
    days_remaining = max((next_payment_date - as_of_date).days, 0)
    safe_daily_amount = safe_to_spend // days_remaining if days_remaining else 0
    safe_weekly_amount = (
        min(safe_to_spend, safe_to_spend * 7 // days_remaining) if days_remaining else 0
    )
    essential_priorities = {
        "protected",
        "essential",
        "adjustable",
        "irregular_essential",
    }
    essential_costs = sum(
        commitment.amount
        for commitment in pending_commitments
        if commitment.priority in essential_priorities
    ) + sum(
        allowance.remaining_amount
        for allowance in allowance_results
        if allowance.priority in essential_priorities
    )
    essential_cost_coverage = (
        round(expected_income_amount / essential_costs, 4) if essential_costs else None
    )
    risks: list[str] = []
    if shortfall:
        risks.append("Projected balance is below zero before the next payment")
    if days_remaining == 0:
        risks.append("The next payment date has arrived or passed")
    risks.extend(
        f"{allowance.name} allowance is overspent"
        for allowance in allowance_results
        if allowance.spent_amount > allowance.amount
    )

    return SafeSpendingForecast(
        as_of_date=as_of_date,
        next_payment_date=next_payment_date,
        usable_balance=usable_balance,
        pending_commitments=pending_commitment_total,
        allowance_reserves=allowance_reserves,
        safe_to_spend=safe_to_spend,
        shortfall=shortfall,
        projected_balance=projected_balance,
        days_remaining=days_remaining,
        safe_daily_amount=safe_daily_amount,
        safe_weekly_amount=safe_weekly_amount,
        essential_cost_coverage=essential_cost_coverage,
        allowances=allowance_results,
        risks=tuple(risks),
    )


def _calculate_allowance(allowance: ForecastAllowance) -> AllowanceForecast:
    if allowance.amount < 0 or allowance.spent_amount < 0:
        raise ValueError("allowance amounts must not be negative")
    return AllowanceForecast(
        id=allowance.id,
        name=allowance.name,
        allowance_type=allowance.allowance_type,
        priority=allowance.priority,
        amount=allowance.amount,
        spent_amount=allowance.spent_amount,
        remaining_amount=max(allowance.amount - allowance.spent_amount, 0),
    )
