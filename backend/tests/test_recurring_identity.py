import pytest

from app.services.recurring_identity import (
    merchant_identity,
    normalise_description_identity,
    normalise_recurring_identity,
)


def test_description_identity_normalises_unicode_case_and_spacing() -> None:
    assert normalise_description_identity("  Amazon\u00a0ＥＵ  ") == "description:amazon eu"
    assert normalise_recurring_identity(" DESCRIPTION:  Amazon EU ", "ignored") == (
        "description:amazon eu"
    )


def test_merchant_identity_is_stable_and_canonical() -> None:
    assert merchant_identity(42) == "merchant:42"
    assert normalise_recurring_identity(" Merchant:0042 ", "ignored") == "merchant:42"


@pytest.mark.parametrize(
    "identity_key",
    ["amazon", "unknown:amazon", "merchant:0", "merchant:not-a-number"],
)
def test_rejects_invalid_identity(identity_key: str) -> None:
    with pytest.raises(ValueError):
        normalise_recurring_identity(identity_key, "Amazon")
