from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from statistics import median

CADENCE_WINDOWS = (
    ("weekly", 6, 8, 5, 10),
    ("fortnightly", 13, 15, 11, 18),
    ("monthly", 25, 35, 21, 40),
    ("annual", 350, 380, 330, 400),
)


@dataclass(frozen=True)
class RecurrenceObservation:
    observation_id: int
    observed_on: date
    amount: int


@dataclass(frozen=True)
class RecurrencePattern:
    cadence: str
    typical_interval_days: int
    typical_amount: int
    occurrence_ids: tuple[int, ...]
    confidence: float


def detect_recurrence(
    observations: tuple[RecurrenceObservation, ...],
    *,
    minimum_occurrences: int = 3,
    allowed_cadences: frozenset[str] | None = None,
) -> RecurrencePattern | None:
    """Detect stable recurrence using one shared amount and cadence policy."""
    if len(observations) < minimum_occurrences:
        return None
    typical_amount = round(median(item.amount for item in observations))
    amount_tolerance = max(100, typical_amount * 0.10)
    stable = [
        item for item in observations if abs(item.amount - typical_amount) <= amount_tolerance
    ]

    by_date: dict[date, RecurrenceObservation] = {}
    for item in stable:
        existing = by_date.get(item.observed_on)
        if existing is None or abs(item.amount - typical_amount) < abs(
            existing.amount - typical_amount
        ):
            by_date[item.observed_on] = item
    stable = [by_date[item_date] for item_date in sorted(by_date)]
    if len(stable) < minimum_occurrences:
        return None

    intervals = [
        (current.observed_on - previous.observed_on).days for previous, current in pairwise(stable)
    ]
    typical_interval = round(median(intervals))
    cadence = next(
        (
            name
            for name, typical_min, typical_max, interval_min, interval_max in CADENCE_WINDOWS
            if (allowed_cadences is None or name in allowed_cadences)
            and typical_min <= typical_interval <= typical_max
            and all(interval_min <= interval <= interval_max for interval in intervals)
        ),
        None,
    )
    if cadence is None:
        return None

    stability = len(stable) / len(observations)
    occurrence_score = min(len(stable) / 4, 1)
    confidence = round(0.6 * occurrence_score + 0.4 * stability, 4)
    return RecurrencePattern(
        cadence=cadence,
        typical_interval_days=typical_interval,
        typical_amount=round(median(item.amount for item in stable)),
        occurrence_ids=tuple(item.observation_id for item in stable),
        confidence=confidence,
    )
