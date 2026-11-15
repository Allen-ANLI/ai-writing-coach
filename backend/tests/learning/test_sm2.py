"""SM-2 unit tests: deterministic scheduling invariants."""

from decimal import Decimal

import pytest

from app.modules.learning import sm2


def test_first_success_schedules_one_day():
    update = sm2.review(sm2.initial_state(), 4)
    assert update.interval_days == Decimal("1")
    assert update.streak == 1
    assert update.repetitions == 1
    assert not update.mastered


def test_second_success_schedules_six_days():
    state = sm2.Sm2State(Decimal("1"), Decimal("2.5"), 1, 1)
    update = sm2.review(state, 4)
    assert update.interval_days == Decimal("6")
    assert update.repetitions == 2


def test_third_success_multiplies_by_ease():
    state = sm2.Sm2State(Decimal("6"), Decimal("2.5"), 2, 2)
    update = sm2.review(state, 4)
    assert update.interval_days == Decimal("15.00")


def test_failure_resets_interval_and_streak():
    state = sm2.Sm2State(Decimal("15"), Decimal("2.5"), 4, 4)
    update = sm2.review(state, 1)
    assert update.interval_days == Decimal("1")
    assert update.streak == 0
    assert update.repetitions == 0
    assert not update.mastered


def test_ease_floor_enforced():
    state = sm2.Sm2State(Decimal("6"), Decimal("1.3"), 2, 2)
    update = sm2.review(state, 3)
    assert update.ease_factor >= Decimal("1.3")


def test_hard_pass_lowers_ease():
    state = sm2.Sm2State(Decimal("6"), Decimal("2.5"), 2, 2)
    hard = sm2.review(state, 3)
    easy = sm2.review(state, 5)
    assert hard.ease_factor < easy.ease_factor


def test_mastery_requires_sustained_success():
    state = sm2.initial_state()
    update = None
    for _ in range(8):
        update = sm2.review(
            sm2.Sm2State(
                update.interval_days if update else state.interval_days,
                update.ease_factor if update else state.ease_factor,
                update.streak if update else state.streak,
                update.repetitions if update else state.repetitions,
            ),
            5,
        )
    assert update.mastered
    assert update.streak >= sm2.MASTERY_STREAK
    assert update.interval_days >= sm2.MASTERY_INTERVAL_DAYS


def test_invalid_quality_rejected():
    with pytest.raises(ValueError):
        sm2.review(sm2.initial_state(), 6)
    with pytest.raises(ValueError):
        sm2.review(sm2.initial_state(), -1)
