import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from time import strptime

DATE_FIELDS = (
    "transaction date",
    "completed date",
    "posted date",
    "started date",
    "date",
)
DESCRIPTION_FIELDS = ("description", "details", "narrative", "merchant")
AMOUNT_FIELDS = ("amount", "transaction amount", "value")
CURRENCY_FIELDS = ("currency", "currency code")
DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%y",
    "%m/%d/%y %H:%M",
    "%d/%m/%Y",
    "%d/%m/%Y %H:%M:%S",
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M",
    "%d-%m-%Y",
    "%Y/%m/%d",
)
MINOR_UNIT_EXPONENTS = {
    "BHD": 3,
    "JPY": 0,
    "KRW": 0,
    "KWD": 3,
    "OMR": 3,
    "TND": 3,
}


class NormalisationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"{field}: {message}")


@dataclass(frozen=True)
class NormalisedTransaction:
    transaction_date: date
    description: str
    normalised_description: str
    amount: int
    currency: str


def _normalise_header(header: str) -> str:
    text = unicodedata.normalize("NFKC", header)
    text = re.sub(r"[_-]+", " ", text)
    return " ".join(text.casefold().split())


def _normalise_row(raw_data: Mapping[str, str | None]) -> dict[str, str | None]:
    row: dict[str, str | None] = {}
    for header, value in raw_data.items():
        normalised_header = _normalise_header(header)
        if not normalised_header:
            raise NormalisationError("headers", "header names must not be empty")
        if normalised_header in row:
            raise NormalisationError(
                "headers",
                f"multiple columns resolve to {normalised_header!r}",
            )
        row[normalised_header] = value
    return row


def _required_value(
    row: Mapping[str, str | None],
    *,
    field: str,
    aliases: Sequence[str],
) -> str:
    for alias in aliases:
        value = row.get(alias)
        if value is not None and value.strip():
            return value.strip()
    raise NormalisationError(field, f"missing value; accepted columns: {', '.join(aliases)}")


def _parse_date(value: str) -> date:
    for date_format in DATE_FORMATS:
        try:
            parsed = strptime(value, date_format)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    raise NormalisationError(
        "transaction_date",
        f"{value!r} is not a supported date",
    )


def _parse_currency(value: str) -> str:
    currency = value.strip().upper()
    if len(currency) != 3 or not currency.isalpha() or not currency.isascii():
        raise NormalisationError("currency", "must be a three-letter ISO currency code")
    return currency


def _parse_amount(value: str, currency: str) -> int:
    cleaned = unicodedata.normalize("NFKC", value).strip()
    negative_parentheses = cleaned.startswith("(") and cleaned.endswith(")")
    if negative_parentheses:
        cleaned = cleaned[1:-1].strip()

    cleaned = cleaned.replace(",", "")
    sign = ""
    if cleaned.startswith(("+", "-")):
        sign, cleaned = cleaned[0], cleaned[1:].strip()
    cleaned = re.sub(r"^[£$€]\s*", "", cleaned)
    cleaned = f"{sign}{cleaned}"
    try:
        major_units = Decimal(cleaned)
    except InvalidOperation as error:
        raise NormalisationError("amount", f"{value!r} is not numeric") from error
    if not major_units.is_finite():
        raise NormalisationError("amount", f"{value!r} must be finite")

    if negative_parentheses:
        major_units = -major_units

    exponent = MINOR_UNIT_EXPONENTS.get(currency, 2)
    minor_units = major_units * (10**exponent)
    if minor_units != minor_units.to_integral_value():
        raise NormalisationError(
            "amount",
            f"{value!r} has more precision than {currency} supports",
        )
    return int(minor_units)


def _normalise_description(value: str) -> tuple[str, str]:
    description = " ".join(unicodedata.normalize("NFKC", value).split())
    if not description:
        raise NormalisationError("description", "must not be empty")
    return description, description.upper()


def normalise_transaction(
    raw_data: Mapping[str, str | None],
    *,
    default_currency: str | None = None,
) -> NormalisedTransaction:
    """Convert one raw CSV row into canonical values without mutating input or external state."""
    row = _normalise_row(raw_data)
    transaction_date = _parse_date(
        _required_value(row, field="transaction_date", aliases=DATE_FIELDS)
    )
    description, normalised_description = _normalise_description(
        _required_value(row, field="description", aliases=DESCRIPTION_FIELDS)
    )

    currency_value = next(
        (
            row[alias]
            for alias in CURRENCY_FIELDS
            if row.get(alias) is not None and row[alias] and row[alias].strip()
        ),
        default_currency,
    )
    if currency_value is None:
        raise NormalisationError(
            "currency",
            f"missing value; accepted columns: {', '.join(CURRENCY_FIELDS)}",
        )
    currency = _parse_currency(currency_value)
    amount = _parse_amount(
        _required_value(row, field="amount", aliases=AMOUNT_FIELDS),
        currency,
    )

    return NormalisedTransaction(
        transaction_date=transaction_date,
        description=description,
        normalised_description=normalised_description,
        amount=amount,
        currency=currency,
    )
