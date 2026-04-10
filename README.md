# learn-from-video

> A Claude Code skill that turns any online video into a comprehensive, professional learning report — capturing everything that was **spoken AND shown on screen**.

**v3.0** — Multi-agent parallel architecture with dedicated Code Specialist agent, adaptive screenshot intervals, and automated self-improvement.

---

## What It Does

When you share a video URL or file, this skill:

1. **Fetches the full transcript** with timestamps and analyzes it for visual content moments
2. **Downloads the video at 720p** and extracts screenshots using adaptive intervals (3s for code, 30s for talking)
3. **Reads every screenshot** — extracting slides, diagrams, code, terminal output, architecture flows
4. **Multi-pass code extraction** — captures code from multiple frames, merges fragments, completes to working examples
5. **Generates a professional Word document (.docx)** that combines spoken content + visuals inline

The result is a thorough report (not a brief summary) where diagrams, code, and visuals appear **inline** exactly where they are discussed — not in a separate appendix.

---

## Installation

```bash
npx skills add https://github.com/yogeshcodeshare/learn-from-video-Skill.git
```

That's it. The skill is now available in your Claude Code session.

---

## Prerequisites

| Tool | Install |
|------|---------|
| Python 3 | [python.org](https://python.org) |
| `yt-dlp` | `pip install yt-dlp` |
| `ffmpeg` | `brew install ffmpeg` (Mac) / `apt install ffmpeg` (Linux) |
| Node.js + npm | [nodejs.org](https://nodejs.org) |

The skill will attempt to auto-install missing Python packages on first run.

---

## How to Use

Just share a video URL or file and ask for notes. Claude will trigger this skill automatically.

### Trigger phrases:

- `learn from this video: https://video-url-here`
- `learnFromVideo https://video-url-here`
- `create notes from this video`
- `make notes for this video`
- `summarize this video in detail`
- `take notes from this lecture`
- `I don't have time to watch this — create notes`

### Single video:
```
learnFromVideo https://www.video-platform.com/watch?v=VIDEO_ID
```

### Multiple videos on the same topic:
```
learnFromVideo these two videos and combine the notes:
https://www.video-platform.com/watch?v=VIDEO_ID_1
https://www.video-platform.com/watch?v=VIDEO_ID_2
```

### Local video file:
```
learnFromVideo /path/to/local/video.mp4
```

---

## Speed/Quality Modes

| Mode | Trigger | Video Quality | Screenshot Interval | Code Extraction | Target Time |
|------|---------|--------------|--------------------|--------------------|-------------|
| **Fast** | "quick notes", "fast summary" | 480p | 45s fixed | Single-pass | 3-5 min |
| **Detailed** (default) | All other requests | 720p | 3-45s adaptive | Multi-pass with gap fill | 8-15 min |

---

## Multi-Agent Architecture (v3.0)

The skill uses a **5-agent parallel pipeline** organized in 3 phases:

```
Phase 1:  Agent 1 (Transcript Analyst)
              │
Phase 2:  Agent 2 (Screenshots) ║ Agent 3 (Code Specialist) ║ Agent 4 (Visual Analyst)
              │
Phase 3:  Agent 5 (Document Assembler)
```

| Agent | Role |
|-------|------|
| **Transcript Analyst** | Fetches transcript, tags timestamps by content type (CODE, DIAGRAM, SLIDE, etc.) |
| **Screenshot Extractor** | Downloads at 720p, adaptive intervals (3s for code, 30s for talking), deduplicates |
| **Code Specialist** | Multi-pass extraction: capture → gap detect → merge fragments → complete → explain |
| **Visual Content Analyst** | Diagrams → Mermaid, slides → text, data → tables. Smart embed/skip decisions |
| **Document Assembler** | Combines all outputs into final .docx with inline visuals, code, and diagrams |

---

## Output

The skill generates a `.docx` Word document saved to your workspace:

- **Single video** → `[VideoTitle]_LearnFromVideo_Notes.docx`
- **Multiple videos** → `[Topic]_Combined_LearnFromVideo_Notes.docx`

### Document structure:

| Section | Description |
|---------|-------------|
| Cover Page | Title, channel/source, URL, date, duration |
| Table of Contents | Manual TOC — works in Word, Google Docs, LibreOffice |
| Executive Summary | 3-5 key takeaways, audience, difficulty level |
| Core Content | Adaptive — follows the video's natural flow |
| Quick Reference | Commands, tools, key facts for quick scanning |
| Sources & Resources | Video URLs, mentioned tools and links |

### Within each content section:
- Embedded screenshots at key visual moments (smart selection — face-cam skipped)
- Reconstructed architecture/workflow diagrams as Mermaid flowcharts
- Code blocks with language labels — captured, merged from multiple frames, completed
- `FROM VIDEO [timestamp]` and `ADDED FOR COMPLETENESS` markers on code
- Timestamp references to jump back to the video
- Visual callout boxes for important on-screen content

---

## Multi-Video Support

Provide multiple video URLs on the same topic and the skill will:

- Identify themes by keyword overlap across transcripts
- Merge overlapping content by theme (not listed video-by-video)
- Cross-reference with [Video 1] / [Video 2] tags where content overlaps
- Include comparison tables for topics covered by multiple videos
- Produce one unified document with a "Video Sources" table at the top

---

## Self-Improvement (eval.json)

The skill includes an automated evaluation framework with **30 binary assertions** across 3 test types:

| Test | Assertions | Focus |
|------|-----------|-------|
| Short tutorial | 20 | Full document structure, formatting, cleanup |
| Code-heavy video | 5 | Code extraction, completion, inline placement |
| Multi-video | 5 | Theme merging, cross-referencing, comparison tables |

Run the Karpathy-style self-improvement loop:
```
See references/self_improve_prompt.md
```

This enables autonomous overnight improvement — the skill tests itself, identifies failures, makes ONE change, re-tests, and commits if improved.

---

## Edge Cases Handled

| Situation | Behavior |
|-----------|----------|
| No captions available | Asks user to paste transcript manually |
| Private / restricted video | Falls back to transcript-only mode |
| yt-dlp not in PATH | Auto-adds `~/.local/bin` to PATH, falls back to `python -m yt_dlp` |
| Non-English video | Detected automatically, noted in document header |
| Very long video (>1 hour) | Screenshot interval increased, "Reading Guide" added |
| Playlist URL | Each video extracted and processed individually |
| Partial / garbled transcript | Unclear segments marked `[unclear at timestamp]` |
| Local video file (.mp4, .mkv) | Processed directly with ffmpeg — no download needed |
| Read-only skill directory | Scripts auto-copied to `/tmp/` |

---

## Repository Structure

```
learn-from-video-Skill/
├── README.md                           ← This file
├── SKILL.md                            ← Main skill definition (v3.0)
├── scripts/
│   └── fetch_transcript.py             ← Transcript extraction script
├── references/
│   ├── report_structure.md             ← docx-js formatting guide + agent output schemas
│   └── self_improve_prompt.md          ← Autonomous improvement loop template
└── eval/
    └── eval.json                       ← 30 binary assertions for quality testing
```

---

## Attribution

Every generated document includes:
- Full video URL/source and channel name on the cover page
- Footer: *"Notes generated from video for personal learning use"*
- Final page: *"For the complete experience, watch the original video at [URL]. All content credit to [channel/creator name]."*

This skill is intended for **personal learning use** only. Respect the original creator's content.

---

## Credits

Built as a Claude Code skill by [@yogeshcodeshare](https://github.com/yogeshcodeshare).

Powered by [Claude Code](https://claude.ai/code) + Anthropic Claude.
