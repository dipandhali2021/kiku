"""Subtitle parsing for .srt and .vtt, plus line cleanup.

Real-world subtitle files are messy: styling tags, karaoke timing, speaker
labels, and lines split across cues mid-sentence. We normalise all of that
before any tokenisation happens, because a naive parser produces lessons that
teach fragments instead of sentences.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_TIME_SRT = re.compile(
    r"(?P<h>\d+):(?P<m>\d{2}):(?P<s>\d{2})[,.](?P<ms>\d{1,3})"
)
_ARROW = re.compile(r"\s*-->\s*")
_ASS_OVERRIDE = re.compile(r"\{[^}]*\}")
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_SPEAKER = re.compile(r"^\s*(?:[-\u2013]\s*)?(?:\(|\[|\u3010)?([^)\]\u3011:\uff1a]{1,12})(?:\)|\]|\u3011)?\s*[:\uff1a]\s*")
_SOUND_EFFECT = re.compile(r"^\s*[(\[\uff08\u3010][^)\]\uff09\u3011]*[)\]\uff09\u3011]\s*$")
_WHITESPACE = re.compile(r"[\u3000\s]+")


@dataclass(slots=True)
class Cue:
    """One subtitle line, timed in milliseconds."""

    index: int
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass(slots=True)
class ParsedSubtitles:
    cues: list[Cue] = field(default_factory=list)
    dropped: int = 0

    @property
    def duration_ms(self) -> int:
        return self.cues[-1].end_ms if self.cues else 0


def _timestamp_to_ms(raw: str) -> int:
    match = _TIME_SRT.search(raw)
    if not match:
        raise ValueError(f"unrecognised timestamp: {raw!r}")
    ms = match.group("ms").ljust(3, "0")
    return (
        int(match.group("h")) * 3_600_000
        + int(match.group("m")) * 60_000
        + int(match.group("s")) * 1_000
        + int(ms)
    )


def clean_text(raw: str) -> tuple[str, str | None]:
    """Strip markup and pull out a speaker label if the line carries one."""
    text = _ASS_OVERRIDE.sub("", raw)
    text = _HTML_TAG.sub("", text)
    text = text.replace("\\N", " ").replace("\\n", " ")
    text = text.replace("\u200b", "")
    text = _WHITESPACE.sub(" ", text).strip()

    speaker: str | None = None
    speaker_match = _SPEAKER.match(text)
    if speaker_match:
        speaker = speaker_match.group(1).strip()
        text = text[speaker_match.end() :].strip()

    return text, speaker


def is_teachable(text: str) -> bool:
    """Filter out cues that cannot become a lesson line."""
    if not text:
        return False
    if _SOUND_EFFECT.match(text):
        return False
    if text.startswith("♪") or text.startswith("♫"):
        return False
    # Require at least one Japanese character, otherwise it is credits or ASCII.
    return any(
        0x3040 <= ord(ch) <= 0x30FF or 0x4E00 <= ord(ch) <= 0x9FFF for ch in text
    )


def parse(content: str) -> ParsedSubtitles:
    """Parse SRT or WebVTT content into normalised cues."""
    content = content.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    blocks = re.split(r"\n{2,}", content)

    result = ParsedSubtitles()
    index = 0

    for block in blocks:
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].strip().upper().startswith("WEBVTT"):
            lines = lines[1:]
        if not lines:
            continue

        timing_at = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_at is None:
            continue

        try:
            start_raw, end_raw = _ARROW.split(lines[timing_at], maxsplit=1)
            start_ms = _timestamp_to_ms(start_raw)
            end_ms = _timestamp_to_ms(end_raw)
        except ValueError:
            result.dropped += 1
            continue

        body = " ".join(lines[timing_at + 1 :])
        text, speaker = clean_text(body)

        if not is_teachable(text):
            result.dropped += 1
            continue

        index += 1
        result.cues.append(
            Cue(index=index, start_ms=start_ms, end_ms=end_ms, text=text, speaker=speaker)
        )

    return merge_split_sentences(result)


def merge_split_sentences(parsed: ParsedSubtitles, max_gap_ms: int = 400) -> ParsedSubtitles:
    """Join consecutive cues that are clearly one sentence cut in two.

    A cue that ends without sentence-final punctuation and is followed almost
    immediately by another cue from the same speaker is a continuation.
    """
    terminal = "。！？!?」…"
    merged: list[Cue] = []

    for cue in parsed.cues:
        if merged:
            prev = merged[-1]
            gap = cue.start_ms - prev.end_ms
            same_speaker = prev.speaker == cue.speaker or cue.speaker is None
            unfinished = not prev.text.endswith(tuple(terminal))
            short_enough = len(prev.text) + len(cue.text) <= 60
            if gap <= max_gap_ms and same_speaker and unfinished and short_enough:
                prev.text = f"{prev.text}{cue.text}"
                prev.end_ms = cue.end_ms
                continue
        merged.append(cue)

    for position, cue in enumerate(merged, start=1):
        cue.index = position

    return ParsedSubtitles(cues=merged, dropped=parsed.dropped)
