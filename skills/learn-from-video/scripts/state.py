#!/usr/bin/env python3
"""Durable state for the multi-phase pipeline.

WHY THIS EXISTS
The pipeline runs for a long time across five phases. Without state it is
entirely in-memory: if anything fails at Agent 4 -- an API error, a crash, an
interrupted session -- every earlier phase is lost. The transcript is cached by
ingest.py, but the *analysis* (which timestamps matter, what each frame shows,
the code blocks reconstructed across frames) is not, and that analysis is the
expensive part: it costs image tokens that have already been spent.

This gives each phase a place to record its output, so a resumed run reads
back instead of re-deriving.

    python state.py $WORK init --source VIDEO --title "..."
    python state.py $WORK set transcript --json-file t.json
    python state.py $WORK set frames --json-file manifest.json
    python state.py $WORK done frames
    python state.py $WORK status
    python state.py $WORK get frames

Phases: transcript, windows, frames, code, visuals, document
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PHASES = ["transcript", "windows", "frames", "code", "visuals", "document"]
STATE_FILE = ".lfv-state.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def state_path(work: Path) -> Path:
    return work / STATE_FILE


def load(work: Path) -> dict:
    p = state_path(work)
    if not p.is_file():
        return {"version": 1, "phases": {ph: {"status": "pending"} for ph in PHASES}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        # A corrupt state file must never block a run; start clean but keep the
        # damaged file for inspection.
        p.rename(p.with_suffix(".corrupt"))
        return {"version": 1, "phases": {ph: {"status": "pending"} for ph in PHASES}}


def save(work: Path, data: dict) -> None:
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = state_path(work).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_path(work))          # atomic: never a half-written state


def main() -> int:
    ap = argparse.ArgumentParser(prog="state")
    ap.add_argument("work", help="Working directory for this video")
    sub = ap.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init"); i.add_argument("--source", required=True); i.add_argument("--title", default=None)
    s = sub.add_parser("set"); s.add_argument("phase", choices=PHASES)
    s.add_argument("--json-file"); s.add_argument("--value"); s.add_argument("--status", default="done")
    d = sub.add_parser("done"); d.add_argument("phase", choices=PHASES)
    g = sub.add_parser("get"); g.add_argument("phase", choices=PHASES)
    sub.add_parser("status")
    sub.add_parser("next")
    r = sub.add_parser("reset"); r.add_argument("phase", nargs="?", choices=PHASES)

    args = ap.parse_args()
    work = Path(args.work).expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    data = load(work)

    if args.cmd == "init":
        data.setdefault("phases", {ph: {"status": "pending"} for ph in PHASES})
        data["source"] = args.source
        if args.title:
            data["title"] = args.title
        data["work_dir"] = str(work)
        data.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
        save(work, data)
        print(json.dumps({"ok": True, "work_dir": str(work)}, indent=2))
        return 0

    if args.cmd == "set":
        payload = None
        if args.json_file:
            payload = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        elif args.value is not None:
            try:
                payload = json.loads(args.value)
            except json.JSONDecodeError:
                payload = args.value
        data["phases"][args.phase] = {
            "status": args.status, "data": payload,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        save(work, data)
        print(json.dumps({"ok": True, "phase": args.phase, "status": args.status}, indent=2))
        return 0

    if args.cmd == "done":
        ph = data["phases"].setdefault(args.phase, {})
        ph["status"] = "done"
        ph["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save(work, data)
        print(json.dumps({"ok": True, "phase": args.phase}, indent=2))
        return 0

    if args.cmd == "get":
        ph = data["phases"].get(args.phase, {})
        print(json.dumps(ph.get("data"), indent=2, ensure_ascii=False))
        return 0 if ph.get("status") == "done" else 3

    if args.cmd == "reset":
        if args.phase:
            data["phases"][args.phase] = {"status": "pending"}
        else:
            data["phases"] = {ph: {"status": "pending"} for ph in PHASES}
        save(work, data)
        print(json.dumps({"ok": True, "reset": args.phase or "all"}, indent=2))
        return 0

    if args.cmd == "next":
        nxt = next((ph for ph in PHASES if data["phases"].get(ph, {}).get("status") != "done"), None)
        print(json.dumps({"next_phase": nxt, "complete": nxt is None}, indent=2))
        return 0

    # status
    done = [ph for ph in PHASES if data["phases"].get(ph, {}).get("status") == "done"]
    nxt = next((ph for ph in PHASES if data["phases"].get(ph, {}).get("status") != "done"), None)
    print(json.dumps({
        "work_dir": str(work), "source": data.get("source"), "title": data.get("title"),
        "phases": {ph: data["phases"].get(ph, {}).get("status", "pending") for ph in PHASES},
        "completed": len(done), "total": len(PHASES),
        "next_phase": nxt, "complete": nxt is None,
        "resumable": len(done) > 0 and nxt is not None,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
