"""Tests for the chunked Whisper wrapper.

What this module exists for: a single large upload to Groq failed 16/16 times
on a 23.34 MiB file, while ~3.4 MB chunks of the same audio succeeded. The
engine only chunks above 24 MiB, so such a file is never chunked.

None of these tests reproduce a Groq failure — that needs the network and a
paid API. They cover the parts that can be asserted offline and that would
silently corrupt a document if wrong: timeline coverage, timestamp stitching,
the report contract both downstream parsers depend on, retry classification,
and resumability after a quota limit.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "learn-from-video" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import chunked_whisper as cw  # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg/ffprobe not installed")


# --------------------------------------------------------------------------
# planning
# --------------------------------------------------------------------------

def test_plan_covers_whole_timeline_without_gaps():
    plan = cw.plan_chunks(3059.0, 450.0)
    assert plan[0][0] == 0.0
    for (offset, duration), (next_offset, _) in zip(plan, plan[1:]):
        assert pytest.approx(offset + duration) == next_offset
    last_offset, last_duration = plan[-1]
    assert pytest.approx(last_offset + last_duration) == 3059.0


def test_plan_of_short_video_is_a_single_chunk():
    assert cw.plan_chunks(120.0, 450.0) == [(0.0, 120.0)]


def test_plan_of_empty_video_is_empty():
    assert cw.plan_chunks(0.0) == []


def test_needs_chunking_matches_the_failing_case():
    # The lesson-8 recording: 51 minutes, 23.34 MiB of audio, failed every time.
    assert cw.needs_chunking(3059.0) is True
    # Lessons 4-7 were all short enough to never reach the broken path.
    assert cw.needs_chunking(1704.0) is False


def test_estimate_matches_observed_extraction():
    # The real file was 24,474,106 bytes for 3059.17s at 64 kbps mono.
    estimate = cw.estimate_audio_bytes(3059.17)
    assert abs(estimate - 24_474_106) / 24_474_106 < 0.02


# --------------------------------------------------------------------------
# the actual bug
# --------------------------------------------------------------------------

@needs_ffmpeg
def test_offset_slice_has_exact_duration(tmp_path: Path):
    """A chunk cut at a non-zero offset decodes to exactly the length asked for.

    NOTE ON SCOPE: this does not reproduce a Groq failure and must not be
    described as doing so. A `-c copy` slice of the same range also decodes
    fine locally (it measures 450.036s against the re-encode's 450.000s on the
    real lesson-8 audio). This asserts the property we actually rely on —
    chunk N's timestamps are offset by exactly N * chunk_seconds, so stitching
    cannot drift. Duration error accumulating across chunks would silently
    misplace every timestamp in the back half of a document.
    """
    source = tmp_path / "tone.mp3"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
         "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1", str(source)],
        check=True, capture_output=True,
    )

    out = tmp_path / "chunk.mp3"
    cw.slice_audio(source, out, offset=30.0, duration=20.0)

    assert out.exists() and out.stat().st_size > 0
    measured = cw.ffprobe_duration(out)
    # Tight bound: re-encoding lands on 20.000s. A tolerance loose enough to
    # accept stream-copy drift would make this assertion meaningless.
    assert measured == pytest.approx(20.0, abs=0.02), (
        f"offset slice decoded to {measured}s, expected 20.000s"
    )


@needs_ffmpeg
def test_slice_audio_rejects_a_bad_range(tmp_path: Path):
    source = tmp_path / "missing.mp3"
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        cw.slice_audio(source, tmp_path / "out.mp3", 0.0, 10.0)


# --------------------------------------------------------------------------
# timestamp stitching
# --------------------------------------------------------------------------

def test_segments_shift_into_absolute_time():
    segments = [{"start": 0.0, "text": "first"}, {"start": 12.5, "text": "second"}]
    assert cw.shift_segments(segments, 450.0) == [(450.0, "first"), (462.5, "second")]


def test_shift_drops_empty_and_malformed_segments():
    segments = [
        {"start": 1.0, "text": "  "},
        {"start": "bad", "text": "x"},
        {"text": "no start"},
        {"start": 2.0, "text": " kept "},
    ]
    assert cw.shift_segments(segments, 0.0) == [(2.0, "kept")]


def test_timestamps_format_with_and_without_hours():
    assert cw.format_timestamp(0) == "00:00"
    assert cw.format_timestamp(90) == "01:30"
    assert cw.format_timestamp(3661) == "01:01:01"


# --------------------------------------------------------------------------
# report contract — both downstream parsers must keep working
# --------------------------------------------------------------------------

def test_report_is_parseable_by_segment_py():
    import segment

    segments = [(0.0, "intro line"), (450.0, "later line"), (3000.0, "closing line")]
    report = cw.render_report("v.mp4", 3059.0, segments)

    parsed = segment.extract_transcript(report)
    assert parsed == [(0, "intro line"), (450, "later line"), (3000, "closing line")]


def test_report_satisfies_has_transcript():
    import ingest

    report = cw.render_report("v.mp4", 100.0, [(0.0, "hello")])
    assert ingest.has_transcript(report) is True


def test_partial_report_is_flagged():
    report = cw.render_report("v.mp4", 3059.0, [(0.0, "only the start")], complete=False)
    assert "PARTIAL" in report


# --------------------------------------------------------------------------
# retry classification
# --------------------------------------------------------------------------

def test_exhausted_engine_failure_is_not_retried():
    """The engine runs its own 4 attempts. Retrying after that repeats a
    settled failure — on lesson 8 it turned 1 error into 16 API calls."""
    import ingest

    stderr = (
        "[watch] whisper HTTP 500 — retrying in 8.0s (attempt 4/4)\n"
        "[watch] whisper fallback failed: Whisper request failed after 4 attempts: "
        'HTTP Error 500: Internal Server Error'
    )
    assert ingest.looks_exhausted(stderr) is True
    assert ingest.looks_transient(stderr) is False


def test_genuine_transient_error_is_still_retried():
    import ingest

    assert ingest.looks_transient("urllib.error.URLError: Connection reset") is True
    assert ingest.looks_transient("HTTP Error 503: Service Unavailable") is True


# --------------------------------------------------------------------------
# flag parsing
# --------------------------------------------------------------------------

@pytest.mark.parametrize("args,expected", [
    (["--detail", "transcript"], "transcript"),
    (["--detail=transcript"], "transcript"),
    (["--detail", "balanced", "--whisper", "groq"], "balanced"),
    (["--whisper", "groq"], None),
    (["--detail"], None),
])
def test_detail_flag_parsing(args, expected):
    import ingest
    assert ingest.detail_of(args) == expected


def test_whisper_backend_parsing():
    import ingest
    assert ingest.whisper_of(["--whisper", "groq"]) == "groq"
    assert ingest.whisper_of(["--whisper=openai"]) == "openai"
    assert ingest.whisper_of([]) is None


# --------------------------------------------------------------------------
# resumability — a quota limit must not cost work already paid for
# --------------------------------------------------------------------------

def test_cached_chunk_is_not_refetched(tmp_path: Path, monkeypatch):
    calls: list[Path] = []

    def fake_post(path, backend, key, log=None):
        calls.append(path)
        return {"segments": [{"start": 0.0, "text": "fresh"}]}

    monkeypatch.setattr(cw, "transcribe_one", fake_post)
    monkeypatch.setattr(cw, "extract_audio", lambda s, o: o.write_bytes(b"x") or o)
    monkeypatch.setattr(cw, "slice_audio",
                        lambda s, o, off, d: o.write_bytes(b"x") or o)
    monkeypatch.setattr(cw, "ffprobe_duration", lambda p: 900.0)

    work = tmp_path / "work"
    work.mkdir()
    (work / "audio.mp3").write_bytes(b"x")
    # Chunk 0 already transcribed on an earlier, interrupted run.
    (work / "chunk_000.json").write_text(
        json.dumps({"segments": [{"start": 0.0, "text": "cached"}]}), encoding="utf-8")

    segments, complete = cw.transcribe(tmp_path / "v.mp4", work, "groq", "k")

    assert complete is True
    assert len(calls) == 1, "cached chunk should not be re-uploaded"
    assert segments[0] == (0.0, "cached")


def test_stitched_timestamps_land_in_the_right_window(tmp_path: Path, monkeypatch):
    """The failure this guards: an off-by-one-chunk offset would put late
    content in early windows, and verify_docx would still report 100%
    coverage while every timestamp in the document was wrong."""
    import segment

    def fake_post(path, backend, key, log=None):
        # Every chunk reports the same 0-based segment; only the offset differs.
        return {"segments": [{"start": 10.0, "text": f"line from {path.stem}"}]}

    monkeypatch.setattr(cw, "transcribe_one", fake_post)
    monkeypatch.setattr(cw, "slice_audio",
                        lambda s, o, off, d: o.write_bytes(b"x") or o)
    monkeypatch.setattr(cw, "ffprobe_duration", lambda p: 1350.0)

    work = tmp_path / "work"
    work.mkdir()
    (work / "audio.mp3").write_bytes(b"x")

    segments, complete = cw.transcribe(tmp_path / "v.mp4", work, "groq", "k")

    assert complete is True
    assert [s for s, _ in segments] == [10.0, 460.0, 910.0]

    report = cw.render_report("v.mp4", 1350.0, segments)
    parsed = segment.extract_transcript(report)
    assert [s for s, _ in parsed] == [10, 460, 910]
    assert "[07:40]" in report and "[15:10]" in report


def test_partial_run_returns_what_it_has(tmp_path: Path, monkeypatch):
    def fail_on_second(path, backend, key, log=None):
        if path.name == "chunk_001.mp3":
            raise RuntimeError("quota")
        return {"segments": [{"start": 0.0, "text": "ok"}]}

    monkeypatch.setattr(cw, "transcribe_one", fail_on_second)
    monkeypatch.setattr(cw, "slice_audio",
                        lambda s, o, off, d: o.write_bytes(b"x") or o)
    monkeypatch.setattr(cw, "ffprobe_duration", lambda p: 1350.0)

    work = tmp_path / "work"
    work.mkdir()
    (work / "audio.mp3").write_bytes(b"x")

    segments, complete = cw.transcribe(tmp_path / "v.mp4", work, "groq", "k")

    assert complete is False
    assert len(segments) == 1, "the first chunk must survive a later failure"
