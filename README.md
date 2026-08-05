# learn-from-video

> Turn any video into a comprehensive, professional learning report — capturing everything that was **spoken AND shown on screen**.

**v3.1** — now running on the `watch` ingestion engine: any yt-dlp-supported site, Whisper fallback for videos without captions, scene-aware frame selection, and a setup preflight that installs what's missing.

---

## What's in the box

Two skills that install together:

| Skill | Invoke | What it does |
|---|---|---|
| **`learn-from-video`** | `learn from this video: <url>` | Produces a full `.docx` study report — screenshots embedded inline, code recovered from the screen and completed to working examples, diagrams recreated as Mermaid. |
| **`watch`** | `/watch <url> [question]` | Gives the model eyes on a video and answers questions in chat. This is also the engine `learn-from-video` runs on. |

Rule of thumb: **`/watch` when you want an answer, `learn-from-video` when you want a document.**

---

## What learn-from-video does

1. **Pulls a timestamped transcript** — native captions where they exist, Whisper (Groq or OpenAI) where they don't
2. **Analyzes it for visual moments** and tags them `CODE` / `DIAGRAM` / `SLIDE` / `UI` / `TERMINAL` / `DATA`
3. **Extracts frames** — scene-aware, with those tagged moments *pinned* so a "look at this" beat is never dropped, plus denser focused passes over code windows
4. **Reads every frame** — extracting slides, diagrams, code, terminal output, architecture flows
5. **Multi-pass code extraction** — merges fragments across frames as the presenter scrolls, then completes them to working examples with `FROM VIDEO` / `ADDED FOR COMPLETENESS` markers
6. **Generates a Word document** combining spoken content and visuals inline

The result is a thorough report — not a brief summary — where diagrams, code, and visuals appear **inline exactly where they are discussed**, never in a separate appendix.

---

## Installation

**Claude Code (plugin — recommended, installs both skills):**

```bash
/plugin marketplace add yogeshcodeshare/learn-from-video-Skill
```

then

```bash
/plugin install learn-from-video@learn-from-video
```

**Codex / Cursor / Copilot / 50+ other Agent Skills hosts:**

```bash
npx skills add yogeshcodeshare/learn-from-video-Skill -g
```

**claude.ai (web):** download `learn-from-video.skill` and `watch.skill` from the [latest release](https://github.com/yogeshcodeshare/learn-from-video-Skill/releases) and upload both via the skill UI.

> Upgrading from v3.0? The skill moved from the repo root to `skills/learn-from-video/`. Remove the old install first.

---

## Setup

On first run the skill runs a preflight and handles this for you. Manually:

```bash
python3 skills/watch/scripts/setup.py
```

| Dependency | Notes |
|---|---|
| Python 3 | stdlib only — no pip packages required |
| `ffmpeg` + `yt-dlp` | auto-installed on macOS via Homebrew; exact commands printed on Linux/Windows |
| Node.js + npm | needed only for the `.docx` generation step (`npm install docx`) |
| Whisper API key | **optional but recommended** — `GROQ_API_KEY` (cheaper, faster) or `OPENAI_API_KEY` in `~/.config/watch/.env`. Without one, videos lacking native captions come back frames-only. |

**Windows:** use `python` rather than `python3` — the `python3` command is a Microsoft Store stub and won't run the scripts.

---

## How to Use

Share a video URL or file and ask for notes. The skill triggers automatically.

**Trigger phrases:**

- `learn from this video: https://video-url-here`
- `learnFromVideo https://video-url-here`
- `create notes from this video`
- `make notes for this video`
- `summarize this video in detail`
- `take notes from this lecture`
- `I don't have time to watch this — create notes`

**Multiple videos on the same topic** — pass several URLs at once. Content merges by *theme*, not by video, with a comparison table and `[Video N]` attribution tags.

**Fast mode** — say "quick notes" / "just the highlights" for a 3-5 minute pass (keyframes, 512px, no Mermaid recreation) instead of the 8-15 minute detailed pass.

---

## Cost

Frames dominate token cost. Detailed Mode captures at 1024px wide because on-screen code is unreadable at 512px — roughly 4× the image tokens of the engine's default. A dense 10-minute coding video is a genuinely expensive run; the skill tells you before an exhaustive pass and offers a focused alternative (`--start`/`--end` over just the section you care about).

---

## Repo layout

```
skills/
  watch/                  ingestion engine (vendored, MIT)
  learn-from-video/       report pipeline + docx assembly
    references/           report structure, self-improvement loop
    eval/                 30 binary output-quality assertions
tests/                    pytest suite for the engine (no network)
hooks/                    Claude Code SessionStart setup status
```

See [AGENTS.md](AGENTS.md) for the development contract and [CHANGELOG.md](CHANGELOG.md) for what changed in v3.1.

---

## Credits

The `watch` ingestion engine (`skills/watch/`), test suite, hooks, and packaging scaffolding come from [**bradautomates/claude-video**](https://github.com/bradautomates/claude-video) by Bradley Bonanno, MIT licensed — vendored at upstream version 0.2.0. The report pipeline, document assembly, and evaluation framework are original to this repo.

MIT licensed. See [LICENSE](LICENSE).
