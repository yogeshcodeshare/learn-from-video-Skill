#!/usr/bin/env python3
"""Measure a generated .docx and fail it if it is too thin.

"The document looks professional but the information inside is very less" is
the characteristic failure of this skill: images and headings are present, so
it *looks* complete, while the actual content is a summary of a summary.

Reading it back by eye does not catch this — the document reads fine in
isolation. Only measuring it against the transcript does.

    python verify_docx.py OUT.docx --report REPORT.md --window 120
    python verify_docx.py OUT.docx --min-words 4000 --min-images 10 --json

Exit codes:
    0  passed
    1  file invalid / unreadable
    4  DENSITY FAILURE — regenerate with more content, do not ship
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TAG = re.compile(r"<[^>]+>")
PARA = re.compile(r"<w:p[ >]")
TSTAMP = re.compile(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b")


def docx_text(path: Path) -> tuple[str, dict]:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    body = TAG.sub(" ", xml)
    body = re.sub(r"\s+", " ", body).strip()
    stats = {
        "images": sum(1 for n in names if n.startswith("word/media/")),
        "paragraphs": len(PARA.findall(xml)),
        "has_header": any("header" in n for n in names),
        "has_footer": any("footer" in n for n in names),
        "tables": xml.count("<w:tbl>"),
    }
    return body, stats


def expected_from_report(report: Path, window: int) -> dict | None:
    seg = SCRIPT_DIR / "segment.py"
    if not seg.is_file() or not report.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(seg), str(report), "--window", str(window), "--json"],
            capture_output=True, timeout=120,
        )
        txt = r.stdout.decode("utf-8", errors="replace")
        i = txt.find("{")
        if i < 0:
            return None
        data = json.loads(txt[i:])
        return {
            "duration": data["duration"],
            "duration_seconds": data["duration_seconds"],
            "window_count": data["window_count"],
            "transcript_words": data["transcript_words"],
            "min_document_words": data["min_document_words"],
            "windows": [(w["start"], w["start_seconds"], w["end_seconds"]) for w in data["windows"]],
            "per_window_floor": [w["min_words_expected"] for w in data["windows"]],
        }
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(prog="verify_docx")
    ap.add_argument("docx")
    ap.add_argument("--report", help="watch engine report, to derive expected density")
    ap.add_argument("--window", type=int, default=120)
    ap.add_argument("--min-words", type=int, default=None, help="Override the derived word floor")
    ap.add_argument("--min-images", type=int, default=5)
    ap.add_argument("--min-coverage", type=float, default=90.0,
                    help="Minimum %% of transcript windows that must be properly written up. "
                         "The target is 100%%: every window represented. The 10%% tolerance exists "
                         "only for genuinely empty stretches -- silence, dead air, an unrelated "
                         "aside. It is NOT a licence to skip content that was hard to write up. "
                         "(default 90)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    path = Path(args.docx)
    if not path.is_file():
        print(f"ERROR: not found: {path}", file=sys.stderr)
        return 1
    try:
        body, stats = docx_text(path)
    except Exception as e:
        print(f"ERROR: unreadable docx ({e})", file=sys.stderr)
        return 1

    words = len(body.split())
    expected = expected_from_report(Path(args.report), args.window) if args.report else None
    floor = args.min_words if args.min_words is not None else (
        expected["min_document_words"] if expected else 1500)

    # Coverage. A window is not "covered" merely because its timestamp is
    # mentioned somewhere -- a passing reference would satisfy that and the
    # document could still say nothing about it. Instead, attribute document
    # text to windows: prose following a timestamp belongs to that timestamp's
    # window, up to the next timestamp. A window counts as REPRESENTED only if
    # it received a real share of writing.
    hits = []  # (char_offset, seconds)
    for m in TSTAMP.finditer(body):
        p = m.group(1).split(":")
        try:
            secs = int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2]) if len(p) == 3 else int(p[0]) * 60 + int(p[1])
        except ValueError:
            continue
        hits.append((m.start(), secs))
    found = {s for _, s in hits}

    covered = uncovered = None
    coverage_pct = None
    thin_windows: list[str] = []
    if expected and expected["windows"]:
        # words attributed to each window
        words_for: dict[int, int] = {i: 0 for i in range(len(expected["windows"]))}
        last_end = expected["windows"][-1][2]
        for n, (off, secs) in enumerate(hits):
            # Windows are contiguous: window N ends exactly where N+1 begins.
            # A naive `start <= secs <= end` test therefore matches the EARLIER
            # window for any timestamp sitting on a boundary, so text written
            # about e.g. 38:00 was credited to the 36:00 window and the 38:00
            # window read as empty. Attribute to the LAST window that starts at
            # or before the timestamp instead.
            idx = None
            for i, w in enumerate(expected["windows"]):
                if secs >= w[1]:
                    idx = i
                else:
                    break
            if idx is None or secs > last_end:
                continue                      # timestamp outside the video
            end = hits[n + 1][0] if n + 1 < len(hits) else len(body)
            words_for[idx] += len(body[off:end].split())

        represented = []
        for i, w in enumerate(expected["windows"]):
            need = expected["per_window_floor"][i] if expected.get("per_window_floor") else 120
            # half the per-window floor is the bar for "genuinely written about"
            if words_for[i] >= max(60, need * 0.5):
                represented.append(i)
            else:
                thin_windows.append(f"{w[0]} ({words_for[i]}w written, need >= {int(max(60, need * 0.5))}w)")
        covered = len(represented)
        uncovered = len(expected["windows"]) - covered
        coverage_pct = round(100 * covered / len(expected["windows"]), 1)

    failures = []
    if words < floor:
        failures.append(f"TOO THIN: {words} words, need >= {floor}. "
                        f"The document summarises instead of teaching — regenerate with real content per window.")
    if stats["images"] < args.min_images:
        failures.append(f"TOO FEW IMAGES: {stats['images']}, need >= {args.min_images}")
    if coverage_pct is not None and coverage_pct < args.min_coverage:
        detail = "; ".join(thin_windows[:8]) + (" …" if len(thin_windows) > 8 else "")
        failures.append(
            f"POOR COVERAGE: only {coverage_pct}% of transcript windows are properly represented "
            f"(need >= {args.min_coverage}%). {uncovered} window(s) got little or no writing. "
            f"Write these up properly: {detail}")

    result = {
        "file": str(path),
        "size_mb": round(path.stat().st_size / 1048576, 2),
        "words": words,
        "word_floor": floor,
        "paragraphs": stats["paragraphs"],
        "images": stats["images"],
        "tables": stats["tables"],
        "has_header": stats["has_header"],
        "has_footer": stats["has_footer"],
        "distinct_timestamps": len(found),
        "windows_covered": covered,
        "windows_uncovered": uncovered,
        "coverage_pct": coverage_pct,
        "thin_windows": thin_windows,
        "transcript_words": expected["transcript_words"] if expected else None,
        "passed": not failures,
        "failures": failures,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"file          : {path.name}  ({result['size_mb']} MB)")
        print(f"words         : {words}   (floor {floor})")
        print(f"paragraphs    : {stats['paragraphs']}")
        print(f"images        : {stats['images']}")
        print(f"tables        : {stats['tables']}")
        if expected:
            print(f"transcript    : {expected['transcript_words']} words over {expected['duration']}")
            print(f"coverage      : {coverage_pct}%  ({covered}/{covered + uncovered} windows properly represented)")
            if thin_windows:
                print("thin windows  : " + ", ".join(thin_windows[:6]) + (" ..." if len(thin_windows) > 6 else ""))
        print()
        if failures:
            print("RESULT: FAILED")
            for f in failures:
                print(f"  - {f}")
        else:
            print("RESULT: PASSED")

    return 4 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
