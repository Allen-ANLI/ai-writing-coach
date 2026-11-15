"""SM-2 style spaced repetition (PRD FR-05.4) — deterministic, unit-tested.

Quality scale 0-5 (SM-2): 0-2 = failure (reset), 3 = hard pass, 4 = pass,
5 = easy pass. Intervals: 1 day, 6 days, then round(interval * ease).
Ease factor floor 1.3. Mastery after sustained success (streak >= 5 and
interval >= 21 days) — a product rule, adjustable without touching callers.
"""

from dataclasses import dataclass
from decimal import Decimal

MASTERY_STREAK = 5
MASTERY_INTERVAL_DAYS = Decimal("21")
INITIAL_EASE = Decimal("2.5")
MIN_EASE = Decimal("1.3")


@dataclass(frozen=True)
class Sm2State:
    interval_days: Decimal
    ease_factor: Decimal
    streak: int
    repetitions: int


@dataclass(frozen=True)
class Sm2Update:
    interval_days: Decimal
    ease_factor: Decimal
    streak: int
    repetitions: int
    mastered: bool


def initial_state() -> Sm2State:
    return Sm2State(interval_days=Decimal("0"), ease_factor=INITIAL_EASE, streak=0, repetitions=0)


def review(state: Sm2State, quality: int) -> Sm2Update:
    """Apply one review outcome. quality must be 0..5."""
    if not 0 <= quality <= 5:
        raise ValueError("quality must be between 0 and 5")
    q = Decimal(quality)
    ease = state.ease_factor + (
        Decimal("0.1") - (5 - q) * (Decimal("0.08") + (5 - q) * Decimal("0.02"))
    )
    if ease < MIN_EASE:
        ease = MIN_EASE

    if quality < 3:
        interval = Decimal("1")
        streak = 0
        repetitions = 0
    else:
        streak = state.streak + 1
        repetitions = state.repetitions + 1
        if repetitions == 1:
            interval = Decimal("1")
        elif repetitions == 2:
            interval = Decimal("6")
        else:
            interval = (state.interval_days * ease).quantize(Decimal("0.01"))

    mastered = streak >= MASTERY_STREAK and interval >= MASTERY_INTERVAL_DAYS
    return Sm2Update(
        interval_days=interval,
        ease_factor=ease.quantize(Decimal("0.01")),
        streak=streak,
        repetitions=repetitions,
        mastered=mastered,
    )
