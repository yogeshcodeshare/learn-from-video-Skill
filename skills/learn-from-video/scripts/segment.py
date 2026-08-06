#!/usr/bin/env python3
"""Slice a transcript into fixed time windows and emit a coverage checklist.

THE PROBLEM THIS SOLVES
-----------------------
Given a long transcript, a model will summarise it from memory: it reads the
whole thing, forms an impression, and writes a few hundred words of impression
back out. The result reads fine and is far too thin — a 39-minute class
collapses into two pages of "the instructor explains X".

The fix is mechanical, not motivational. Slice the transcript into windows and
require one written subsection per window. The model then cannot skip content,
because every window is a visible, checkable unit of work.

    python segment.py REPORT.md --window 120 --json > windows.json
    python segment.py REPORT.md --window 120            # human-readable

Each window carries its own verbatim transcript text. Write the document
window by window, with that window's text in front of you — never from a
remembered overview of the whole video.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LINE = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*(.*)$")


def parse_seconds(h: str, m: str, s: str | None) -> int:
    return int(h) * 3600 + int(m) * 60 + int(s) if s else int(h) * 60 + int(m)


def extract_transcript(report_text: str) -> list[tuple[int, str]]:
    """Pull [MM:SS] lines out of a watch engine report."""
    seg: list[tuple[int, str]] = []
    for raw in report_text.splitlines():
        m = LINE.match(raw.strip())
        if not m:
            continue
        secs = parse_seconds(m.group(1), m.group(2), m.group(3))
        text = m.group(4).strip()
        if text:
            seg.append((secs, text))
    return seg


def dedupe(segments: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Caption tracks repeat the previous line as scroll-context. Drop text
    already fully contained in the line before it."""
    out: list[tuple[int, str]] = []
    for secs, text in segments:
        if out:
            prev = out[-1][1]
            if text == prev or text in prev:
                continue
            # strip the leading overlap a rolling caption duplicates
            words, pw = text.split(), prev.split()
            for k in range(min(len(words), len(pw)), 3, -1):
                if pw[-k:] == words[:k]:
                    text = " ".join(words[k:])
                    break
            if not text.strip():
                continue
        out.append((secs, text))
    return out


def fmt(t: int) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_windows(segments: list[tuple[int, str]], window: int) -> list[dict]:
    if not segments:
        return []
    end = segments[-1][0]
    out = []
    for i, start in enumerate(range(0, end + 1, window)):
        stop = start + window
        chunk = [(t, x) for t, x in segments if start <= t < stop]
        if not chunk:
            continue
        text = " ".join(x for _, x in chunk)
        out.append({
            "index": i + 1,
            "start": fmt(start), "end": fmt(min(stop, end)),
            "start_seconds": start, "end_seconds": min(stop, end),
            "segment_count": len(chunk),
            "word_count": len(text.split()),
            "text": text,
            # A teaching document EXPANDS on speech, it does not compress it.
            # Spoken words are lossy: the reader also needs the on-screen state,
            # the exact field names, the why, and the steps the speaker performed
            # silently. 0.9x spoken words is a floor, not a target.
            "min_words_expected": max(120, int(len(text.split()) * 0.9)),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="segment")
    ap.add_argument("report", help="Path to the watch engine report (.md)")
    ap.add_argument("--window", type=int, default=120, help="Window length in seconds (default 120)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-dedupe", action="store_true", help="Keep rolling-caption duplication")
    args = ap.parse_args()

    p = Path(args.report)
    if not p.is_file():
        raise SystemExit(f"ERROR: report not found: {p}")

    segments = extract_transcript(p.read_text(encoding="utf-8", errors="replace"))
    if not segments:
        raise SystemExit("ERROR: no [MM:SS] transcript lines found in that report.")
    if not args.no_dedupe:
        segments = dedupe(segments)

    windows = build_windows(segments, args.window)
    total_words = sum(w["word_count"] for w in windows)
    duration = segments[-1][0]

    summary = {
        "duration_seconds": duration,
        "duration": fmt(duration),
        "window_seconds": args.window,
        "window_count": len(windows),
        "transcript_words": total_words,
        "min_document_words": sum(w["min_words_expected"] for w in windows),
        "windows": windows,
    }

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    print(f"Duration          : {summary['duration']}")
    print(f"Windows           : {len(windows)} x {args.window}s")
    print(f"Transcript words  : {total_words}")
    print(f"MINIMUM doc words : {summary['min_document_words']}  <-- write at least this much")
    print()
    print("COVERAGE CHECKLIST — every window needs its own written subsection:")
    for w in windows:
        print(f"  [ ] {w['index']:>3}. {w['start']:>7} - {w['end']:<7} "
              f"({w['word_count']:>4}w spoken, >= {w['min_words_expected']:>4}w written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
