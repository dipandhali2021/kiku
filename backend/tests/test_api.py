"""End-to-end API tests.

Requires the web dependencies (fastapi, sqlalchemy, httpx). Runs in CI and in
local development via `uv run pytest`.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("AUTH_DEV_MODE", "true")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_kiku.db")

from tests.test_nlp import SAMPLE_SRT  # noqa: E402

AUTH = {"Authorization": "Bearer dev:test-user"}
OTHER = {"Authorization": "Bearer dev:other-user"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient backed by a throwaway SQLite file."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'kiku.db'}")

    # Reload the modules that captured settings at import time.
    import importlib

    from app import config

    importlib.reload(config)
    from app.db import session as db_session

    importlib.reload(db_session)
    from app import main

    importlib.reload(main)

    from fastapi.testclient import TestClient

    with TestClient(main.app) as test_client:
        yield test_client


def test_health_reports_engines(client) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["dictionary_entries"] > 0
    assert body["tokenizer"] in {"fugashi", "longest-match"}


def test_auth_is_required(client) -> None:
    assert client.get("/words").status_code == 401
    assert client.post("/lessons", json={"subtitles": SAMPLE_SRT}).status_code == 401


def test_import_clip_returns_lesson(client) -> None:
    response = client.post(
        "/lessons",
        json={"title": "Cafe scene", "subtitles": SAMPLE_SRT},
        headers=AUTH,
    )
    assert response.status_code == 201
    lesson = response.json()
    assert lesson["title"] == "Cafe scene"
    assert lesson["line_count"] == 3
    assert lesson["lines"][0]["romaji"]
    assert any(w["meaning"] for w in lesson["lines"][0]["words"])


def test_reimporting_the_same_clip_is_a_cache_hit(client) -> None:
    first = client.post("/lessons", json={"subtitles": SAMPLE_SRT}, headers=AUTH).json()
    second = client.post("/lessons", json={"subtitles": SAMPLE_SRT}, headers=AUTH).json()
    assert first["clip_id"] == second["clip_id"]

    fetched = client.get(f"/lessons/{first['clip_id']}", headers=AUTH)
    assert fetched.status_code == 200
    assert fetched.json()["line_count"] == first["line_count"]


def test_blank_and_untranslatable_subtitles_are_rejected(client) -> None:
    assert client.post("/lessons", json={"subtitles": "   "}, headers=AUTH).status_code == 422
    english_only = "1\n00:00:01,000 --> 00:00:02,000\nHello there.\n"
    assert (
        client.post("/lessons", json={"subtitles": english_only}, headers=AUTH).status_code
        == 422
    )


def test_save_word_then_review_it(client) -> None:
    lesson = client.post("/lessons", json={"subtitles": SAMPLE_SRT}, headers=AUTH).json()
    word = next(w for w in lesson["lines"][0]["words"] if w["teachable"])

    saved = client.post(
        "/words",
        json={
            "lemma": word["lemma"],
            "surface": word["surface"],
            "reading": word["reading"],
            "romaji": word["romaji"],
            "meaning": word["meaning"],
            "context_japanese": lesson["lines"][0]["japanese"],
            "clip_id": lesson["clip_id"],
        },
        headers=AUTH,
    )
    assert saved.status_code == 201
    word_id = saved.json()["id"]

    # A newly saved word is due immediately.
    due = client.get("/reviews", headers=AUTH).json()
    assert word_id in [item["id"] for item in due]

    graded = client.post(
        "/reviews", json={"word_id": word_id, "grade": 2}, headers=AUTH
    )
    assert graded.status_code == 201
    assert graded.json()["interval_days"] >= 1

    # Now scheduled in the future, so the queue is empty.
    assert client.get("/reviews", headers=AUTH).json() == []


def test_saving_the_same_word_twice_does_not_duplicate(client) -> None:
    payload = {"lemma": "待つ", "surface": "待って", "meaning": "to wait"}
    client.post("/words", json=payload, headers=AUTH)
    client.post("/words", json=payload, headers=AUTH)
    assert len(client.get("/words", headers=AUTH).json()) == 1


def test_saved_words_raise_comprehension_on_next_import(client) -> None:
    lesson = client.post("/lessons", json={"subtitles": SAMPLE_SRT}, headers=AUTH).json()
    before = lesson["comprehension_estimate"]

    for line in lesson["lines"]:
        for word in line["words"]:
            if word["teachable"]:
                client.post(
                    "/words",
                    json={"lemma": word["lemma"], "surface": word["surface"]},
                    headers=AUTH,
                )

    after = client.get(f"/lessons/{lesson['clip_id']}", headers=AUTH).json()
    assert after["comprehension_estimate"] > before
    assert after["new_words"] == 0


def test_users_cannot_touch_each_others_words(client) -> None:
    saved = client.post(
        "/words", json={"lemma": "私", "surface": "私"}, headers=AUTH
    ).json()
    assert client.get("/words", headers=OTHER).json() == []
    assert client.delete(f"/words/{saved['id']}", headers=OTHER).status_code == 404
    assert (
        client.post(
            "/reviews", json={"word_id": saved["id"], "grade": 2}, headers=OTHER
        ).status_code
        == 404
    )


def test_progress_reflects_activity(client) -> None:
    client.post("/lessons", json={"subtitles": SAMPLE_SRT}, headers=AUTH)
    saved = client.post(
        "/words", json={"lemma": "ちょっと", "surface": "ちょっと"}, headers=AUTH
    ).json()
    client.post("/reviews", json={"word_id": saved["id"], "grade": 2}, headers=AUTH)

    progress = client.get("/progress", headers=AUTH).json()
    assert progress["saved_words"] == 1
    assert progress["clips_imported"] == 1
    assert progress["reviews_today"] == 1
    assert progress["streak_days"] == 1
    assert progress["due_now"] == 0


def test_oversized_subtitles_are_rejected(client, monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "max_subtitle_bytes", 100)
    big = SAMPLE_SRT * 20
    assert client.post("/lessons", json={"subtitles": big}, headers=AUTH).status_code == 413
