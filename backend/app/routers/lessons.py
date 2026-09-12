"""Lesson endpoints: import a clip, fetch a cached lesson, list clips."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, current_user
from app.config import settings
from app.db import models
from app.db.session import get_session
from app.lessons.builder import LessonBuilder, clip_id_for
from app.repository import ensure_user, known_lemmas
from app.schemas import ClipOut, LessonCreate, LessonOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.post("", response_model=LessonOut, status_code=status.HTTP_201_CREATED)
def create_lesson(
    payload: LessonCreate,
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> LessonOut:
    """Build a lesson from subtitle text.

    Cached by subtitle content hash, so re-importing the same clip is free and
    two users importing the same episode only pay for the LLM once. The
    learner's known words are applied on top of the cached payload, because
    those differ per user while the lesson itself does not.
    """
    if len(payload.subtitles.encode("utf-8")) > settings.max_subtitle_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"subtitles exceed {settings.max_subtitle_bytes} bytes",
        )

    ensure_user(session, user)
    _enforce_daily_limit(session, user.uid)

    clip_id = clip_id_for(payload.subtitles)
    known = known_lemmas(session, user.uid)

    cached = session.get(models.Lesson, clip_id)
    if cached is not None:
        lesson = LessonOut.model_validate(cached.payload)
        lesson.title = payload.title or lesson.title
        _apply_known(lesson, known)
        _upsert_clip(session, user.uid, lesson, payload.local_media_uri)
        return lesson

    built = LessonBuilder().build(
        payload.subtitles,
        title=payload.title,
        known_words=known,
        max_lines=payload.max_lines or settings.max_lines_per_lesson,
    )
    if not built.lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="no teachable Japanese lines found in this subtitle file",
        )

    lesson = LessonOut.model_validate(built.to_dict())

    # Cache the lesson without per-user state so it is reusable.
    shareable = lesson.model_copy(deep=True)
    _apply_known(shareable, set())
    session.add(
        models.Lesson(clip_id=clip_id, engine=built.engine, payload=shareable.model_dump(mode="json"))
    )
    _upsert_clip(session, user.uid, lesson, payload.local_media_uri)

    logger.info(
        "built lesson clip=%s lines=%d engine=%s", clip_id, lesson.line_count, built.engine
    )
    return lesson


@router.get("/{clip_id}", response_model=LessonOut)
def get_lesson(
    clip_id: str,
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> LessonOut:
    cached = session.get(models.Lesson, clip_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="lesson not found")

    lesson = LessonOut.model_validate(cached.payload)
    _apply_known(lesson, known_lemmas(session, user.uid))

    clip = session.get(models.Clip, clip_id)
    if clip is not None and clip.owner_uid == user.uid:
        lesson.title = clip.title
    return lesson


@router.get("", response_model=list[ClipOut])
def list_clips(
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
    limit: int = 50,
) -> list[ClipOut]:
    rows = session.scalars(
        select(models.Clip)
        .where(models.Clip.owner_uid == user.uid)
        .order_by(models.Clip.created_at.desc())
        .limit(min(limit, 200))
    ).all()
    return [ClipOut.model_validate(row) for row in rows]


# -- helpers ---------------------------------------------------------------


def _apply_known(lesson: LessonOut, known: set[str]) -> None:
    """Recompute per-user state on a shared lesson payload."""
    teachable = 0
    known_count = 0
    for line in lesson.lines:
        for word in line.words:
            word.known = word.lemma in known or word.surface in known
            if word.teachable:
                teachable += 1
                known_count += int(word.known)
    lesson.comprehension_estimate = round(100 * known_count / teachable) if teachable else 0
    lesson.new_words = teachable - known_count


def _upsert_clip(
    session: Session, uid: str, lesson: LessonOut, media_uri: str | None
) -> None:
    clip = session.get(models.Clip, lesson.clip_id)
    if clip is None:
        session.add(
            models.Clip(
                id=lesson.clip_id,
                owner_uid=uid,
                title=lesson.title,
                duration_ms=lesson.duration_ms,
                line_count=lesson.line_count,
                difficulty=lesson.difficulty,
                local_media_uri=media_uri,
            )
        )
        return
    clip.title = lesson.title
    if media_uri:
        clip.local_media_uri = media_uri


def _enforce_daily_limit(session: Session, uid: str) -> None:
    """Cost guardrail. Present from day one, not after the first bill."""
    today_count = session.scalar(
        select(func.count())
        .select_from(models.Clip)
        .where(
            models.Clip.owner_uid == uid,
            func.date(models.Clip.created_at) == func.date(func.now()),
        )
    )
    if (today_count or 0) >= settings.daily_lesson_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="daily lesson limit reached, try again tomorrow",
        )
