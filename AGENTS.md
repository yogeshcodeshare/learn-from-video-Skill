# learn-from-video

Agent Skills package that turns a video into a comprehensive Word-document learning report. Installable across Claude Code (most common host), Codex, Cursor, GitHub Copilot, and 50+ other [Agent Skills](https://agentskills.io) hosts.

Two skills ship together:

- **`watch`** — the ingestion engine. Pure-stdlib Python orchestrating `yt-dlp` + `ffmpeg` and an optional Whisper API. Answers questions about a video in chat. Vendored from [bradautomates/claude-video](https://github.com/bradautomates/claude-video) (MIT).
- **`learn-from-video`** — the report generator. Drives the engine through a 5-agent pipeline and assembles a `.docx` via docx-js.

The split is deliberate: `/watch` gives the model *eyes*, `learn-from-video` decides *what to write down*.

## Structure

- `skills/watch/SKILL.md` — canonical engine contract; source of truth for `/watch` behavior across every host.
- `skills/watch/scripts/watch.py` — entry point; orchestrates download → frames → transcript.
- `skills/watch/scripts/{download,frames,transcribe,whisper,setup,config}.py` — yt-dlp wrapper, ffmpeg frame extraction + auto-fps, caption/Whisper transcription, preflight/installer, shared config.
- `skills/learn-from-video/SKILL.md` — the report pipeline (Agents 1-5) and docx assembly rules.
- `skills/learn-from-video/references/report_structure.md` — docx-js formatting patterns.
- `skills/learn-from-video/references/self_improve_prompt.md` — autonomous improvement loop.
- `skills/learn-from-video/eval/eval.json` — 30 binary output-quality assertions.
- `skills/learn-from-video/scripts/ingest.py` — **the only supported way to call the engine.** Adds UTF-8 safety, transcript caching and 5xx retries. Never call `watch.py` directly from this skill.
- `skills/learn-from-video/scripts/segment.py` — transcript → time windows + coverage checklist + word floor.
- `skills/learn-from-video/scripts/verify_docx.py` — density gate. Exit `4` = too thin, do not deliver.
- `skills/learn-from-video/scripts/preflight.py` — Node/npm + engine check, run *before* frame extraction.
- `skills/learn-from-video/scripts/fetch_transcript.py` — legacy YouTube-only transcript fallback for environments without yt-dlp.
- `skills/*/scripts/build-skill.sh` — build `dist/<name>.skill` for claude.ai upload (dev-only).
- `hooks/` — Claude Code SessionStart setup-status hook (Claude Code only).
- `.claude-plugin/` — `plugin.json` + `marketplace.json`.
- `.codex-plugin/plugin.json` — Codex/agents manifest; `"skills": "./skills/"` points the Agent Skills CLI at both skill folders.
- `.agents/plugins/marketplace.json` — agents marketplace listing.
- `CLAUDE.md` → `@AGENTS.md` — generic-agent entry point.
- `tests/` — pytest suite for the engine (ffmpeg-synthesized clips; no network).

## Orientation

- The product is the slash-command-invoked skills, not a CLI. `scripts/watch.py` is implementation. Features must work across every harness the skills install into, not just Claude Code.
- **Each skill is one self-contained folder.** SKILL.md and `scripts/` are siblings inside it. This is what lets `npx skills add` copy a working skill as a unit — do NOT move a SKILL.md or `scripts/` to the repo root.
- **`learn-from-video` depends on `watch` as a sibling directory** (`$SKILL_DIR/../watch`). Keep them in the same plugin. If you ever split them, the report skill degrades to `fetch_transcript.py` and no frames.
- **Path resolution is harness-agnostic.** Each SKILL.md resolves `SKILL_DIR` as the directory of the SKILL.md the model just Read. Do NOT reintroduce `${CLAUDE_SKILL_DIR}` (Claude-Code-only) — it is unset on Codex/Cursor/agents and breaks every script call there.
- **No `commands/` wrapper.** Slash commands derive from SKILL.md frontmatter (`name:` + `user-invocable: true`). A separate command file creates a duplicate.
- **Never hand-roll `yt-dlp`/`ffmpeg` in a SKILL.md.** That was the v3.0 design and it was fragile. All ingestion goes through `watch.py`, and from learn-from-video always via `ingest.py`.
- **`skills/watch/` is vendored byte-identical to upstream and must stay that way.** Verify with `git rev-parse HEAD:skills/watch` — it must equal `a998b18e29c46ecc7d08c4aad90db1cdd757cc7d`. Fixes for engine bugs belong in `learn-from-video/scripts/` as a wrapper, not as edits to the vendored tree. This keeps future upstream merges clean.
- **Depth is enforced, not encouraged.** `verify_docx.py` exit `4` blocks delivery. Do not "fix" a density failure by lowering thresholds — that reintroduces the exact defect the gate exists to catch.

## Install surfaces

| Surface | Install |
|---------|---------|
| Claude Code | `/plugin marketplace add yogeshcodeshare/learn-from-video-Skill` then `/plugin install learn-from-video@learn-from-video` |
| Codex / Cursor / Copilot / +50 | `npx skills add yogeshcodeshare/learn-from-video-Skill -g` |
| claude.ai (web) | upload `dist/learn-from-video.skill` and `dist/watch.skill` |

## Commands

```bash
# Engine tests (stdlib + pytest; ffmpeg required for frame tests)
python3 -m pytest -q

# Build the claude.ai upload bundles
bash skills/watch/scripts/build-skill.sh              # → dist/watch.skill
bash skills/learn-from-video/scripts/build-skill.sh   # → dist/learn-from-video.skill

# Dev: mirror the working tree into the installed Claude Code plugin cache
./dev-sync.sh                       # --dry-run to preview
```

## Rules

- Keep the version in sync across both `SKILL.md` frontmatters, `.claude-plugin/plugin.json`, and `.codex-plugin/plugin.json` when cutting a release.
- Releasing: tag `vX.Y.Z` and push the tag; `.github/workflows/release.yml` builds both `.skill` bundles and attaches them to the GitHub release.
- Never commit real API keys or `.env` contents; keys live in `~/.config/watch/.env` (mode `0600`) at runtime.
- When syncing upstream engine changes, pull them into `skills/watch/` and `tests/` only — keep local edits out of that subtree so future merges stay clean. Record the upstream commit in `CHANGELOG.md`.
