#!/usr/bin/env python3
"""Dependency preflight for learn-from-video.

The engine's own setup.py checks ffmpeg/yt-dlp/Whisper. This checks the things
learn-from-video needs *on top* of that — chiefly Node and npm for docx
generation. Run this BEFORE frame extraction, not after: discovering that Node
is missing at the end of an hour-long pipeline wastes the whole run.

    python preflight.py --json
    python preflight.py --check      # exit 0 when able to produce a document

Exit codes:
    0  ready
    2  watch engine missing
    3  node/npm missing (ingestion fine, document generation impossible)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def which(name: str) -> str | None:
    p = shutil.which(name)
    if p:
        return p
    if os.name == "nt":
        for ext in (".cmd", ".exe", ".bat"):
            p = shutil.which(name + ext)
            if p:
                return p
    return None


def version_of(exe: str | None) -> str | None:
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, timeout=20)
        return r.stdout.decode("utf-8", errors="replace").strip().splitlines()[0] if r.stdout else None
    except Exception:
        return None


def find_engine() -> Path | None:
    env = os.environ.get("WATCH_ENGINE")
    cands = ([Path(env)] if env else []) + [
        SCRIPT_DIR / ".." / ".." / "watch" / "scripts" / "watch.py",
        SCRIPT_DIR / ".." / ".." / ".." / "watch" / "scripts" / "watch.py",
    ]
    for c in cands:
        p = c.resolve()
        if p.is_file():
            return p
    return None


def engine_status(engine: Path | None) -> dict:
    """Delegate the ffmpeg/yt-dlp/key question to the engine's own preflight."""
    if not engine:
        return {"available": False}
    setup = engine.parent / "setup.py"
    if not setup.is_file():
        return {"available": True, "setup_json": None}
    try:
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        r = subprocess.run([sys.executable, str(setup), "--json"],
                           capture_output=True, timeout=60, env=env)
        txt = r.stdout.decode("utf-8", errors="replace")
        start = txt.find("{")
        return {"available": True, "setup_json": json.loads(txt[start:]) if start >= 0 else None}
    except Exception:
        return {"available": True, "setup_json": None}


def main() -> int:
    ap = argparse.ArgumentParser(prog="preflight")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true", help="silent; exit code only")
    args = ap.parse_args()

    engine = find_engine()
    eng = engine_status(engine)
    node, npm = which("node"), which("npm")

    missing = []
    if not engine:
        missing.append("watch-engine")
    if not node:
        missing.append("node")
    if not npm:
        missing.append("npm")

    can_ingest = engine is not None
    can_document = bool(node and npm)

    if not can_ingest:
        status, code = "engine_missing", 2
    elif not can_document:
        status, code = "needs_node", 3
    else:
        status, code = "ready", 0

    result = {
        "status": status,
        "can_ingest": can_ingest,
        "can_document": can_document,
        "missing": missing,
        "engine_path": str(engine) if engine else None,
        "node_version": version_of(node),
        "npm_version": version_of(npm),
        "engine_setup": eng.get("setup_json"),
        "platform": sys.platform,
        "python": sys.version.split()[0],
    }

    if args.check:
        return code
    if args.json:
        print(json.dumps(result, indent=2))
        return code

    print(f"status        : {status}")
    print(f"can ingest    : {can_ingest}")
    print(f"can document  : {can_document}")
    if missing:
        print(f"missing       : {', '.join(missing)}")
    if not can_document:
        print()
        print("Node.js + npm are required for .docx generation (the `docx` package).")
        print("Install from https://nodejs.org — then re-run this preflight.")
        print("Ingestion and transcript analysis still work without them.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
