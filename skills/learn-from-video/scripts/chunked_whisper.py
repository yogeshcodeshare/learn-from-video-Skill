#!/usr/bin/env python3
"""Chunked Whisper transcription for long videos.

WHY THIS EXISTS
---------------
Observed on an 8th lesson recording (51:00, 23.34 MiB of extracted audio):

  * Uploading the whole file to Groq failed with HTTP 500 on 16 consecutive
    attempts, across four separate runs and ~25 minutes.
  * Splitting the same audio into ~3.4 MB chunks succeeded: 6 of 7 chunks
    transcribed, the 7th blocked only by an hourly quota limit.

So a single large upload is unreliable well below the engine's 24 MiB
threshold, while small chunks work. The engine only chunks above 24 MiB
(skills/watch/scripts/whisper.py), so a file like this one is never chunked and
fails every time.

WHAT IS *NOT* ESTABLISHED
-------------------------
An earlier version of this file claimed the engine's `-c copy` slicing was the
root cause — that a stream-copy slice at a non-zero offset starts mid-frame and
Groq rejects it. That claim was based on one A/B (a copy slice 500'd, the same
range re-encoded returned 200) and it does not hold up:

  * The two files are indistinguishable locally — same codec, sample rate,
    channels, bitrate and duration to within 36 ms, both decode without error.
  * Re-encoded chunks ALSO returned 500 intermittently (chunks 4 and 6 of 7),
    then succeeded on retry.

The honest reading is that Groq returns intermittent 500s and that retrying
fixes them; the single A/B was coincidence. This module still re-encodes rather
than stream-copies, but as a cheap belt-and-braces measure that also yields
exact chunk durations — NOT as a proven fix. Do not cite it as one.

`skills/watch/` is pinned byte-identical to upstream by a CI parity check, so
this lives in the wrapper rather than the vendored tree.

Also handled, because each cost real quota to discover:
  * Groq's edge rejects urllib's default User-Agent with HTTP 403.
  * HTTP 429 is a quota window, not a fault — wait it out instead of
    burning retry attempts.
  * Every chunk response is cached to disk the moment it arrives, so a run
    interrupted by a quota limit resumes instead of re-paying for prior chunks.
    (The run that discovered this threw away 6 good chunks — ~2,700 s of
    quota — because a late failure raised before anything was written.)
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"
OPENAI_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_MODEL = "whisper-1"

# The engine uses 24 MiB. Groq fails well below that in practice, so aim far
# lower — chunks are cheap, a failed 20-minute upload is not.
SAFE_UPLOAD_BYTES = 16 * 1024 * 1024

# Default slice length. At the engine's 64 kbps mono this is ~3.4 MB.
DEFAULT_CHUNK_SECONDS = 450.0

# urllib's default UA ("Python-urllib/3.x") is rejected by Groq's edge with 403.
USER_AGENT = "learn-from-video/1.0"

MAX_ATTEMPTS = 8
QUOTA_WAIT_SECONDS = 180.0


def ffprobe_duration(path: Path) -> float:
    """Duration in seconds, or 0.0 if ffprobe cannot determine it."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, OSError):
        return 0.0


def estimate_audio_bytes(duration_seconds: float, bitrate_kbps: int = 64) -> int:
    """Bytes the engine's 64 kbps mono extraction would produce."""
    return int(duration_seconds * (bitrate_kbps * 1000 / 8))


def needs_chunking(duration_seconds: float, limit: int = SAFE_UPLOAD_BYTES) -> bool:
    """True when a single upload would land in the range that fails."""
    return estimate_audio_bytes(duration_seconds) > limit


def plan_chunks(
    total_seconds: float,
    chunk_seconds: float = DEFAULT_CHUNK_SECONDS,
) -> list[tuple[float, float]]:
    """Contiguous (offset, duration) pairs covering the whole timeline."""
    if total_seconds <= 0:
        return []
    n = max(1, math.ceil(total_seconds / chunk_seconds))
    plan: list[tuple[float, float]] = []
    for i in range(n):
        offset = i * chunk_seconds
        duration = min(chunk_seconds, total_seconds - offset)
        if duration <= 0:
            break
        plan.append((round(offset, 3), round(duration, 3)))
    return plan


def slice_audio(source: Path, out_path: Path, offset: float, duration: float) -> Path:
    """Cut one chunk, re-encoding rather than stream-copying.

    Re-encoding yields an exact duration and a self-contained file for a few
    seconds of CPU. It is NOT a proven fix for Groq's 500s — see the module
    docstring; copy-sliced and re-encoded chunks are locally indistinguishable
    and both have been observed to 500. Retries are what actually recovers those.
    """
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{offset:.3f}",
        "-i", str(source.resolve()),
        "-t", f"{duration:.3f}",
        "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1",
        str(out_path.resolve()),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg failed to slice at {offset:.0f}s: {result.stderr.strip()}")
    return out_path


def extract_audio(source: Path, out_path: Path) -> Path:
    """Extract mono 64 kbps mp3, matching what the engine produces."""
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source.resolve()),
        "-vn", "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1",
        str(out_path.resolve()),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"ffmpeg failed to extract audio: {result.stderr.strip()}")
    return out_path


def load_api_key(preferred: str | None = None) -> tuple[str | None, str | None]:
    """Return (backend, key), matching the engine's own resolution order."""
    def from_dotenv(path: Path, name: str) -> str | None:
        if not path.exists():
            return None
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() != name:
                    continue
                value = value.strip()
                if len(value) >= 2 and value[0] in ("\"", "'") and value[-1] == value[0]:
                    value = value[1:-1]
                return value or None
        except OSError:
            return None
        return None

    dotenv_paths = [Path.home() / ".config" / "watch" / ".env", Path.cwd() / ".env"]
    candidates = (("GROQ_API_KEY", "groq"), ("OPENAI_API_KEY", "openai"))
    if preferred is not None:
        candidates = tuple(c for c in candidates if c[1] == preferred)

    for key_name, backend in candidates:
        value = os.environ.get(key_name)
        value = value.strip() if value else None
        if not value:
            for candidate in dotenv_paths:
                value = from_dotenv(candidate, key_name)
                if value:
                    break
        if value:
            return backend, value
    return None, None


def build_multipart(path: Path, model: str) -> tuple[bytes, str]:
    """Encode one transcription request body. Returns (body, boundary)."""
    boundary = uuid.uuid4().hex
    body = bytearray()

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: audio/mpeg\r\n\r\n".encode()
    )
    body.extend(path.read_bytes())
    body.extend(b"\r\n")

    for name, value in (("model", model), ("response_format", "verbose_json")):
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())

    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), boundary


def transcribe_one(path: Path, backend: str, key: str, log=None) -> dict:
    """POST a single chunk, retrying transient faults and waiting out quota."""
    endpoint = GROQ_ENDPOINT if backend == "groq" else OPENAI_ENDPOINT
    model = GROQ_MODEL if backend == "groq" else OPENAI_MODEL
    body, boundary = build_multipart(path, model)

    last: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(
            endpoint, data=body,
            headers={
                "Authorization": f"Bearer {key}",
                # Without this Groq's edge answers 403.
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            detail = exc.read().decode("utf-8", "replace")[:160]
            # 429 means the hourly audio quota is spent. That is not a fault
            # and retrying fast only wastes the window.
            wait = QUOTA_WAIT_SECONDS if exc.code == 429 else min(2.0 ** attempt, 60.0)
            if log:
                log(f"HTTP {exc.code} on {path.name} "
                    f"(attempt {attempt}/{MAX_ATTEMPTS}), waiting {wait:.0f}s — {detail}")
            if attempt == MAX_ATTEMPTS:
                break
            time.sleep(wait)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if log:
                log(f"{type(exc).__name__} on {path.name} "
                    f"(attempt {attempt}/{MAX_ATTEMPTS}) — {exc}")
            if attempt == MAX_ATTEMPTS:
                break
            time.sleep(min(2.0 ** attempt, 60.0))

    raise RuntimeError(f"whisper failed for {path.name} after {MAX_ATTEMPTS} attempts: {last}")


def shift_segments(segments: list[dict], offset: float) -> list[tuple[float, str]]:
    """Convert one chunk's 0-based segments into absolute source time."""
    out: list[tuple[float, str]] = []
    for segment in segments:
        try:
            start = float(segment["start"]) + offset
        except (KeyError, TypeError, ValueError):
            continue
        text = str(segment.get("text", "")).strip()
        if text:
            out.append((start, text))
    return out


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def render_report(source: str, duration: float, segments: list[tuple[float, str]],
                  complete: bool = True) -> str:
    """Emit a report in the engine's own format.

    ingest.has_transcript() looks for the "**Transcript:** N segments" line and
    segment.py parses the "[MM:SS] text" lines, so both must match exactly.
    """
    lines = [
        "",
        "# watch: video report",
        "",
        f"- **Source:** {source}",
        f"- **Duration:** {format_timestamp(duration)} ({duration:.1f}s)",
        "- **Detail:** transcript",
        f"- **Transcript:** {len(segments)} segments (chunked wrapper)",
    ]
    if not complete:
        lines.append("- **Warning:** transcript is PARTIAL — some chunks failed.")
    lines += ["", "## Transcript", ""]
    for seconds, text in segments:
        lines.append(f"[{format_timestamp(seconds)}] {text}")
    lines.append("")
    return "\n".join(lines)


def transcribe(
    source: Path,
    work_dir: Path,
    backend: str,
    key: str,
    chunk_seconds: float = DEFAULT_CHUNK_SECONDS,
    log=None,
) -> tuple[list[tuple[float, str]], bool]:
    """Transcribe a whole video by chunking. Returns (segments, complete).

    Never raises on a partial failure: whatever transcribed is returned with
    complete=False, so a quota limit costs the tail rather than the run.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    audio = work_dir / "audio.mp3"
    if not audio.exists():
        if log:
            log("extracting audio…")
        extract_audio(source, audio)

    duration = ffprobe_duration(audio) or ffprobe_duration(source)
    plan = plan_chunks(duration, chunk_seconds)
    if log:
        log(f"{duration:.0f}s audio → {len(plan)} chunks of {chunk_seconds:.0f}s")

    segments: list[tuple[float, str]] = []
    complete = True
    for index, (offset, chunk_duration) in enumerate(plan):
        cache = work_dir / f"chunk_{index:03d}.json"
        if cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                segments.extend(shift_segments(data.get("segments") or [], offset))
                if log:
                    log(f"chunk {index + 1}/{len(plan)} cached")
                continue
            except (OSError, json.JSONDecodeError):
                pass  # fall through and re-fetch

        part = work_dir / f"chunk_{index:03d}.mp3"
        if not part.exists():
            slice_audio(audio, part, offset, chunk_duration)

        try:
            data = transcribe_one(part, backend, key, log=log)
        except RuntimeError as exc:
            if log:
                log(f"chunk {index + 1}/{len(plan)} failed, keeping partial — {exc}")
            complete = False
            break

        # Cache before anything else can fail: never re-pay for this chunk.
        cache.write_text(json.dumps(data), encoding="utf-8")
        chunk_segments = shift_segments(data.get("segments") or [], offset)
        segments.extend(chunk_segments)
        if log:
            log(f"chunk {index + 1}/{len(plan)} → {len(chunk_segments)} segments")

    segments.sort(key=lambda pair: pair[0])
    return segments, complete
