"""Kana utilities: katakana/hiragana conversion and Hepburn romanisation.

Pure standard library on purpose. This module has no external dependency so
it can be tested anywhere and reused in a CLI without the web stack.
"""

from __future__ import annotations

HIRAGANA_START = 0x3041
HIRAGANA_END = 0x3096
KATAKANA_START = 0x30A1
KATAKANA_END = 0x30F6
KANA_OFFSET = KATAKANA_START - HIRAGANA_START

# Two-character digraphs must be matched before single characters.
_DIGRAPHS = {
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo",
    "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
    "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
    "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
    "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo",
    "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
    "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo",
    "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
    "じゃ": "ja", "じゅ": "ju", "じょ": "jo",
    "ぢゃ": "ja", "ぢゅ": "ju", "ぢょ": "jo",
    "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
    "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",
    "てぃ": "ti", "でぃ": "di", "どぅ": "du",
    "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo",
    "うぇ": "we", "うぃ": "wi", "ゔぁ": "va",
}

_MONOGRAPHS = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "ゐ": "wi", "ゑ": "we", "を": "o", "ん": "n",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o",
    "ゃ": "ya", "ゅ": "yu", "ょ": "yo", "ゎ": "wa", "ゕ": "ka",
    "ー": "\u0304",  # placeholder, resolved as a long vowel below
    "、": ", ", "。": ". ", "！": "!", "？": "?", "　": " ",
}

_SOKUON = "っ"
_CHOONPU = "ー"
_VOWELS = "aiueo"


def is_kana(ch: str) -> bool:
    return HIRAGANA_START <= ord(ch) <= HIRAGANA_END or KATAKANA_START <= ord(ch) <= KATAKANA_END


def is_kanji(ch: str) -> bool:
    code = ord(ch)
    return 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF


def has_kanji(text: str) -> bool:
    return any(is_kanji(ch) for ch in text)


def to_hiragana(text: str) -> str:
    """Convert katakana to hiragana, leaving everything else untouched."""
    out = []
    for ch in text:
        if KATAKANA_START <= ord(ch) <= KATAKANA_END:
            out.append(chr(ord(ch) - KANA_OFFSET))
        else:
            out.append(ch)
    return "".join(out)


def to_katakana(text: str) -> str:
    out = []
    for ch in text:
        if HIRAGANA_START <= ord(ch) <= HIRAGANA_END:
            out.append(chr(ord(ch) + KANA_OFFSET))
        else:
            out.append(ch)
    return "".join(out)


def to_romaji(text: str) -> str:
    """Modified Hepburn romanisation of kana text.

    Handles digraphs, the sokuon (small tsu) as a doubled consonant, the long
    vowel mark, and syllabic n before vowels (kon'ya, not konya).
    """
    kana = to_hiragana(text)
    out: list[str] = []
    i = 0
    pending_sokuon = False

    while i < len(kana):
        two = kana[i : i + 2]
        one = kana[i]

        if one == _SOKUON:
            pending_sokuon = True
            i += 1
            continue

        if one == _CHOONPU:
            # Lengthen the previous vowel by repeating it.
            if out and out[-1] and out[-1][-1] in _VOWELS:
                out.append(out[-1][-1])
            i += 1
            continue

        if two in _DIGRAPHS:
            syllable = _DIGRAPHS[two]
            i += 2
        elif one in _MONOGRAPHS:
            syllable = _MONOGRAPHS[one]
            i += 1
        else:
            # Not kana (kanji, latin, punctuation): pass through unchanged.
            out.append(one)
            i += 1
            pending_sokuon = False
            continue

        if pending_sokuon and syllable and syllable[0].isalpha():
            syllable = syllable[0] + syllable
            pending_sokuon = False

        # Syllabic n followed by a vowel or y needs an apostrophe.
        if out and out[-1] == "n" and syllable and syllable[0] in _VOWELS + "y":
            out.append("'")

        out.append(syllable)

    return "".join(out).strip()
