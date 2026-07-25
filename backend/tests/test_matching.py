from decimal import Decimal

from app.services.matching import (
    MerchantCandidate,
    RuleCandidate,
    evaluate_rules,
    identify_merchant,
)


def test_identifies_the_most_specific_merchant() -> None:
    match = identify_merchant(
        "TESCO EXPRESS LONDON 0123",
        [
            MerchantCandidate(id=1, name="Tesco"),
            MerchantCandidate(id=2, name="Tesco Express"),
        ],
    )

    assert match is not None
    assert match.merchant_id == 2
    assert match.confidence == Decimal("0.9500")


def test_ambiguous_merchant_match_is_rejected() -> None:
    match = identify_merchant(
        "COFFEE SHOP",
        [
            MerchantCandidate(id=1, name="Coffee"),
            MerchantCandidate(id=2, name="Coffee"),
        ],
    )

    assert match is None


def test_rapidfuzz_identifies_a_typo_in_merchant_name() -> None:
    match = identify_merchant(
        "TESOC EXPRESS",
        [MerchantCandidate(id=7, name="Tesco Express")],
    )

    assert match is not None
    assert match.merchant_id == 7
    assert match.confidence >= Decimal("0.9000")


def test_rules_use_priority_before_rule_id() -> None:
    match = evaluate_rules(
        "TESCO STORES 0123",
        [
            RuleCandidate(id=1, match_pattern="TESCO", category_id=10, priority=10),
            RuleCandidate(id=2, match_pattern="STORES", category_id=20, priority=100),
        ],
    )

    assert match is not None
    assert match.rule_id == 2
    assert match.category_id == 20
    assert match.confidence == Decimal("1.0000")


def test_empty_rule_patterns_never_match() -> None:
    match = evaluate_rules(
        "TESCO",
        [RuleCandidate(id=1, match_pattern=" ", category_id=10, priority=100)],
    )

    assert match is None
