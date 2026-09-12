"""Database schema.

Five tables is the whole MVP:
  users      one row per Firebase uid
  clips      an imported subtitle file (metadata only, never the video)
  lessons    cached lesson JSON keyed by subtitle content hash
  words      the learner's vocabulary with SRS state
  reviews    an append-only log of every grade, for analytics and re-tuning

The reviews log matters: it lets us replay history against new SRS weights
without asking users to re-learn anything.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    # Firebase uid is the primary key: no separate identity table to keep in sync.
    uid: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(default=True)
    daily_goal_minutes: Mapped[int] = mapped_column(Integer, default=5)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_active_on: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    words: Mapped[list[Word]] = relationship(back_populates="user")


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # content hash
    owner_uid: Mapped[str] = mapped_column(
        ForeignKey("users.uid", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    line_count: Mapped[int] = mapped_column(Integer, default=0)
    difficulty: Mapped[str] = mapped_column(String(8), default="unknown")
    # Local file identifier on the device. The video itself never leaves the phone.
    local_media_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Lesson(Base):
    """Cached lesson payload, shared across users who import the same clip."""

    __tablename__ = "lessons"

    clip_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    engine: Mapped[str] = mapped_column(String(32), default="unknown")
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Word(Base):
    """A saved vocabulary item with its SRS state."""

    __tablename__ = "words"
    __table_args__ = (
        UniqueConstraint("owner_uid", "lemma", name="uq_words_owner_lemma"),
        Index("ix_words_due", "owner_uid", "due_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_uid: Mapped[str] = mapped_column(
        ForeignKey("users.uid", ondelete="CASCADE"), index=True
    )
    lemma: Mapped[str] = mapped_column(String(64))
    surface: Mapped[str] = mapped_column(String(64))
    reading: Mapped[str] = mapped_column(String(64), default="")
    romaji: Mapped[str] = mapped_column(String(96), default="")
    meaning: Mapped[str] = mapped_column(Text, default="")
    jlpt: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # The sentence the word was learned in. Context is what makes it stick,
    # and it is what the review card shows.
    context_japanese: Mapped[str] = mapped_column(Text, default="")
    context_english: Mapped[str] = mapped_column(Text, default="")
    clip_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    start_ms: Mapped[int] = mapped_column(Integer, default=0)
    end_ms: Mapped[int] = mapped_column(Integer, default=0)

    # SRS state (see app/srs.py)
    stability: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, default=5.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="words")


class Review(Base):
    """Append-only grade log. Never updated, never deleted."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), index=True
    )
    owner_uid: Mapped[str] = mapped_column(String(128), index=True)
    grade: Mapped[int] = mapped_column(Integer)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
