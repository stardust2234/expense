import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from rapidfuzz import fuzz


@dataclass(frozen=True)
class MerchantCandidate:
    id: int
    name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class MerchantMatch:
    merchant_id: int
    confidence: Decimal


@dataclass(frozen=True)
class RuleCandidate:
    id: int
    match_pattern: str
    category_id: int
    priority: int


@dataclass(frozen=True)
class RuleMatch:
    rule_id: int
    category_id: int
    confidence: Decimal


def _canonical_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).upper().split())


def identify_merchant(
    normalised_description: str,
    merchants: Iterable[MerchantCandidate],
) -> MerchantMatch | None:
    """Return the strongest unambiguous canonical-name match."""
    description = _canonical_text(normalised_description)
    matches_by_merchant: dict[int, tuple[Decimal, int, int]] = {}

    for merchant in merchants:
        for candidate_name in (merchant.name, *merchant.aliases):
            name = _canonical_text(candidate_name)
            if not name:
                continue
            if description == name:
                confidence = Decimal("1.0000")
            elif description.startswith(f"{name} "):
                confidence = Decimal("0.9500")
            elif f" {name} " in f" {description} ":
                confidence = Decimal("0.9000")
            else:
                fuzzy_score = fuzz.WRatio(description, name, score_cutoff=85)
                if not fuzzy_score:
                    continue
                confidence = Decimal(str(round(fuzzy_score / 100, 4)))
            candidate = (confidence, len(name), merchant.id)
            current = matches_by_merchant.get(merchant.id)
            if current is None or candidate[:2] > current[:2]:
                matches_by_merchant[merchant.id] = candidate

    if not matches_by_merchant:
        return None

    matches = list(matches_by_merchant.values())
    matches.sort(key=lambda match: (-match[0], -match[1], match[2]))
    best = matches[0]
    if len(matches) > 1 and matches[1][:2] == best[:2]:
        return None
    return MerchantMatch(merchant_id=best[2], confidence=best[0])


def evaluate_rules(
    normalised_description: str,
    rules: Iterable[RuleCandidate],
) -> RuleMatch | None:
    """Evaluate substring rules by descending priority, then stable rule ID."""
    description = _canonical_text(normalised_description)
    ordered_rules = sorted(rules, key=lambda rule: (-rule.priority, rule.id))

    for rule in ordered_rules:
        pattern = _canonical_text(rule.match_pattern)
        if pattern and pattern in description:
            return RuleMatch(
                rule_id=rule.id,
                category_id=rule.category_id,
                confidence=Decimal("1.0000"),
            )
    return None
