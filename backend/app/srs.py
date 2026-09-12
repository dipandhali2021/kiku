"""Spaced repetition scheduling (FSRS-inspired, simplified).

Why not plain SM-2: SM-2 treats every lapse the same and has no concept of
memory stability, so it over-reviews easy words and under-reviews hard ones.
This keeps FSRS's two-variable model (stability and difficulty) with a small
rule set, which is enough for an MVP and can be replaced by real FSRS weights
later without changing the stored columns.

Grades follow the four-button convention:
  0 again  1 hard  2 good  3 easy
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

AGAIN, HARD, GOOD, EASY = 0, 1, 2, 3

_MIN_STABILITY = 0.4
_MAX_STABILITY = 365.0 * 3
_MIN_DIFFICULTY = 1.0
_MAX_DIFFICULTY = 10.0
_INITIAL_STABILITY = {AGAIN: 0.4, HARD: 1.0, GOOD: 2.5, EASY: 5.0}


@dataclass(slots=True)
class ReviewState:
    """What we persist per word, per user."""

    stability: float = 0.0
    difficulty: float = 5.0
    reps: int = 0
    lapses: int = 0
    due_at: datetime | None = None
    last_reviewed_at: datetime | None = None

    @property
    def is_new(self) -> bool:
        return self.reps == 0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def schedule(state: ReviewState, grade: int, now: datetime | None = None) -> ReviewState:
    """Return the next state for a word after a review.

    Pure function: no database, no clock reads beyond the injected `now`, so it
    is trivially testable and identical on client and server.
    """
    if grade not in (AGAIN, HARD, GOOD, EASY):
        raise ValueError(f"grade must be 0-3, got {grade}")

    now = now or datetime.now(timezone.utc)

    if state.is_new:
        stability = _INITIAL_STABILITY[grade]
        difficulty = _clamp(6.0 - grade, _MIN_DIFFICULTY, _MAX_DIFFICULTY)
        lapses = 1 if grade == AGAIN else 0
    else:
        difficulty = _clamp(
            state.difficulty + (0.6 - 0.35 * grade),
            _MIN_DIFFICULTY,
            _MAX_DIFFICULTY,
        )
        if grade == AGAIN:
            # A lapse keeps some of the old stability: relearning is faster
            # than learning from scratch.
            stability = _clamp(state.stability * 0.35, _MIN_STABILITY, _MAX_STABILITY)
            lapses = state.lapses + 1
        else:
            ease = {HARD: 1.2, GOOD: 1.0, EASY: 1.35}[grade]
            # Harder words grow more slowly; this is the FSRS intuition.
            growth = 1.0 + (11.0 - difficulty) * 0.22 * ease
            if grade == HARD:
                growth = max(1.1, growth * 0.6)
            stability = _clamp(
                max(state.stability, _MIN_STABILITY) * growth,
                _MIN_STABILITY,
                _MAX_STABILITY,
            )
            lapses = state.lapses

    interval_days = max(1.0, round(stability, 2))
    return ReviewState(
        stability=round(stability, 3),
        difficulty=round(difficulty, 3),
        reps=state.reps + 1,
        lapses=lapses,
        due_at=now + timedelta(days=interval_days),
        last_reviewed_at=now,
    )


def interval_days(state: ReviewState) -> int:
    """Human-readable interval for the UI ("next in 6 days")."""
    if state.due_at is None or state.last_reviewed_at is None:
        return 0
    return max(0, (state.due_at - state.last_reviewed_at).days)


def is_due(state: ReviewState, now: datetime | None = None) -> bool:
    if state.due_at is None:
        return True
    return state.due_at <= (now or datetime.now(timezone.utc))
