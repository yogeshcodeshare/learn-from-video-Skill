#!/usr/bin/env python3
"""Robust ingestion wrapper around the sibling `watch` engine.

Why this exists — three failures observed in real runs that the engine alone
does not survive:

1. **Encoding.** On Windows, stdout defaults to a legacy codepage (cp1252).
   A transcript containing Devanagari, CJK, Cyrillic or emoji crashes the
   engine with UnicodeEncodeError *after* the Whisper API call has been paid
   for and completed. The transcript is produced, then destroyed.

2. **No transcript cache.** The engine caches the extracted `audio.mp3` but
   not the transcript. Any crash, any transient API error, means re-uploading
   the audio and paying again. Over a multi-video course that is real money
   and real time.

3. **Transient API errors.** Groq/OpenAI return HTTP 5xx under load. A single
   500 aborts an otherwise-complete pipeline run.

This wrapper fixes all three without modifying the vendored engine, which is
kept byte-identical to bradautomates/claude-video upstream.

Usage:
    python ingest.py <SOURCE> --work DIR [engine flags...] [--json]

Every unrecognised flag is passed straight through to watch.py, so this stays
compatible as the engine gains options.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
CACHE_VERSION = 1

# Force UTF-8 on our own streams so we can print anything the engine returns.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def find_engine() -> Path:
    """Locate watch.py. The engine is a sibling skill directory."""
    candidates = [
        SCRIPT_DIR / ".." / ".." / "watch" / "scripts" / "watch.py",
        SCRIPT_DIR / ".." / ".." / ".." / "watch" / "scripts" / "watch.py",
    ]
    env = os.environ.get("WATCH_ENGINE")
    if env:
        candidates.insert(0, Path(env))
    for c in candidates:
        p = c.resolve()
        if p.is_file():
            return p
    raise SystemExit(
        "ERROR: watch engine not found. Expected at <skills>/watch/scripts/watch.py.\n"
        "learn-from-video requires the sibling 'watch' skill from the same plugin.\n"
        "Set WATCH_ENGINE=/path/to/watch.py to override."
    )


def source_fingerprint(source: str) -> str:
    """Identify the source. Local files use size+mtime; URLs use the string."""
    p = Path(source)
    if p.is_file():
        st = p.stat()
        return f"file:{p.resolve()}:{st.st_size}:{int(st.st_mtime)}"
    return f"url:{source}"


def cache_key(source: str, passthrough: list[str]) -> str:
    """A run is cacheable per (source, engine flags). --out-dir is excluded so
    the same logical run reuses its cache regardless of working directory."""
    filtered, skip = [], False
    for a in passthrough:
        if skip:
            skip = False
            continue
        if a in ("--out-dir",):
            skip = True
            continue
        if a.startswith("--out-dir="):
            continue
        filtered.append(a)
    raw = f"v{CACHE_VERSION}|{source_fingerprint(source)}|{'|'.join(sorted(filtered))}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


TRANSIENT_MARKERS = (
    "HTTP Error 5",
    "internal_server_error",
    "Internal Server Error",
    "502",
    "503",
    "504",
    "Connection reset",
    "timed out",
    "Temporary failure",
)


def looks_transient(stderr: str) -> bool:
    return any(m in stderr for m in TRANSIENT_MARKERS)


def has_transcript(report: str) -> bool:
    import re
    return bool(re.search(r"\*\*Transcript:\*\*\s+\d+\s+segments", report))


def wants_transcript(passthrough: list[str]) -> bool:
    return "--no-whisper" not in passthrough


def run_engine(engine: Path, source: str, passthrough: list[str]) -> tuple[int, str, str]:
    env = dict(os.environ)
    # The core fix: the engine inherits a UTF-8 stdout instead of the legacy
    # Windows codepage, so non-Latin transcripts cannot crash it.
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, str(engine), source, *passthrough],
        capture_output=True, env=env,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return proc.returncode, out, err


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="ingest",
        description="Cached, retrying, encoding-safe wrapper around the watch engine.",
    )
    ap.add_argument("source", help="Video URL or local file path")
    ap.add_argument("--work", required=True, help="Stable working directory for this video")
    ap.add_argument("--retries", type=int, default=3, help="Retry attempts on transient API errors (default 3)")
    ap.add_argument("--retry-wait", type=float, default=5.0, help="Initial backoff seconds (doubles each retry)")
    ap.add_argument("--no-cache", action="store_true", help="Ignore any cached report and re-run")
    ap.add_argument("--json", action="store_true", help="Emit a JSON status object instead of the raw report")
    args, passthrough = ap.parse_known_args()

    engine = find_engine()
    work = Path(args.work).expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    cache_dir = work / ".lfv-cache"
    cache_dir.mkdir(exist_ok=True)

    # The engine writes its artefacts into --out-dir; keep that as `work`
    # unless the caller explicitly overrode it.
    if not any(a == "--out-dir" or a.startswith("--out-dir=") for a in passthrough):
        passthrough += ["--out-dir", str(work)]

    key = cache_key(args.source, passthrough)
    report_path = cache_dir / f"report-{key}.md"
    meta_path = cache_dir / f"meta-{key}.json"

    # ---- cache hit -------------------------------------------------------
    if report_path.is_file() and not args.no_cache:
        report = report_path.read_text(encoding="utf-8")
        meta = {}
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        result = {
            "status": "ok", "cache_hit": True, "attempts": 0,
            "has_transcript": has_transcript(report),
            "report_path": str(report_path), "work_dir": str(work),
            "cached_at": meta.get("cached_at"),
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(report)
        print(f"[ingest] cache hit ({report_path.name}) — engine not re-run", file=sys.stderr)
        return 0

    # ---- run, with retries ----------------------------------------------
    wait = args.retry_wait
    last_err = ""
    attempts = 0
    for attempt in range(1, max(1, args.retries) + 1):
        attempts = attempt
        code, out, err = run_engine(engine, args.source, passthrough)
        last_err = err
        transcript_ok = has_transcript(out)

        if code == 0 and (transcript_ok or not wants_transcript(passthrough)):
            report_path.write_text(out, encoding="utf-8")
            meta_path.write_text(json.dumps({
                "cached_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "source": args.source, "flags": passthrough,
                "has_transcript": transcript_ok, "attempts": attempt,
            }, indent=2), encoding="utf-8")
            result = {
                "status": "ok", "cache_hit": False, "attempts": attempt,
                "has_transcript": transcript_ok,
                "report_path": str(report_path), "work_dir": str(work),
            }
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(out)
            return 0

        retryable = looks_transient(err) or (wants_transcript(passthrough) and not transcript_ok and code == 0)
        if attempt < args.retries and retryable:
            print(f"[ingest] attempt {attempt}/{args.retries} did not yield a transcript "
                  f"({'transient API error' if looks_transient(err) else 'no transcript returned'}) "
                  f"— retrying in {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
            wait *= 2
            continue
        break

    # ---- give up, but preserve whatever we got ---------------------------
    partial = report_path.with_name(f"partial-{key}.md")
    if last_err:
        (cache_dir / f"stderr-{key}.log").write_text(last_err, encoding="utf-8")
    result = {
        "status": "failed", "cache_hit": False, "attempts": attempts,
        "has_transcript": False, "work_dir": str(work),
        "stderr_tail": last_err.strip().splitlines()[-4:] if last_err else [],
        "hint": "Audio is already extracted in the work dir; re-running only repeats the API call, not the extraction.",
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("INGEST FAILED after "
              f"{attempts} attempt(s). See {cache_dir / f'stderr-{key}.log'}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
