"""Turn subtitles into a lesson.

This is the core of Kiku. Everything else is plumbing.

Pipeline per clip:
  subtitles -> cues -> tokens -> dictionary lookup -> difficulty scoring
  -> teaching line (Japanese / romaji / English / nuance) -> lesson JSON

The LLM is only asked for what a dictionary cannot provide: natural
translation, register, and nuance notes. Everything mechanical stays local so
it is free, fast, and deterministic.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

from app.llm.client import LlmClient, SceneGloss, get_llm_client
from app.nlp import kana, subtitles as srt
from app.nlp.dictionary import Dictionary, get_dictionary
from app.nlp.tokenizer import Token, Tokenizer, get_tokenizer

# JLPT level ordering, easiest first.
_JLPT_ORDER = ["N5", "N4", "N3", "N2", "N1"]
_JLPT_WEIGHT = {"N5": 1, "N4": 2, "N3": 3, "N2": 4, "N1": 5}


@dataclass(slots=True)
class WordChip:
    """A tappable word inside a line."""

    surface: str
    reading: str
    romaji: str
    meaning: str
    pos: str
    lemma: str
    jlpt: str | None = None
    note: str | None = None
    start: int = 0
    end: int = 0
    known: bool = False
    teachable: bool = True
    in_dictionary: bool = True


@dataclass(slots=True)
class LessonLine:
    """One teaching unit: a single line of dialogue."""

    index: int
    start_ms: int
    end_ms: int
    japanese: str
    romaji: str
    english: str = ""
    nuance: str = ""
    register: str = ""
    speaker: str | None = None
    words: list[WordChip] = field(default_factory=list)

    @property
    def new_word_count(self) -> int:
        return sum(1 for w in self.words if w.teachable and not w.known)


@dataclass(slots=True)
class Lesson:
    """The payload the Android app renders."""

    clip_id: str
    title: str
    engine: str
    duration_ms: int
    line_count: int
    difficulty: str
    comprehension_estimate: int
    new_words: int
    lines: list[LessonLine] = field(default_factory=list)
    dropped_cues: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def clip_id_for(content: str) -> str:
    """Stable id from subtitle content, so re-importing is a cache hit."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


class LessonBuilder:
    def __init__(
        self,
        tokenizer: Tokenizer | None = None,
        dictionary: Dictionary | None = None,
        llm: LlmClient | None = None,
    ) -> None:
        self._tokenizer = tokenizer or get_tokenizer()
        self._dict = dictionary or get_dictionary()
        self._llm = llm or get_llm_client()

    def build(
        self,
        content: str,
        title: str = "Untitled clip",
        known_words: set[str] | None = None,
        max_lines: int | None = None,
    ) -> Lesson:
        known = known_words or set()
        parsed = srt.parse(content)
        cues = parsed.cues[:max_lines] if max_lines else parsed.cues

        lines = [self._build_line(cue, known) for cue in cues]
        glosses = self._llm.gloss_scene([line.japanese for line in lines])
        for line, gloss in zip(lines, glosses, strict=False):
            self._apply_gloss(line, gloss)

        comprehension = self._comprehension(lines)
        return Lesson(
            clip_id=clip_id_for(content),
            title=title,
            engine=self._tokenizer.name,
            duration_ms=parsed.duration_ms,
            line_count=len(lines),
            difficulty=self._difficulty(lines),
            comprehension_estimate=comprehension,
            new_words=sum(line.new_word_count for line in lines),
            lines=lines,
            dropped_cues=parsed.dropped,
        )

    # -- internals ---------------------------------------------------------

    def _build_line(self, cue: srt.Cue, known: set[str]) -> LessonLine:
        tokens = self._tokenizer.tokenize(cue.text)
        words = [self._build_chip(token, known) for token in tokens]
        return LessonLine(
            index=cue.index,
            start_ms=cue.start_ms,
            end_ms=cue.end_ms,
            japanese=cue.text,
            romaji=self._line_romaji(words),
            speaker=cue.speaker,
            words=words,
        )

    def _build_chip(self, token: Token, known: set[str]) -> WordChip:
        entry = self._dict.lookup(token.surface)
        reading = token.reading or (entry.reading if entry else "")
        if not reading and not kana.has_kanji(token.surface):
            reading = kana.to_hiragana(token.surface)
        lemma = token.lemma or (entry.lemma if entry else token.surface)

        return WordChip(
            surface=token.surface,
            reading=reading,
            romaji=kana.to_romaji(reading) if reading else "",
            meaning=entry.gloss if entry else "",
            pos=entry.pos if entry and entry.pos != "unknown" else token.pos,
            lemma=lemma,
            jlpt=entry.jlpt if entry else None,
            note=entry.note if entry else None,
            start=token.start,
            end=token.end,
            known=lemma in known or token.surface in known,
            teachable=token.teachable,
            in_dictionary=entry is not None,
        )

    @staticmethod
    def _line_romaji(words: list[WordChip]) -> str:
        parts: list[str] = []
        for word in words:
            if word.pos == "punctuation":
                parts.append(word.surface.replace("、", ",").replace("。", "."))
                continue
            piece = word.romaji or kana.to_romaji(word.surface)
            if piece:
                parts.append(piece)
        text = " ".join(parts)
        return text.replace(" ,", ",").replace(" .", ".").replace("  ", " ").strip()

    @staticmethod
    def _comprehension(lines: list[LessonLine]) -> int:
        """Rough share of teachable tokens the learner already knows."""
        teachable = [w for line in lines for w in line.words if w.teachable]
        if not teachable:
            return 0
        known = sum(1 for w in teachable if w.known)
        return round(100 * known / len(teachable))

    @staticmethod
    def _difficulty(lines: list[LessonLine]) -> str:
        """Report the JLPT level that covers ~80% of the vocabulary."""
        weights = [
            _JLPT_WEIGHT[w.jlpt]
            for line in lines
            for w in line.words
            if w.teachable and w.jlpt in _JLPT_WEIGHT
        ]
        if not weights:
            return "unknown"
        weights.sort()
        cutoff = weights[int(len(weights) * 0.8) - 1] if len(weights) > 1 else weights[0]
        return _JLPT_ORDER[min(cutoff, len(_JLPT_ORDER)) - 1]

    @staticmethod
    def _apply_gloss(line: LessonLine, gloss: SceneGloss | None) -> None:
        if gloss is None:
            return
        line.english = gloss.english
        line.nuance = gloss.nuance
        line.register = gloss.register
