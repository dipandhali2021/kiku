"""Command-line entry point for the lesson pipeline.

The whole teaching engine runs without the web layer, a database, or a network
connection. That makes it possible to judge lesson quality on real subtitle
files before any UI exists, which is the fastest way to find out whether the
product idea works.

    python -m app.cli sample/cafe.srt
    python -m app.cli sample/cafe.srt --json
    python -m app.cli sample/cafe.srt --known 私,今日
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.lessons.builder import Lesson, LessonBuilder

_BOLD = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"


def render(lesson: Lesson, *, color: bool = True) -> str:
    def paint(text: str, code: str) -> str:
        return f"{code}{text}{_RESET}" if color else text

    out: list[str] = []
    out.append(paint(f"▶ {lesson.title}", _BOLD))
    out.append(
        paint(
            f"  {lesson.line_count} lines · {lesson.duration_ms / 1000:.1f}s · "
            f"level {lesson.difficulty} · {lesson.comprehension_estimate}% known · "
            f"{lesson.new_words} new words · engine: {lesson.engine}",
            _DIM,
        )
    )
    if lesson.dropped_cues:
        out.append(paint(f"  {lesson.dropped_cues} non-teachable cues skipped", _DIM))
    out.append("")

    for line in lesson.lines:
        stamp = f"{line.start_ms / 1000:6.1f}s"
        who = f"{line.speaker}: " if line.speaker else ""
        out.append(f"{paint(stamp, _DIM)}  {paint(who + line.japanese, _BOLD)}")
        out.append(f"         {paint(line.romaji, _CYAN)}")
        if line.english:
            out.append(f"         {line.english}")
        if line.register:
            out.append(f"         {paint('register: ' + line.register, _DIM)}")
        if line.nuance:
            out.append(f"         {paint('→ ' + line.nuance, _YELLOW)}")

        chips = [w for w in line.words if w.teachable]
        for chip in chips:
            mark = paint("✓", _GREEN) if chip.known else " "
            meaning = chip.meaning or paint("(not in dictionary)", _DIM)
            level = f" [{chip.jlpt}]" if chip.jlpt else ""
            out.append(f"           {mark} {chip.surface} · {chip.romaji} · {meaning}{level}")
            if chip.note:
                out.append(f"             {paint(chip.note, _DIM)}")
        out.append("")

    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kiku", description="Build a Kiku lesson from subtitles.")
    parser.add_argument("subtitle", type=Path, help="path to an .srt or .vtt file")
    parser.add_argument("--json", action="store_true", help="emit lesson JSON")
    parser.add_argument("--known", default="", help="comma-separated words already known")
    parser.add_argument("--max-lines", type=int, default=None)
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args(argv)

    if not args.subtitle.exists():
        print(f"error: {args.subtitle} not found", file=sys.stderr)
        return 1

    content = args.subtitle.read_text(encoding="utf-8", errors="replace")
    known = {w.strip() for w in args.known.split(",") if w.strip()}

    lesson = LessonBuilder().build(
        content,
        title=args.subtitle.stem.replace("_", " ").title(),
        known_words=known,
        max_lines=args.max_lines,
    )

    if args.json:
        print(json.dumps(lesson.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render(lesson, color=not args.no_color))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
