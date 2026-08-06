# Changelog

## v3.2.0 — Content depth, robustness and tests

v3.1 moved ingestion onto a solid engine. v3.2 fixes the two things that run revealed: documents that looked finished but were thin, and a pipeline that threw away paid-for work on any error.

### The content-depth problem

Real-run finding: a 39-minute lecture produced a document referencing only **60% of the transcript** — 8 of 20 two-minute windows had no coverage at all. It looked complete (35 screenshots, styled headings, tables) and taught very little, because the model summarised from an impression of the transcript rather than working through it.

Two mechanical defences now make that failure impossible to ship:

- **`scripts/segment.py`** — slices the transcript into time windows, each carrying its verbatim text, and emits a coverage checklist plus a `min_document_words` floor. You write one subsection per window with that window's text in front of you.
- **`scripts/verify_docx.py`** — measures the finished document against the transcript. Exit code `4` on a density failure means **do not deliver**. It reports word count vs. floor, image count, and exactly which windows have no coverage.

The word floor expands rather than compresses: **0.9× spoken words minimum**, because a reader also needs on-screen state, exact field names, and steps the speaker performed silently.

SKILL.md now carries an explicit anti-pattern table — "The instructor explains the difference between X and Y" versus stating the actual difference — with a single test for any sentence: *could a reader act on it without watching the video?*

### Robustness

- **`scripts/ingest.py`** — a wrapper around the engine adding three fixes, each from an observed failure:
  - **UTF-8 safety.** On Windows the engine crashes with `UnicodeEncodeError` on Devanagari/CJK/Cyrillic/emoji *after* the Whisper call completed and was paid for. The transcript was produced, then destroyed. The wrapper forces UTF-8 so a non-English transcript cannot destroy itself.
  - **Transcript caching.** The engine cached extracted audio but not the transcript, so any later crash meant re-uploading and paying again. Reports are now cached per (source, flags) in `$WORK/.lfv-cache/`.
  - **Retries.** Groq returned HTTP 500 mid-run and aborted an otherwise-complete pipeline. Transient 5xx errors now retry with exponential backoff.
- **`scripts/preflight.py`** — checks Node + npm (needed for docx) *before* frame extraction, not after. Delegates ffmpeg/yt-dlp/Whisper to the engine's own `setup.py`. Exit `3` means ingestion works but no document can be produced.

### Tests

`tests/test_learn_from_video.py` — **21 tests**, no network, no ffmpeg, no API keys. Suite grows from 71 to 92. Covers window segmentation, rolling-caption dedupe, Devanagari handling, density failure detection, coverage measurement, cache-key stability, and transient-error classification.

### Also

- Mandatory cost gate: videos over 20 minutes require explicit user agreement before frame extraction.
- Non-Latin/machine-transcript rule: state which content came from Whisper (may contain errors) and which was read from screenshots (reliable).
- Third-party software shown for comparison must be labelled, so readers don't mistake it for the product being taught.
- If the file's timeline differs from a timeline the user supplies, use the file's and say so.

### Upstream parity preserved

All fixes live in `skills/learn-from-video/scripts/`. **`skills/watch/` remains byte-identical to upstream** — verified by git tree hash `a998b18e29c46ecc7d08c4aad90db1cdd757cc7d`. The encoding bug is an upstream defect worth reporting to bradautomates/claude-video; this repo works around it rather than forking.

---

## v3.1.0 — Watch engine

The ad-hoc `yt-dlp`/`ffmpeg` shell commands that lived inside SKILL.md are gone. Ingestion now runs on the vendored `watch` engine from [bradautomates/claude-video](https://github.com/bradautomates/claude-video) (MIT), bundled as a sibling skill.

### Added

- **`watch` skill** (`skills/watch/`) — the ingestion engine, vendored verbatim from upstream. Also usable on its own as `/watch <url> [question]` to ask questions about a video in chat.
- **Whisper transcript fallback** — videos with no captions now work. Audio only (never the video) is sent to Groq `whisper-large-v3` (preferred: cheaper, faster) or OpenAI `whisper-1`. Audio over the 25 MB API cap is chunked automatically. Previously, a video without YouTube captions was a dead end.
- **Any yt-dlp-supported source** — Vimeo, X, TikTok, Twitch clips, and local files, not just YouTube.
- **Scene-aware frame selection** — ffmpeg scene-change detection with a uniform-sampling fallback for static video, replacing fixed-interval sampling.
- **Automatic near-duplicate frame removal** — a frame-delta pass drops held slides and static screen recordings so the frame budget goes to distinct content. `--no-dedup` opts out (used deliberately when capturing typing sequences).
- **Transcript-cue frames** (`--timestamps`) — Agent 1's tagged "as you can see" moments are now *pinned* frames, reserved against the frame cap before scene selection runs. Deictic moments are exactly what visual selection misses, since pointing at a static slide is a low-visual-change event.
- **Focused section passes** (`--start`/`--end`) — denser sampling over a named range, replacing the hand-rolled `for i in $(seq ...); do ffmpeg -ss ...` loop for code windows.
- **Setup preflight** (`setup.py`) — auto-installs `ffmpeg` + `yt-dlp` on macOS via Homebrew, prints exact commands on Linux/Windows, scaffolds `~/.config/watch/.env` at mode `0600`. `--check` is a <100ms silent gate; `--json` is machine-readable.
- **Detail modes** — `transcript` / `efficient` / `balanced` / `token-burner` replace the two ad-hoc quality tiers. Fast Mode maps to `efficient`, Detailed Mode to `balanced`.
- **Plugin packaging** — `.claude-plugin/` (plugin + marketplace), `.codex-plugin/`, `.agents/plugins/`. Installable on Claude Code, Codex, Cursor, Copilot and 50+ Agent Skills hosts.
- **SessionStart hook** (`hooks/`) — one-line setup status in Claude Code, silent when everything is wired up.
- **Release CI** — tag `vX.Y.Z` to build and attach `dist/learn-from-video.skill` and `dist/watch.skill` to a GitHub release.
- **Test suite** (`tests/`) — 10 pytest files covering the engine against ffmpeg-synthesized clips, no network required.
- **`dev-sync.sh`** — mirror the working tree into the installed plugin cache without publishing.

### Changed

- **Repo layout is now a plugin.** The skill moved from the repo root to `skills/learn-from-video/`. `npx skills add` on the repo now installs both skills.
- **Detailed Mode captures at `--resolution 1024`**, up from the engine's 512px default, because on-screen code is unreadable at 512px. This roughly quadruples image tokens per frame — a deliberate trade for this skill's job. Fast Mode stays at 512px.
- **`SKILL_DIR` resolution is harness-agnostic** — derived from the path of the SKILL.md the model read, rather than assuming a fixed install path or `${CLAUDE_SKILL_DIR}`.
- **Windows is documented** — `python`, not `python3` (the `python3` command on Windows is a Microsoft Store stub).
- **Cleanup is explicit** — work dirs hold the full downloaded video plus every frame, and are removed after the document is verified rather than deleting the video mid-pipeline.
- Frame timestamps are absolute source time in every mode, so they align directly against the transcript.

### Removed

- Hand-rolled `yt-dlp` fallback chain and `ffmpeg` extraction loops from SKILL.md. The engine handles fallbacks, 2 fps rate capping, and the 1998px height clamp required for `Read` compatibility.
- `export PATH="$HOME/.local/bin:$PATH"` preamble and `pip install --break-system-packages` guidance — `setup.py` owns dependency installation now.

### Retained

- `scripts/fetch_transcript.py` as a YouTube-only legacy fallback for environments where `yt-dlp` cannot be installed.
- The whole report design: adaptive (non-template) structure, combined-not-separated philosophy, the 5-agent pipeline, multi-pass code recovery with `FROM VIDEO` / `ADDED FOR COMPLETENESS` markers, inline Mermaid recreation, manual TOC, and the docx-js gotcha list.

### Attribution

`skills/watch/`, `tests/`, `hooks/`, `.gitattributes`, `.skillignore`, and `dev-sync.sh` originate from [bradautomates/claude-video](https://github.com/bradautomates/claude-video) by Bradley Bonanno, MIT licensed. Upstream `watch` version at time of vendoring: **0.2.0**. See `CHANGELOG-upstream.md` for its history.

---

## v3.0

Multi-agent parallel architecture with a dedicated Code Specialist agent, adaptive screenshot intervals, and the automated self-improvement loop.
