"""Tests for spaced repetition scheduling."""

from __future__ import annotations

from datetime import datetime, timezone

from app import srs

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


def test_new_word_good_grade_schedules_days_ahead() -> None:
    state = srs.schedule(srs.ReviewState(), srs.GOOD, now=NOW)
    assert state.reps == 1
    assert state.due_at is not None and state.due_at > NOW
    assert srs.interval_days(state) >= 2


def test_easy_beats_good_beats_hard() -> None:
    hard = srs.schedule(srs.ReviewState(), srs.HARD, now=NOW)
    good = srs.schedule(srs.ReviewState(), srs.GOOD, now=NOW)
    easy = srs.schedule(srs.ReviewState(), srs.EASY, now=NOW)
    assert hard.stability < good.stability < easy.stability


def test_again_keeps_word_due_immediately_and_counts_lapse() -> None:
    state = srs.schedule(srs.ReviewState(), srs.AGAIN, now=NOW)
    assert state.lapses == 1
    assert srs.interval_days(state) <= 1


def test_intervals_grow_across_successful_reviews() -> None:
    state = srs.ReviewState()
    intervals = []
    for _ in range(4):
        state = srs.schedule(state, srs.GOOD, now=NOW)
        intervals.append(srs.interval_days(state))
    assert intervals == sorted(intervals)
    assert intervals[-1] > intervals[0]


def test_lapse_retains_partial_stability() -> None:
    """Relearning is faster than learning: a lapse must not reset to zero."""
    state = srs.ReviewState()
    for _ in range(3):
        state = srs.schedule(state, srs.GOOD, now=NOW)
    before = state.stability
    lapsed = srs.schedule(state, srs.AGAIN, now=NOW)
    assert 0 < lapsed.stability < before


def test_difficulty_rises_on_failure_and_falls_on_success() -> None:
    state = srs.schedule(srs.ReviewState(), srs.GOOD, now=NOW)
    harder = srs.schedule(state, srs.AGAIN, now=NOW)
    easier = srs.schedule(state, srs.EASY, now=NOW)
    assert harder.difficulty > state.difficulty
    assert easier.difficulty < state.difficulty


def test_difficulty_stays_in_range() -> None:
    state = srs.ReviewState()
    for _ in range(30):
        state = srs.schedule(state, srs.AGAIN, now=NOW)
    assert 1.0 <= state.difficulty <= 10.0


def test_invalid_grade_is_rejected() -> None:
    try:
        srs.schedule(srs.ReviewState(), 7, now=NOW)
    except ValueError:
        return
    raise AssertionError("expected ValueError for an out-of-range grade")


def test_new_word_is_due() -> None:
    assert srs.is_due(srs.ReviewState(), now=NOW)
    scheduled = srs.schedule(srs.ReviewState(), srs.EASY, now=NOW)
    assert not srs.is_due(scheduled, now=NOW)


def run_all() -> int:
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL {name}: {exc or 'assertion failed'}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{failures} failure(s)")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run_all() else 0)
