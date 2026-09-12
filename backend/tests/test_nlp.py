"""Tests for the language pipeline.

Deliberately fixture-free and dependency-free so this file can also be run
without pytest installed:

    python -c "import tests.test_nlp as t; t.run_all()"
"""

from __future__ import annotations

from app.lessons.builder import LessonBuilder
from app.nlp import kana, subtitles as srt
from app.nlp.dictionary import deinflect, get_dictionary
from app.nlp.tokenizer import LongestMatchTokenizer

SAMPLE_SRT = """1
00:00:01,120 --> 00:00:03,480
<i>あおい：</i>もう行かなきゃ。

2
00:00:03,900 --> 00:00:06,020
あおい：ちょっと待ってくれない？

3
00:00:06,400 --> 00:00:08,150
{\\an8}ゆうた：えっ、どうしたの？

4
00:00:19,400 --> 00:00:21,000
♪ ～♪
"""


# -- kana ------------------------------------------------------------------


def test_romaji_basic_syllables() -> None:
    assert kana.to_romaji("ありがとう") == "arigatou"
    assert kana.to_romaji("こんにちは") == "konnichiha"


def test_romaji_handles_digraphs() -> None:
    assert kana.to_romaji("とうきょう") == "toukyou"
    assert kana.to_romaji("しゅくだい") == "shukudai"


def test_romaji_doubles_consonant_for_sokuon() -> None:
    # The small tsu is the classic romanisation bug: 待って is "matte", not "mate".
    assert kana.to_romaji("まって") == "matte"
    assert kana.to_romaji("きっと") == "kitto"


def test_romaji_lengthens_vowel_for_choonpu() -> None:
    assert kana.to_romaji("コーヒー") == "koohii"


def test_romaji_separates_syllabic_n() -> None:
    # Without the apostrophe こんや would read as "konya" (ko-nya).
    assert kana.to_romaji("こんや") == "kon'ya"


def test_katakana_to_hiragana() -> None:
    assert kana.to_hiragana("カタカナ") == "かたかな"
    assert kana.to_katakana("ひらがな") == "ヒラガナ"


def test_kanji_detection() -> None:
    assert kana.has_kanji("誕生日")
    assert not kana.has_kanji("おめでとう")


# -- subtitles -------------------------------------------------------------


def test_parse_extracts_timing_and_speaker() -> None:
    parsed = srt.parse(SAMPLE_SRT)
    first = parsed.cues[0]
    assert first.start_ms == 1120
    assert first.end_ms == 3480
    assert first.speaker == "あおい"
    assert first.text == "もう行かなきゃ。"


def test_parse_strips_markup() -> None:
    parsed = srt.parse(SAMPLE_SRT)
    # HTML italics and ASS override blocks must not reach the learner.
    assert all("<" not in cue.text and "{" not in cue.text for cue in parsed.cues)


def test_parse_drops_music_and_effect_cues() -> None:
    parsed = srt.parse(SAMPLE_SRT)
    assert parsed.dropped == 1
    assert all("♪" not in cue.text for cue in parsed.cues)


def test_parse_handles_vtt_and_crlf() -> None:
    vtt = "WEBVTT\r\n\r\n00:00:02.000 --> 00:00:04.000\r\nこれ、渡したくてさ。\r\n"
    parsed = srt.parse(vtt)
    assert len(parsed.cues) == 1
    assert parsed.cues[0].start_ms == 2000


def test_merge_joins_sentence_split_across_cues() -> None:
    split = (
        "1\n00:00:13,200 --> 00:00:16,400\n遅くなったけど、\n\n"
        "2\n00:00:16,480 --> 00:00:18,900\n誕生日おめでとう。\n"
    )
    parsed = srt.parse(split)
    assert len(parsed.cues) == 1
    assert parsed.cues[0].text == "遅くなったけど、誕生日おめでとう。"
    assert parsed.cues[0].end_ms == 18900


def test_merge_keeps_separate_sentences_apart() -> None:
    two = (
        "1\n00:00:01,000 --> 00:00:02,000\nありがとう。\n\n"
        "2\n00:00:02,100 --> 00:00:03,000\n本当にありがとう。\n"
    )
    assert len(srt.parse(two).cues) == 2


# -- dictionary and tokenizer ---------------------------------------------


def test_dictionary_loads_seed_entries() -> None:
    assert len(get_dictionary()) > 40


def test_deinflect_finds_dictionary_form() -> None:
    assert "待つ" in deinflect("待って")


def test_tokenizer_respects_word_boundaries() -> None:
    # Regression: greedy matching used to produce もう行 by trimming during lookup.
    tokens = LongestMatchTokenizer().tokenize("もう行かなきゃ。")
    surfaces = [t.surface for t in tokens]
    assert surfaces == ["もう", "行かなきゃ", "。"]


def test_tokenizer_splits_particles() -> None:
    tokens = LongestMatchTokenizer().tokenize("私に？")
    assert [t.surface for t in tokens] == ["私", "に", "？"]
    assert tokens[1].pos == "particle"


def test_tokenizer_marks_punctuation_not_teachable() -> None:
    tokens = LongestMatchTokenizer().tokenize("これ、")
    assert tokens[-1].is_punctuation
    assert not tokens[-1].teachable


# -- lesson builder --------------------------------------------------------


def test_builder_produces_teaching_lines() -> None:
    lesson = LessonBuilder().build(SAMPLE_SRT, title="Cafe")
    assert lesson.line_count == 3
    assert lesson.title == "Cafe"
    assert lesson.clip_id  # content hash

    first = lesson.lines[0]
    assert first.japanese == "もう行かなきゃ。"
    assert first.romaji.startswith("mou ikanakya")
    assert first.speaker == "あおい"


def test_builder_attaches_dictionary_meaning_and_nuance() -> None:
    lesson = LessonBuilder().build(SAMPLE_SRT)
    words = {w.surface: w for line in lesson.lines for w in line.words}
    assert "to go" in words["行かなきゃ"].meaning or words["行かなきゃ"].meaning
    assert words["行かなきゃ"].note  # grammar explanation, not just a gloss
    assert words["行かなきゃ"].romaji == "ikanakya"


def test_builder_marks_known_words_and_scores_comprehension() -> None:
    lesson = LessonBuilder().build(SAMPLE_SRT, known_words={"もう", "ちょっと"})
    known = [w.surface for line in lesson.lines for w in line.words if w.known]
    assert "もう" in known
    assert 0 < lesson.comprehension_estimate < 100


def test_builder_is_deterministic() -> None:
    # Same subtitles must produce the same clip id, or caching breaks.
    a = LessonBuilder().build(SAMPLE_SRT)
    b = LessonBuilder().build(SAMPLE_SRT)
    assert a.clip_id == b.clip_id
    assert a.to_dict() == b.to_dict()


def test_builder_respects_max_lines() -> None:
    lesson = LessonBuilder().build(SAMPLE_SRT, max_lines=2)
    assert lesson.line_count == 2


def run_all() -> int:
    """Run every test in this module without pytest. Returns failure count."""
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL {name}: {exc or 'assertion failed'}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{failures} failure(s)")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run_all() else 0)
