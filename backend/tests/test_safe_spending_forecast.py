from datetime import date

import pytest

from app.services.safe_spending_forecast import (
    ForecastAllowance,
    ForecastCommitment,
    calculate_safe_spending,
)


def test_calculates_safe_daily_and_weekly_spending() -> None:
    forecast = calculate_safe_spending(
        as_of_date=date(2026, 7, 25),
        next_payment_date=date(2026, 8, 22),
        usable_balance=31000,
        expected_income_amount=80000,
        pending_commitments=(ForecastCommitment(16500, "protected"),),
        allowances=(
            ForecastAllowance(
                id=1,
                name="Food and transport",
                allowance_type="food",
                priority="essential",
                amount=9000,
                spent_amount=0,
            ),
            ForecastAllowance(
                id=2,
                name="Irregular costs",
                allowance_type="irregular_cost",
                priority="irregular_essential",
                amount=2000,
                spent_amount=0,
            ),
        ),
    )

    assert forecast.pending_commitments == 16500
    assert forecast.allowance_reserves == 11000
    assert forecast.projected_balance == 3500
    assert forecast.safe_to_spend == 3500
    assert forecast.shortfall == 0
    assert forecast.days_remaining == 28
    assert forecast.safe_daily_amount == 125
    assert forecast.safe_weekly_amount == 875
    assert forecast.essential_cost_coverage == 2.9091
    assert forecast.risks == ()


def test_only_reserves_the_unspent_part_of_an_allowance() -> None:
    forecast = calculate_safe_spending(
        as_of_date=date(2026, 7, 25),
        next_payment_date=date(2026, 8, 1),
        usable_balance=20000,
        expected_income_amount=50000,
        pending_commitments=(),
        allowances=(
            ForecastAllowance(
                id=1,
                name="Groceries",
                allowance_type="food",
                priority="essential",
                amount=10000,
                spent_amount=3500,
            ),
        ),
    )

    assert forecast.allowances[0].spent_amount == 3500
    assert forecast.allowances[0].remaining_amount == 6500
    assert forecast.safe_to_spend == 13500


def test_shortfall_is_reported_without_negative_safe_spending() -> None:
    forecast = calculate_safe_spending(
        as_of_date=date(2026, 7, 25),
        next_payment_date=date(2026, 8, 1),
        usable_balance=10000,
        expected_income_amount=50000,
        pending_commitments=(ForecastCommitment(12000, "protected"),),
        allowances=(),
    )

    assert forecast.projected_balance == -2000
    assert forecast.safe_to_spend == 0
    assert forecast.shortfall == 2000
    assert forecast.risks == ("Projected balance is below zero before the next payment",)


def test_past_payment_date_never_produces_a_negative_day_count() -> None:
    forecast = calculate_safe_spending(
        as_of_date=date(2026, 8, 2),
        next_payment_date=date(2026, 8, 1),
        usable_balance=10000,
        expected_income_amount=50000,
        pending_commitments=(),
        allowances=(),
    )

    assert forecast.days_remaining == 0
    assert forecast.safe_daily_amount == 0
    assert forecast.safe_weekly_amount == 0
    assert forecast.risks == ("The next payment date has arrived or passed",)


def test_rejects_negative_planned_amounts() -> None:
    with pytest.raises(ValueError, match="commitment"):
        calculate_safe_spending(
            as_of_date=date(2026, 7, 25),
            next_payment_date=date(2026, 8, 1),
            usable_balance=10000,
            expected_income_amount=50000,
            pending_commitments=(ForecastCommitment(-1, "protected"),),
            allowances=(),
        )


def test_reports_overspent_allowance_without_hiding_actual_spending() -> None:
    forecast = calculate_safe_spending(
        as_of_date=date(2026, 7, 25),
        next_payment_date=date(2026, 8, 1),
        usable_balance=10000,
        expected_income_amount=50000,
        pending_commitments=(),
        allowances=(
            ForecastAllowance(
                id=1,
                name="Groceries",
                allowance_type="food",
                priority="essential",
                amount=5000,
                spent_amount=6500,
            ),
        ),
    )

    assert forecast.allowances[0].spent_amount == 6500
    assert forecast.allowances[0].remaining_amount == 0
    assert forecast.risks == ("Groceries allowance is overspent",)
