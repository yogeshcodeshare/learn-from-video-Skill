"""Tests for the learn-from-video scripts.

No network, no ffmpeg, no API keys. Fixtures are synthesised in-process.
"""
from __future__ import annotations

import json
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


def make_docx(path: Path, words: int, images: int = 0, timestamps: list[str] | None = None) -> Path:
    """A minimal but structurally valid .docx."""
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
