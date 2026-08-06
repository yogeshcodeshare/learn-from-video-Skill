"""Tests for the learn-from-video scripts.

No network, no ffmpeg, no API keys. Fixtures are synthesised in-process.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "skills" / "learn-from-video" / "scripts"


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, timeout=120,
        env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
             "PATH": __import__("os").environ.get("PATH", ""),
             "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
    )


def out(p: subprocess.CompletedProcess) -> str:
    return p.stdout.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- fixtures

def make_report(path: Path, minutes: int = 10, hindi: bool = False) -> Path:
    """A synthetic watch-engine report with one transcript line per 3 seconds."""
    lines = [
        "", "# watch: video report", "",
        "- **Source:** test.mp4",
        f"- **Duration:** {minutes}:00 ({minutes * 60}.0s)",
        f"- **Transcript:** {minutes * 20} segments (via whisper (groq))",
        "", "## Transcript", "", "_Source: whisper (groq)._", "", "```",
    ]
    # Each line must be distinct: identical consecutive lines are exactly what
    # the rolling-caption dedupe is designed to collapse.
    body = "यह हिंदी वाक्य संख्या {n} है जो टेस्ट के लिए बनाया गया" if hindi else \
           "spoken sentence number {n} used for testing the segmentation logic"
    for i, s in enumerate(range(0, minutes * 60, 3)):
        lines.append(f"[{s // 60:02d}:{s % 60:02d}] {body.format(n=i)}")
    lines += ["```", "", "---", "_Work dir: `/tmp/x` — delete when done._"]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def make_docx(path: Path, words: int, images: int = 0, timestamps: list[str] | None = None,
              stuff: bool = False) -> Path:
    """A minimal but structurally valid .docx.

    When `timestamps` are given the words are distributed AFTER each timestamp,
    which is what a real document looks like. `stuff=True` instead crams the
    timestamps together with no prose -- the loophole the coverage metric must
    reject.
    """
    if timestamps and not stuff:
        per = max(1, words // len(timestamps))
        parts = []
        for n, ts in enumerate(timestamps):
            parts.append(ts)
            parts.extend(f"w{n}x{i}" for i in range(per))
        text = " ".join(parts)
    else:
        text = " ".join(f"word{i}" for i in range(words))
        if timestamps:
            text += " " + " ".join(timestamps)
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", doc)
        for i in range(images):
            z.writestr(f"word/media/image{i}.jpg", b"\xff\xd8\xff\xe0fake")
    return path


# ---------------------------------------------------------------- segment.py

def test_segment_builds_windows(tmp_path):
    r = make_report(tmp_path / "r.md", minutes=10)
    p = run("segment.py", str(r), "--window", "120", "--json")
    assert p.returncode == 0, p.stderr.decode()
    data = json.loads(out(p))
    assert data["window_count"] == 5          # 10 minutes / 2-minute windows
    assert data["duration_seconds"] >= 570
    assert data["transcript_words"] > 0


def test_segment_windows_are_contiguous_and_carry_text(tmp_path):
    r = make_report(tmp_path / "r.md", minutes=6)
    data = json.loads(out(run("segment.py", str(r), "--window", "120", "--json")))
    prev_end = 0
    for w in data["windows"]:
        assert w["start_seconds"] == prev_end
        assert w["text"].strip(), "window must carry its verbatim text"
        assert w["word_count"] > 0
        prev_end = w["start_seconds"] + 120


def test_segment_word_floor_expands_not_compresses(tmp_path):
    """A teaching document must not be allowed to be shorter than the speech."""
    r = make_report(tmp_path / "r.md", minutes=8)
    data = json.loads(out(run("segment.py", str(r), "--window", "120", "--json")))
    for w in data["windows"]:
        assert w["min_words_expected"] >= 120
    assert data["min_document_words"] >= 0.8 * data["transcript_words"]


def test_segment_handles_devanagari(tmp_path):
    """The Windows encoding crash that destroyed a paid transcript."""
    r = make_report(tmp_path / "r.md", minutes=4, hindi=True)
    p = run("segment.py", str(r), "--window", "120", "--json")
    assert p.returncode == 0, p.stderr.decode()
    assert json.loads(out(p))["window_count"] == 2


def test_segment_dedupes_rolling_captions(tmp_path):
    r = tmp_path / "r.md"
    r.write_text("\n".join([
        "## Transcript", "```",
        "[00:00] hello there this is the first line",
        "[00:03] hello there this is the first line",          # exact repeat
        "[00:06] hello there this is the first line and more",  # rolling overlap
        "```",
    ]), encoding="utf-8")
    data = json.loads(out(run("segment.py", str(r), "--window", "120", "--json")))
    assert data["windows"][0]["text"].count("hello there this is the first line") == 1


def test_segment_rejects_report_without_transcript(tmp_path):
    r = tmp_path / "r.md"
    r.write_text("# watch: video report\n\n_No frames extracted._\n", encoding="utf-8")
    assert run("segment.py", str(r)).returncode != 0


# ------------------------------------------------------------ verify_docx.py

def test_verify_passes_a_dense_document(tmp_path):
    d = make_docx(tmp_path / "ok.docx", words=5000, images=12)
    p = run("verify_docx.py", str(d), "--min-words", "2000", "--min-images", "5", "--json")
    assert p.returncode == 0
    assert json.loads(out(p))["passed"] is True


def test_verify_fails_a_thin_document(tmp_path):
    """The exact defect: looks finished, contains nothing."""
    d = make_docx(tmp_path / "thin.docx", words=200, images=20)
    p = run("verify_docx.py", str(d), "--min-words", "3000", "--json")
    assert p.returncode == 4
    r = json.loads(out(p))
    assert r["passed"] is False
    assert any("TOO THIN" in f for f in r["failures"])


def test_verify_fails_on_too_few_images(tmp_path):
    d = make_docx(tmp_path / "noimg.docx", words=5000, images=1)
    p = run("verify_docx.py", str(d), "--min-words", "100", "--min-images", "10", "--json")
    assert p.returncode == 4
    assert any("TOO FEW IMAGES" in f for f in json.loads(out(p))["failures"])


def test_verify_detects_uncovered_windows(tmp_path):
    """A document that discusses only the first minutes of a long video."""
    r = make_report(tmp_path / "r.md", minutes=20)          # 10 windows
    d = make_docx(tmp_path / "part.docx", words=9000, images=10,
                  timestamps=["0:30", "1:15"])              # only window 1
    p = run("verify_docx.py", str(d), "--report", str(r), "--window", "120", "--json")
    res = json.loads(out(p))
    assert res["windows_uncovered"] >= 8
    assert res["coverage_pct"] < 80
    assert p.returncode == 4


def test_verify_coverage_passes_when_spread(tmp_path):
    r = make_report(tmp_path / "r.md", minutes=10)           # 5 windows
    stamps = ["0:30", "2:30", "4:30", "6:30", "8:30"]
    d = make_docx(tmp_path / "full.docx", words=12000, images=10, timestamps=stamps)
    p = run("verify_docx.py", str(d), "--report", str(r), "--window", "120", "--json")
    res = json.loads(out(p))
    assert res["coverage_pct"] == 100.0
    assert p.returncode == 0


def test_verify_rejects_timestamp_stuffing(tmp_path):
    """A document may not pass by NAMING every window while writing nothing.

    This is the loophole a mention-based coverage metric leaves open: sprinkle
    timestamps through a thin document and coverage reads 100%.
    """
    r = make_report(tmp_path / "r.md", minutes=20)              # 10 windows
    stamps = [f"{m}:30" for m in range(0, 20, 2)]               # every window named
    d = tmp_path / "stuffed.docx"
    # all timestamps crammed together, no prose attributed to any of them
    make_docx(d, words=30, images=10, timestamps=stamps, stuff=True)
    p = run("verify_docx.py", str(d), "--report", str(r), "--window", "120", "--json")
    res = json.loads(out(p))
    assert res["coverage_pct"] < 80, "naming a window must not count as covering it"
    assert res["thin_windows"], "the thin windows must be named so they can be fixed"
    assert p.returncode == 4


def test_verify_reports_which_windows_are_thin(tmp_path):
    r = make_report(tmp_path / "r.md", minutes=10)
    d = make_docx(tmp_path / "x.docx", words=100, images=10, timestamps=["0:30"])
    res = json.loads(out(run("verify_docx.py", str(d), "--report", str(r),
                             "--window", "120", "--json")))
    assert len(res["thin_windows"]) >= 4
    assert all("w written" in t for t in res["thin_windows"])


def test_verify_min_coverage_is_configurable(tmp_path):
    r = make_report(tmp_path / "r.md", minutes=10)
    d = make_docx(tmp_path / "x.docx", words=100, images=10, timestamps=["0:30"])
    strict = run("verify_docx.py", str(d), "--report", str(r), "--min-coverage", "80", "--json")
    loose = run("verify_docx.py", str(d), "--report", str(r), "--min-coverage", "0",
                "--min-words", "10", "--json")
    assert strict.returncode == 4
    assert json.loads(out(loose))["passed"] is True


def test_verify_rejects_missing_and_corrupt_files(tmp_path):
    assert run("verify_docx.py", str(tmp_path / "nope.docx")).returncode == 1
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"this is not a zip archive")
    assert run("verify_docx.py", str(bad)).returncode == 1


# -------------------------------------------------------------- preflight.py

def test_preflight_emits_valid_json():
    p = run("preflight.py", "--json")
    data = json.loads(out(p))
    for k in ("status", "can_ingest", "can_document", "missing", "platform", "python"):
        assert k in data
    assert data["status"] in ("ready", "needs_node", "engine_missing")


def test_preflight_finds_the_sibling_engine():
    """learn-from-video is useless if it cannot locate watch/scripts/watch.py."""
    data = json.loads(out(run("preflight.py", "--json")))
    assert data["can_ingest"] is True
    assert data["engine_path"] and data["engine_path"].endswith("watch.py")


def test_preflight_check_is_silent():
    p = run("preflight.py", "--check")
    assert out(p).strip() == ""


# ----------------------------------------------------------------- ingest.py

@pytest.fixture
def ingest_mod():
    sys.path.insert(0, str(SCRIPTS))
    import importlib
    m = importlib.import_module("ingest")
    yield m
    sys.path.remove(str(SCRIPTS))


def test_ingest_cache_key_ignores_out_dir(ingest_mod, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x" * 100)
    a = ingest_mod.cache_key(str(f), ["--detail", "transcript", "--out-dir", "/tmp/a"])
    b = ingest_mod.cache_key(str(f), ["--detail", "transcript", "--out-dir", "/tmp/b"])
    assert a == b, "same logical run must share a cache entry"


def test_ingest_cache_key_changes_with_flags(ingest_mod, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x" * 100)
    a = ingest_mod.cache_key(str(f), ["--detail", "transcript"])
    b = ingest_mod.cache_key(str(f), ["--detail", "balanced"])
    assert a != b


def test_ingest_cache_key_changes_when_file_changes(ingest_mod, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x" * 100)
    a = ingest_mod.cache_key(str(f), ["--detail", "transcript"])
    f.write_bytes(b"y" * 500)
    assert a != ingest_mod.cache_key(str(f), ["--detail", "transcript"])


def test_ingest_recognises_transient_errors(ingest_mod):
    """The Groq 500 that aborted a real run."""
    assert ingest_mod.looks_transient('HTTP Error 500: Internal Server Error')
    assert ingest_mod.looks_transient('{"type":"internal_server_error"}')
    assert ingest_mod.looks_transient("Connection reset by peer")
    assert not ingest_mod.looks_transient("HTTP Error 401: Unauthorized")
    assert not ingest_mod.looks_transient("no such file")


def test_ingest_detects_transcript_presence(ingest_mod):
    assert ingest_mod.has_transcript("- **Transcript:** 403 segments (via whisper (groq))")
    assert not ingest_mod.has_transcript("- **Transcript:** none available")


def test_ingest_finds_engine(ingest_mod):
    assert ingest_mod.find_engine().is_file()


# ------------------------------------------------------------------ state.py

def test_state_init_and_status(tmp_path):
    w = str(tmp_path / "work")
    assert run("state.py", w, "init", "--source", "v.mp4", "--title", "T").returncode == 0
    s = json.loads(out(run("state.py", w, "status")))
    assert s["source"] == "v.mp4" and s["title"] == "T"
    assert s["completed"] == 0 and s["complete"] is False
    assert s["next_phase"] == "transcript"


def test_state_round_trips_phase_data(tmp_path):
    """The point of state: expensive analysis survives a crash."""
    w = str(tmp_path / "work")
    run("state.py", w, "init", "--source", "v.mp4")
    payload = tmp_path / "frames.json"
    payload.write_text(json.dumps({"frames": [{"path": "a.jpg", "t": "1:00"}]}), encoding="utf-8")
    assert run("state.py", w, "set", "frames", "--json-file", str(payload)).returncode == 0
    got = json.loads(out(run("state.py", w, "get", "frames")))
    assert got["frames"][0]["path"] == "a.jpg"


def test_state_get_pending_phase_signals_not_done(tmp_path):
    w = str(tmp_path / "work")
    run("state.py", w, "init", "--source", "v.mp4")
    assert run("state.py", w, "get", "code").returncode == 3


def test_state_next_advances_and_completes(tmp_path):
    w = str(tmp_path / "work")
    run("state.py", w, "init", "--source", "v.mp4")
    for ph in ["transcript", "windows", "frames", "code", "visuals", "document"]:
        assert json.loads(out(run("state.py", w, "next")))["next_phase"] == ph
        run("state.py", w, "done", ph)
    n = json.loads(out(run("state.py", w, "next")))
    assert n["complete"] is True and n["next_phase"] is None


def test_state_survives_a_corrupt_file(tmp_path):
    """A broken state file must never block a run."""
    w = tmp_path / "work"
    w.mkdir()
    (w / ".lfv-state.json").write_text("{ not json", encoding="utf-8")
    p = run("state.py", str(w), "status")
    assert p.returncode == 0
    assert (w / ".lfv-state.corrupt").exists()


def test_state_reset_single_phase(tmp_path):
    w = str(tmp_path / "work")
    run("state.py", w, "init", "--source", "v.mp4")
    run("state.py", w, "done", "transcript")
    run("state.py", w, "done", "frames")
    run("state.py", w, "reset", "frames")
    s = json.loads(out(run("state.py", w, "status")))
    assert s["phases"]["transcript"] == "done"
    assert s["phases"]["frames"] == "pending"


# -------------------------------------------------------------- build_docx.js

def _node_docx_available() -> bool:
    import shutil
    if not (shutil.which("node") or shutil.which("node.exe")):
        return False
    root = Path(__file__).parent.parent
    return (root / "node_modules" / "docx").is_dir()


needs_docx = pytest.mark.skipif(not _node_docx_available(),
                                reason="node + docx not installed (npm install docx)")


@needs_docx
def test_build_docx_renders_every_block_type(tmp_path):
    import shutil
    root = Path(__file__).parent.parent
    img = tmp_path / "shot.jpg"
    img.write_bytes(bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9"))
    spec = {
        "output": str(tmp_path / "out.docx"),
        "title": "T", "subtitle": "S", "meta": [["K", "V"]],
        "toc": [["1", "One", 3]],
        "sections": [{"heading": "1. One", "blocks": [
            {"type": "h2", "text": "h2"}, {"type": "h3", "text": "h3"},
            {"type": "p", "text": "para"},
            {"type": "ts", "time": "1:00", "text": "timestamped"},
            {"type": "bullets", "items": ["a", "b"]},
            {"type": "image", "path": str(img), "caption": "cap"},
            {"type": "table", "headers": ["A"], "rows": [["1"]], "widths": [4000]},
            {"type": "callout", "style": "warn", "title": "W", "body": ["x"]},
            {"type": "code", "language": "js", "text": "const a=1;"},
            {"type": "mermaid", "text": "graph LR\n A-->B"},
            {"type": "spacer"}, {"type": "pagebreak"},
        ]}],
    }
    sp = tmp_path / "spec.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    node = shutil.which("node") or shutil.which("node.exe")
    r = subprocess.run([node, str(root / "skills" / "learn-from-video" / "scripts" / "build_docx.js"), str(sp)],
                       capture_output=True, cwd=str(root), timeout=180)
    assert r.returncode == 0, r.stderr.decode()
    res = json.loads(r.stdout.decode("utf-8", errors="replace"))
    assert res["ok"] is True and res["images"] == 1
    assert res["warnings"] == []
    with zipfile.ZipFile(spec["output"]) as z:
        assert any(n.startswith("word/media/") for n in z.namelist())


@needs_docx
def test_build_docx_warns_on_missing_image_but_still_renders(tmp_path):
    import shutil
    root = Path(__file__).parent.parent
    spec = {"output": str(tmp_path / "o.docx"), "title": "T",
            "sections": [{"heading": "S", "blocks": [{"type": "image", "path": str(tmp_path / "nope.jpg")}]}]}
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    node = shutil.which("node") or shutil.which("node.exe")
    r = subprocess.run([node, str(root / "skills" / "learn-from-video" / "scripts" / "build_docx.js"), str(sp)],
                       capture_output=True, cwd=str(root), timeout=180)
    assert r.returncode == 0
    res = json.loads(r.stdout.decode("utf-8", errors="replace"))
    assert any("missing image" in w for w in res["warnings"])
    assert Path(spec["output"]).is_file()


@needs_docx
def test_build_docx_clamps_oversized_tables(tmp_path):
    """Column widths wider than the page must be scaled, not allowed to overflow."""
    import shutil
    root = Path(__file__).parent.parent
    spec = {"output": str(tmp_path / "o.docx"), "title": "T",
            "sections": [{"heading": "S", "blocks": [
                {"type": "table", "headers": ["A", "B"], "rows": [["1", "2"]], "widths": [20000, 20000]}]}]}
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    node = shutil.which("node") or shutil.which("node.exe")
    r = subprocess.run([node, str(root / "skills" / "learn-from-video" / "scripts" / "build_docx.js"), str(sp)],
                       capture_output=True, cwd=str(root), timeout=180)
    assert r.returncode == 0
    with zipfile.ZipFile(spec["output"]) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    # Only the table's own grid columns — page width lives in sectPr and is
    # legitimately larger.
    cols = [int(m) for m in re.findall(r'<w:gridCol\s+w:w="(\d+)"', xml)]
    assert cols, "table grid columns not found"
    assert sum(cols) <= 9360, f"table overflows the page: {cols}"


def test_verify_attributes_boundary_timestamps_to_the_right_window(tmp_path):
    """Windows are contiguous, so a timestamp on a boundary belongs to the
    window it STARTS, not the one it ends. Getting this wrong credited text to
    the previous window and made the final window read as empty."""
    r = make_report(tmp_path / "r.md", minutes=6)          # windows at 0:00, 2:00, 4:00
    d = make_docx(tmp_path / "b.docx", words=900, images=6,
                  timestamps=["0:00", "2:00", "4:00"])     # every one on a boundary
    res = json.loads(out(run("verify_docx.py", str(d), "--report", str(r),
                             "--window", "120", "--json")))
    assert res["coverage_pct"] == 100.0, f"boundary timestamps mis-attributed: {res['thin_windows']}"
    assert res["windows_uncovered"] == 0
