"""Initial schema: users, clips, lessons, words, reviews

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("uid", sa.String(length=128), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("daily_goal_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("streak_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_active_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "clips",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("owner_uid", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("difficulty", sa.String(length=8), nullable=False, server_default="unknown"),
        sa.Column("local_media_uri", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_uid"], ["users.uid"], ondelete="CASCADE"),
    )
    op.create_index("ix_clips_owner_uid", "clips", ["owner_uid"])

    # Lesson payloads are shared across users: the key is the subtitle content
    # hash, so re-importing the same scene costs nothing.
    op.create_table(
        "lessons",
        sa.Column("clip_id", sa.String(length=32), primary_key=True),
        sa.Column("engine", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "words",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_uid", sa.String(length=128), nullable=False),
        sa.Column("lemma", sa.String(length=64), nullable=False),
        sa.Column("surface", sa.String(length=64), nullable=False),
        sa.Column("reading", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("romaji", sa.String(length=96), nullable=False, server_default=""),
        sa.Column("meaning", sa.Text(), nullable=False, server_default=""),
        sa.Column("jlpt", sa.String(length=8), nullable=True),
        sa.Column("context_japanese", sa.Text(), nullable=False, server_default=""),
        sa.Column("context_english", sa.Text(), nullable=False, server_default=""),
        sa.Column("clip_id", sa.String(length=32), nullable=True),
        sa.Column("start_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("end_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stability", sa.Float(), nullable=False, server_default="0"),
        sa.Column("difficulty", sa.Float(), nullable=False, server_default="5"),
        sa.Column("reps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lapses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_uid"], ["users.uid"], ondelete="CASCADE"),
        # One card per dictionary form per user, so every inflection of a verb
        # maps onto the same review item.
        sa.UniqueConstraint("owner_uid", "lemma", name="uq_words_owner_lemma"),
    )
    op.create_index("ix_words_owner_uid", "words", ["owner_uid"])
    # The hot query: "what is due for this user right now".
    op.create_index("ix_words_due", "words", ["owner_uid", "due_at"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("word_id", sa.Integer(), nullable=False),
        sa.Column("owner_uid", sa.String(length=128), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["word_id"], ["words.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_reviews_word_id", "reviews", ["word_id"])
    op.create_index("ix_reviews_owner_uid", "reviews", ["owner_uid"])


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_index("ix_words_due", table_name="words")
    op.drop_index("ix_words_owner_uid", table_name="words")
    op.drop_table("words")
    op.drop_table("lessons")
    op.drop_index("ix_clips_owner_uid", table_name="clips")
    op.drop_table("clips")
    op.drop_table("users")
