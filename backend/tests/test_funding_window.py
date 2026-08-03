from datetime import date

from app.services.funding_window import IncomeScheduleItem, resolve_funding_window


def test_end_of_month_income_funds_until_the_following_income() -> None:
    window = resolve_funding_window(
        (
            IncomeScheduleItem(1, date(2026, 7, 30), 92490),
            IncomeScheduleItem(2, date(2026, 8, 29), 292490),
        ),
        as_of_date=date(2026, 8, 3),
    )

    assert window.start_date == date(2026, 7, 30)
    assert window.end_date == date(2026, 8, 29)
    assert window.funding_amount == 92490
    assert window.next_income_amount == 292490


def test_single_future_income_projects_the_previous_monthly_payment() -> None:
    window = resolve_funding_window(
        (IncomeScheduleItem(1, date(2026, 8, 29), 100000),),
        as_of_date=date(2026, 8, 3),
    )

    assert window.start_date == date(2026, 7, 29)
    assert window.end_date == date(2026, 8, 29)


def test_single_received_income_projects_the_next_monthly_payment() -> None:
    window = resolve_funding_window(
        (IncomeScheduleItem(1, date(2026, 8, 31), 100000),),
        as_of_date=date(2026, 9, 2),
    )

    assert window.start_date == date(2026, 8, 31)
    assert window.end_date == date(2026, 9, 30)
