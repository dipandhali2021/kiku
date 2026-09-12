"""Vocabulary endpoints: save a word, list saved words, delete."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import srs
from app.auth import CurrentUser, current_user
from app.db import models
from app.db.session import get_session
from app.repository import ensure_user
from app.schemas import WordCreate, WordOut

router = APIRouter(prefix="/words", tags=["words"])


def _to_out(word: models.Word) -> WordOut:
    state = srs.ReviewState(
        stability=word.stability,
        difficulty=word.difficulty,
        reps=word.reps,
        lapses=word.lapses,
        due_at=word.due_at,
        last_reviewed_at=word.last_reviewed_at,
    )
    out = WordOut.model_validate(word)
    out.interval_days = srs.interval_days(state)
    return out


@router.post("", response_model=WordOut, status_code=status.HTTP_201_CREATED)
def save_word(
    payload: WordCreate,
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> WordOut:
    """Save a word tapped inside a lesson.

    Idempotent per lemma: tapping the same word twice updates the context
    rather than creating a duplicate, because seeing a word in a second scene
    is a reason to enrich the card, not to split it.
    """
    ensure_user(session, user)

    existing = session.scalar(
        select(models.Word).where(
            models.Word.owner_uid == user.uid, models.Word.lemma == payload.lemma
        )
    )
    if existing is not None:
        if payload.context_japanese:
            existing.context_japanese = payload.context_japanese
            existing.context_english = payload.context_english
            existing.clip_id = payload.clip_id
            existing.start_ms = payload.start_ms
            existing.end_ms = payload.end_ms
        session.flush()
        return _to_out(existing)

    word = models.Word(
        owner_uid=user.uid,
        # New words are due immediately so the first review can happen today.
        due_at=datetime.now(timezone.utc),
        **payload.model_dump(),
    )
    session.add(word)
    session.flush()
    return _to_out(word)


@router.get("", response_model=list[WordOut])
def list_words(
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
    limit: int = 200,
) -> list[WordOut]:
    rows = session.scalars(
        select(models.Word)
        .where(models.Word.owner_uid == user.uid)
        .order_by(models.Word.created_at.desc())
        .limit(min(limit, 500))
    ).all()
    return [_to_out(row) for row in rows]


@router.delete("/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_word(
    word_id: int,
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> None:
    word = session.get(models.Word, word_id)
    if word is None or word.owner_uid != user.uid:
        raise HTTPException(status_code=404, detail="word not found")
    session.delete(word)
