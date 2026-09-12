"""Small data-access helpers shared by routers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import models


def ensure_user(session: Session, user: CurrentUser) -> models.User:
    """Create the user row on first contact.

    Firebase is the identity provider, so the first authenticated request is
    also the sign-up. There is no separate registration endpoint.
    """
    row = session.get(models.User, user.uid)
    if row is None:
        row = models.User(
            uid=user.uid, email=user.email, is_anonymous=user.is_anonymous
        )
        session.add(row)
        session.flush()
        return row

    # An anonymous account that linked a credential keeps the same uid.
    if user.email and row.email != user.email:
        row.email = user.email
    row.is_anonymous = user.is_anonymous
    return row


def known_lemmas(session: Session, uid: str) -> set[str]:
    """Every word the learner has saved, by lemma and surface."""
    rows = session.execute(
        select(models.Word.lemma, models.Word.surface).where(
            models.Word.owner_uid == uid
        )
    ).all()
    known: set[str] = set()
    for lemma, surface in rows:
        known.add(lemma)
        known.add(surface)
    return known


def touch_streak(session: Session, uid: str, now: datetime | None = None) -> int:
    """Update the streak on activity.

    Guilt-free by design: a single missed day does not reset to zero, it drops
    the streak by one. Losing 40 days of work to one bad day is the main reason
    people abandon streak-based apps.
    """
    now = now or datetime.now(timezone.utc)
    user = session.get(models.User, uid)
    if user is None:
        return 0

    today = now.date()
    last = user.last_active_on.date() if user.last_active_on else None

    if last == today:
        return user.streak_days
    if last is None:
        user.streak_days = 1
    elif last == today - timedelta(days=1):
        user.streak_days += 1
    elif last == today - timedelta(days=2):
        user.streak_days = max(1, user.streak_days - 1)  # one grace day
    else:
        user.streak_days = 1

    user.last_active_on = now
    return user.streak_days


def reviews_today(session: Session, uid: str, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    return (
        session.scalar(
            select(func.count())
            .select_from(models.Review)
            .where(models.Review.owner_uid == uid, models.Review.reviewed_at >= start)
        )
        or 0
    )
