"""Vocabulary dictionary.

Production loads JMdict, JMnedict, and KANJIDIC into SQLite at image build
time. For the MVP this wraps a seed JSON file with the same interface, so the
swap later is one class, not a rewrite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import kana

_SEED_PATH = Path(__file__).parent / "data" / "seed_dict.json"


@dataclass(slots=True)
class Entry:
    """One dictionary entry."""

    surface: str
    reading: str = ""
    lemma: str = ""
    pos: str = "unknown"
    glosses: list[str] = field(default_factory=list)
    jlpt: str | None = None
    note: str | None = None
    frequency: int = 0

    @property
    def gloss(self) -> str:
        return "; ".join(self.glosses[:3])

    @property
    def romaji(self) -> str:
        return kana.to_romaji(self.reading or self.surface)


class Dictionary:
    """Surface- and reading-indexed lookup."""

    def __init__(self, entries: list[Entry]) -> None:
        self._by_surface: dict[str, Entry] = {}
        self._by_lemma: dict[str, Entry] = {}
        for entry in entries:
            existing = self._by_surface.get(entry.surface)
            if existing is None or entry.frequency > existing.frequency:
                self._by_surface[entry.surface] = entry
            if entry.lemma:
                self._by_lemma.setdefault(entry.lemma, entry)

    def __len__(self) -> int:
        return len(self._by_surface)

    def lookup_exact(self, surface: str) -> Entry | None:
        """Exact surface or lemma match only.

        Tokenisation must use this rather than `lookup`: de-inflection
        candidates include trimmed forms, so a greedy matcher would happily
        accept もう行 as a match for もう and swallow the next word.
        """
        return self._by_surface.get(surface) or self._by_lemma.get(surface)

    def lookup(self, surface: str) -> Entry | None:
        """Exact match, then a de-inflected guess. For known token surfaces."""
        entry = self.lookup_exact(surface)
        if entry is not None:
            return entry
        for candidate in deinflect(surface):
            entry = self._by_surface.get(candidate) or self._by_lemma.get(candidate)
            if entry is not None:
                return entry
        return None

    def known_surfaces(self) -> set[str]:
        return set(self._by_surface)


# Ordered suffix rules: (inflected ending, dictionary-form ending).
# Deliberately small. MeCab handles this properly in production; these rules
# only need to cover the conversational forms that show up in subtitles.
_DEINFLECT_RULES: list[tuple[str, str]] = [
    ("していません", "する"),
    ("している", "する"),
    ("しました", "する"),
    ("します", "する"),
    ("した", "する"),
    ("して", "する"),
    ("って", "つ"),
    ("った", "つ"),
    ("んで", "む"),
    ("んだ", "む"),
    ("いて", "く"),
    ("いた", "く"),
    ("いで", "ぐ"),
    ("いだ", "ぐ"),
    ("して", "す"),
    ("した", "す"),
    ("えて", "える"),
    ("えた", "える"),
    ("けて", "ける"),
    ("けた", "ける"),
    ("てて", "てる"),
    ("ない", "る"),
    ("ます", "る"),
    ("ました", "る"),
    ("たい", "る"),
    ("て", "る"),
    ("た", "る"),
    ("くない", "い"),
    ("くて", "い"),
    ("く", "い"),
    ("くても", "い"),
]


def deinflect(surface: str) -> list[str]:
    """Candidate dictionary forms for an inflected surface, best guess first."""
    candidates: list[str] = []
    for ending, replacement in _DEINFLECT_RULES:
        if surface.endswith(ending) and len(surface) > len(ending):
            candidates.append(surface[: -len(ending)] + replacement)
    # Bare stem, for cases like 見た -> 見
    if len(surface) > 1:
        candidates.append(surface[:-1])
        candidates.append(surface[:-1] + "る")
        candidates.append(surface[:-1] + "す")
    return candidates


def _load_entries(path: Path = _SEED_PATH) -> list[Entry]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Entry(**item) for item in raw]


@lru_cache(maxsize=1)
def get_dictionary() -> Dictionary:
    return Dictionary(_load_entries())
