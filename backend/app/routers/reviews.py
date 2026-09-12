"""Review endpoints: the due queue, grading, and progress."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import srs
from app.auth import CurrentUser, current_user
from app.db import models
from app.db.session import get_session
from app.repository import ensure_user, reviews_today, touch_streak
from app.routers.words import _to_out
from app.schemas import ProgressOut, ReviewCreate, ReviewResult, WordOut

router = APIRouter(tags=["reviews"])


@router.get("/reviews", response_model=list[WordOut])
def due_queue(
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
    limit: int = 20,
) -> list[WordOut]:
    """Words due now, hardest first.

    Capped small on purpose: a 200-card backlog is what makes people quit. The
    app should always offer a session that finishes.
    """
    now = datetime.now(timezone.utc)
    rows = session.scalars(
        select(models.Word)
        .where(
            models.Word.owner_uid == user.uid,
            or_(models.Word.due_at.is_(None), models.Word.due_at <= now),
        )
        .order_by(models.Word.difficulty.desc(), models.Word.due_at.asc())
        .limit(min(limit, 50))
    ).all()
    return [_to_out(row) for row in rows]


@router.post("/reviews", response_model=ReviewResult, status_code=status.HTTP_201_CREATED)
def grade_word(
    payload: ReviewCreate,
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> ReviewResult:
    """Record a grade and reschedule the word."""
    word = session.get(models.Word, payload.word_id)
    if word is None or word.owner_uid != user.uid:
        raise HTTPException(status_code=404, detail="word not found")

    state = srs.ReviewState(
        stability=word.stability,
        difficulty=word.difficulty,
        reps=word.reps,
        lapses=word.lapses,
        due_at=word.due_at,
        last_reviewed_at=word.last_reviewed_at,
    )
    updated = srs.schedule(state, payload.grade)

    word.stability = updated.stability
    word.difficulty = updated.difficulty
    word.reps = updated.reps
    word.lapses = updated.lapses
    word.due_at = updated.due_at
    word.last_reviewed_at = updated.last_reviewed_at

    session.add(
        models.Review(
            word_id=word.id,
            owner_uid=user.uid,
            grade=payload.grade,
            elapsed_ms=payload.elapsed_ms,
        )
    )
    touch_streak(session, user.uid)

    return ReviewResult(
        word_id=word.id,
        grade=payload.grade,
        reps=word.reps,
        due_at=word.due_at,
        interval_days=srs.interval_days(updated),
    )


@router.get("/progress", response_model=ProgressOut)
def progress(
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> ProgressOut:
    """Everything the Today screen needs, in one request."""
    ensure_user(session, user)
    now = datetime.now(timezone.utc)

    def count(model, *conditions) -> int:
        return session.scalar(
            select(func.count()).select_from(model).where(*conditions)
        ) or 0

    user_row = session.get(models.User, user.uid)
    return ProgressOut(
        saved_words=count(models.Word, models.Word.owner_uid == user.uid),
        due_now=count(
            models.Word,
            models.Word.owner_uid == user.uid,
            or_(models.Word.due_at.is_(None), models.Word.due_at <= now),
        ),
        reviews_today=reviews_today(session, user.uid, now),
        streak_days=user_row.streak_days if user_row else 0,
        clips_imported=count(models.Clip, models.Clip.owner_uid == user.uid),
    )
