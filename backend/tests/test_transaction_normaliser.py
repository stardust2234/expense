from datetime import date

import pytest

from app.services.transaction_normaliser import (
    NormalisationError,
    NormalisedTransaction,
    normalise_transaction,
)


def test_normalises_canonical_transaction_without_mutating_input() -> None:
    raw_data = {
        "Transaction Date": "24/07/2026",
        "Description": "  Tesco\u00a0Stores   0123 ",
        "Amount": "£1,234.56",
        "Currency": "gbp",
    }
    original = raw_data.copy()

    result = normalise_transaction(raw_data)

    assert result == NormalisedTransaction(
        transaction_date=date(2026, 7, 24),
        description="Tesco Stores 0123",
        normalised_description="TESCO STORES 0123",
        amount=123456,
        currency="GBP",
    )
    assert raw_data == original


def test_accepts_header_aliases_and_default_currency() -> None:
    result = normalise_transaction(
        {
            "posted_date": "2026-07-24",
            "Narrative": "Coffee shop",
            "Value": "(4.25)",
        },
        default_currency="GBP",
    )

    assert result.transaction_date == date(2026, 7, 24)
    assert result.amount == -425
    assert result.currency == "GBP"


def test_accepts_revolut_completed_date_with_time() -> None:
    result = normalise_transaction(
        {
            "Type": "Card Payment",
            "Started Date": "2025-10-24 16:41:36",
            "Completed Date": "2025-10-25 02:58:41",
            "Description": "Best-one",
            "Amount": "-4.58",
            "Currency": "GBP",
        }
    )

    assert result.transaction_date == date(2025, 10, 25)
    assert result.description == "Best-one"
    assert result.amount == -458


def test_accepts_revolut_short_us_timestamp() -> None:
    result = normalise_transaction(
        {
            "Started Date": "4/15/26 15:50",
            "Completed Date": "4/16/26 6:00",
            "Description": "Payment from bank",
            "Amount": "3.64",
            "Currency": "GBP",
        }
    )

    assert result.transaction_date == date(2026, 4, 16)
    assert result.amount == 364


def test_uses_currency_minor_unit_precision() -> None:
    result = normalise_transaction(
        {
            "Date": "2026/07/24",
            "Merchant": "Tokyo Metro",
            "Amount": "250",
            "Currency Code": "JPY",
        }
    )

    assert result.amount == 250
    assert result.normalised_description == "TOKYO METRO"


def test_accepts_sign_before_currency_symbol() -> None:
    result = normalise_transaction(
        {
            "Date": "2026-07-24",
            "Description": "Refund",
            "Amount": "-£12.50",
            "Currency": "GBP",
        }
    )

    assert result.amount == -1250


@pytest.mark.parametrize(
    ("raw_data", "field"),
    [
        ({"Description": "Coffee", "Amount": "2", "Currency": "GBP"}, "transaction_date"),
        (
            {
                "Date": "24.07.2026",
                "Description": "Coffee",
                "Amount": "2",
                "Currency": "GBP",
            },
            "transaction_date",
        ),
        (
            {
                "Date": "2026-07-24",
                "Description": "Coffee",
                "Amount": "2.001",
                "Currency": "GBP",
            },
            "amount",
        ),
        (
            {
                "Date": "2026-07-24",
                "Description": "Coffee",
                "Amount": "2",
                "Currency": "Sterling",
            },
            "currency",
        ),
    ],
)
def test_rejects_values_that_cannot_be_normalised(
    raw_data: dict[str, str],
    field: str,
) -> None:
    with pytest.raises(NormalisationError) as error:
        normalise_transaction(raw_data)

    assert error.value.field == field


def test_rejects_headers_that_collide_after_normalisation() -> None:
    with pytest.raises(NormalisationError, match="multiple columns"):
        normalise_transaction(
            {
                "Transaction Date": "2026-07-24",
                "transaction_date": "2026-07-25",
                "Description": "Coffee",
                "Amount": "2",
                "Currency": "GBP",
            }
        )
