import calendar
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class IncomeScheduleItem:
    cycle_id: int
    payment_date: date
    expected_amount: int


@dataclass(frozen=True)
class FundingWindow:
    funding_cycle_id: int
    start_date: date
    funding_amount: int
    next_cycle_id: int | None
    end_date: date
    next_income_amount: int


def resolve_funding_window(
    schedule: tuple[IncomeScheduleItem, ...],
    *,
    as_of_date: date,
) -> FundingWindow:
    """Resolve the income received most recently and the next scheduled income.

    The start is inclusive and the end is exclusive. When only one calendar plan
    exists, its monthly cadence is projected backward or forward so the forecast
    still has an income-to-income boundary.
    """
    if not schedule:
        raise ValueError("At least one scheduled income is required")
    ordered = tuple(sorted(schedule, key=lambda item: (item.payment_date, item.cycle_id)))
    received = [item for item in ordered if item.payment_date <= as_of_date]
    upcoming = [item for item in ordered if item.payment_date > as_of_date]

    if received:
        funding = received[-1]
    else:
        first = ordered[0]
        funding = IncomeScheduleItem(
            cycle_id=first.cycle_id,
            payment_date=_shift_month(first.payment_date, -1),
            expected_amount=first.expected_amount,
        )

    if upcoming:
        next_income = upcoming[0]
    else:
        next_income = IncomeScheduleItem(
            cycle_id=funding.cycle_id,
            payment_date=_shift_month(funding.payment_date, 1),
            expected_amount=funding.expected_amount,
        )

    return FundingWindow(
        funding_cycle_id=funding.cycle_id,
        start_date=funding.payment_date,
        funding_amount=funding.expected_amount,
        next_cycle_id=next_income.cycle_id if next_income in ordered else None,
        end_date=next_income.payment_date,
        next_income_amount=next_income.expected_amount,
    )


def _shift_month(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))
