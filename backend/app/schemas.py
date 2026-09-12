"""Request and response models.

These are the API contract. `shared/lesson.schema.json` mirrors them so the
Android data classes and the backend cannot drift apart silently.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class WordChipOut(BaseModel):
    surface: str
    reading: str = ""
    romaji: str = ""
    meaning: str = ""
    pos: str = "unknown"
    lemma: str = ""
    jlpt: str | None = None
    note: str | None = None
    start: int = 0
    end: int = 0
    known: bool = False
    teachable: bool = True
    in_dictionary: bool = True


class LessonLineOut(BaseModel):
    index: int
    start_ms: int
    end_ms: int
    japanese: str
    romaji: str
    english: str = ""
    nuance: str = ""
    register: str = ""
    speaker: str | None = None
    words: list[WordChipOut] = Field(default_factory=list)


class LessonOut(BaseModel):
    clip_id: str
    title: str
    engine: str
    duration_ms: int
    line_count: int
    difficulty: str
    comprehension_estimate: int
    new_words: int
    lines: list[LessonLineOut] = Field(default_factory=list)
    dropped_cues: int = 0


class LessonCreate(BaseModel):
    """Import a clip. Only subtitle text crosses the network."""

    title: str = Field(default="Untitled clip", max_length=300)
    subtitles: str = Field(min_length=1, description=".srt or .vtt content")
    local_media_uri: str | None = Field(
        default=None,
        description="Opaque on-device identifier. The video is never uploaded.",
    )
    max_lines: int | None = Field(default=None, ge=1, le=500)

    @field_validator("subtitles")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("subtitles must not be blank")
        return value


class WordCreate(BaseModel):
    """Save a word from a lesson into the review queue."""

    lemma: str = Field(min_length=1, max_length=64)
    surface: str = Field(min_length=1, max_length=64)
    reading: str = ""
    romaji: str = ""
    meaning: str = ""
    jlpt: str | None = None
    context_japanese: str = ""
    context_english: str = ""
    clip_id: str | None = None
    start_ms: int = 0
    end_ms: int = 0


class WordOut(BaseModel):
    id: int
    lemma: str
    surface: str
    reading: str
    romaji: str
    meaning: str
    jlpt: str | None = None
    context_japanese: str = ""
    context_english: str = ""
    clip_id: str | None = None
    start_ms: int = 0
    end_ms: int = 0
    reps: int = 0
    lapses: int = 0
    due_at: datetime | None = None
    interval_days: int = 0

    model_config = {"from_attributes": True}


class ReviewCreate(BaseModel):
    """Grade a word. 0 again, 1 hard, 2 good, 3 easy."""

    word_id: int
    grade: int = Field(ge=0, le=3)
    elapsed_ms: int = Field(default=0, ge=0)


class ReviewResult(BaseModel):
    word_id: int
    grade: int
    reps: int
    due_at: datetime | None
    interval_days: int


class ClipOut(BaseModel):
    id: str
    title: str
    duration_ms: int
    line_count: int
    difficulty: str
    local_media_uri: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProgressOut(BaseModel):
    """What the Today screen shows."""

    saved_words: int
    due_now: int
    reviews_today: int
    streak_days: int
    clips_imported: int


class HealthOut(BaseModel):
    status: str
    version: str
    environment: str
    tokenizer: str
    llm: str
    dictionary_entries: int
