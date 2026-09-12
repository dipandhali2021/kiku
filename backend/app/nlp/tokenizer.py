"""Japanese tokenisation with a pluggable engine.

Production uses MeCab + UniDic through fugashi, which gives dictionary forms,
readings, and part of speech. That is a native dependency with a large
dictionary, so this module degrades to a dictionary-driven longest-match
tokeniser when fugashi is unavailable. The fallback keeps the whole pipeline
testable in CI and on a laptop without a build toolchain.

Swapping engines never changes the output shape: always a list of Token.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from . import kana
from .dictionary import Dictionary, get_dictionary

# Particles and auxiliaries we always want split off, longest first.
_FUNCTION_WORDS = [
    "てくれない",
    "なきゃ",
    "たくて",
    "けど",
    "のに",
    "から",
    "まで",
    "より",
    "だけ",
    "でも",
    "しか",
    "ねえ",
    "の？",
    "の",
    "は",
    "が",
    "を",
    "に",
    "で",
    "と",
    "も",
    "や",
    "よ",
    "な",
    "か",
    "ね",
    "さ",
    "わ",
    "ぞ",
]

_PUNCTUATION = "、。！？!?「」　 …・"


@dataclass(slots=True)
class Token:
    """One surface token in a line."""

    surface: str
    reading: str = ""
    lemma: str = ""
    pos: str = "unknown"
    start: int = 0

    @property
    def end(self) -> int:
        return self.start + len(self.surface)

    @property
    def is_punctuation(self) -> bool:
        return all(ch in _PUNCTUATION for ch in self.surface)

    @property
    def romaji(self) -> str:
        source = self.reading or self.surface
        return kana.to_romaji(source) if source else ""

    @property
    def teachable(self) -> bool:
        """Whether this token is worth offering as a tappable vocabulary item."""
        if self.is_punctuation or not self.surface.strip():
            return False
        return self.pos not in {"particle", "punctuation"}


class Tokenizer:
    """Base interface. Engines implement `tokenize`."""

    name = "base"

    def tokenize(self, text: str) -> list[Token]:  # pragma: no cover - interface
        raise NotImplementedError


class FugashiTokenizer(Tokenizer):
    """MeCab + UniDic. The production engine."""

    name = "fugashi"

    _POS_MAP = {
        "名詞": "noun",
        "動詞": "verb",
        "形容詞": "adjective",
        "形状詞": "adjectival-noun",
        "副詞": "adverb",
        "助詞": "particle",
        "助動詞": "auxiliary",
        "接続詞": "conjunction",
        "感動詞": "interjection",
        "連体詞": "determiner",
        "代名詞": "pronoun",
        "接頭辞": "prefix",
        "接尾辞": "suffix",
        "補助記号": "punctuation",
    }

    def __init__(self) -> None:
        import fugashi  # noqa: PLC0415 - optional dependency, imported lazily

        self._tagger = fugashi.Tagger()

    def tokenize(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        cursor = 0
        for word in self._tagger(text):
            surface = word.surface
            start = text.find(surface, cursor)
            if start < 0:
                start = cursor
            cursor = start + len(surface)
            features = word.feature
            pos_raw = getattr(features, "pos1", "") or ""
            reading = getattr(features, "kana", None) or getattr(features, "pron", "") or ""
            lemma = getattr(features, "lemma", None) or surface
            tokens.append(
                Token(
                    surface=surface,
                    reading=kana.to_hiragana(reading),
                    lemma=lemma,
                    pos=self._POS_MAP.get(pos_raw, "unknown"),
                    start=start,
                )
            )
        return tokens


class LongestMatchTokenizer(Tokenizer):
    """Dictionary-driven fallback engine.

    Greedy longest match against the bundled dictionary, with function words
    and character-class boundaries as backstops. Not as accurate as MeCab, but
    deterministic, dependency-free, and good enough to develop the whole app
    against.
    """

    name = "longest-match"
    _MAX_WORD = 8

    def __init__(self, dictionary: Dictionary | None = None) -> None:
        self._dict = dictionary or get_dictionary()

    def tokenize(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        i = 0
        n = len(text)

        while i < n:
            ch = text[i]

            if ch in _PUNCTUATION:
                tokens.append(Token(surface=ch, pos="punctuation", start=i))
                i += 1
                continue

            matched = self._match_dictionary(text, i)
            if matched is None:
                matched = self._match_function_word(text, i)
            if matched is None:
                matched = self._match_by_character_class(text, i)

            tokens.append(matched)
            i = matched.end

        return tokens

    def _match_dictionary(self, text: str, i: int) -> Token | None:
        for length in range(min(self._MAX_WORD, len(text) - i), 0, -1):
            candidate = text[i : i + length]
            entry = self._dict.lookup_exact(candidate)
            if entry is not None and (length > 1 or kana.is_kanji(candidate)):
                return Token(
                    surface=candidate,
                    reading=entry.reading,
                    lemma=entry.lemma or candidate,
                    pos=entry.pos,
                    start=i,
                )
        return None

    def _match_function_word(self, text: str, i: int) -> Token | None:
        for word in _FUNCTION_WORDS:
            if text.startswith(word, i):
                entry = self._dict.lookup_exact(word)
                return Token(
                    surface=word,
                    reading=entry.reading if entry else word,
                    lemma=word,
                    pos=entry.pos if entry else "particle",
                    start=i,
                )
        return None

    def _match_by_character_class(self, text: str, i: int) -> Token:
        """Group a run of the same script as one token."""

        def script_of(ch: str) -> str:
            if kana.is_kanji(ch):
                return "kanji"
            if 0x30A1 <= ord(ch) <= 0x30FF:
                return "katakana"
            if 0x3041 <= ord(ch) <= 0x3096:
                return "hiragana"
            return "other"

        script = script_of(text[i])
        j = i + 1
        limit = i + self._MAX_WORD
        while j < len(text) and j < limit and script_of(text[j]) == script:
            if text[j] in _PUNCTUATION:
                break
            # Stop before a known function word so particles stay separate.
            if script == "hiragana" and any(
                text.startswith(word, j) for word in _FUNCTION_WORDS if len(word) > 1
            ):
                break
            j += 1

        surface = text[i:j]
        reading = surface if script in {"hiragana", "katakana"} else ""
        pos = "particle" if surface in _FUNCTION_WORDS else "unknown"
        return Token(
            surface=surface,
            reading=kana.to_hiragana(reading),
            lemma=surface,
            pos=pos,
            start=i,
        )


@lru_cache(maxsize=1)
def get_tokenizer() -> Tokenizer:
    """Return the best available engine, preferring MeCab."""
    try:
        return FugashiTokenizer()
    except Exception:  # noqa: BLE001 - any import/dictionary failure falls back
        return LongestMatchTokenizer()


def tokenize(text: str) -> list[Token]:
    return get_tokenizer().tokenize(text)
