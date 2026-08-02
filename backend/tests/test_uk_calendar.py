from datetime import date

from app.services.uk_calendar import previous_uk_banking_day


def test_moves_weekend_payment_to_friday() -> None:
    assert previous_uk_banking_day(date(2026, 8, 29)) == date(2026, 8, 28)


def test_moves_christmas_payment_before_bank_holidays() -> None:
    assert previous_uk_banking_day(date(2026, 12, 28)) == date(2026, 12, 24)


def test_leaves_normal_banking_day_unchanged() -> None:
    assert previous_uk_banking_day(date(2026, 7, 29)) == date(2026, 7, 29)


def test_can_move_new_year_payment_into_previous_month() -> None:
    assert previous_uk_banking_day(date(2028, 1, 1)) == date(2027, 12, 31)
