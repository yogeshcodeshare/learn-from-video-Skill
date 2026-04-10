# learn-from-video

> A Claude Code skill that turns any YouTube video into a comprehensive, professional learning report — capturing everything that was **spoken AND shown on screen**.

---

## What It Does

When you share a YouTube URL, this skill:

1. **Fetches the full transcript** with timestamps
2. **Downloads the video** and extracts screenshots at key moments (every 20–30 seconds + targeted visual timestamps)
3. **Reads every screenshot** — extracting slides, diagrams, code, terminal output, architecture flows
4. **Completes partial code** shown in the video into fully working examples
5. **Generates a professional Word document (.docx)** that combines spoken content + visuals inline — so reading it feels like watching the video

The result is a thorough report (not a brief summary) where diagrams, code, and visuals appear **inline** exactly where they are discussed — not in a separate appendix.

---

## Installation

```bash
npx skills add https://github.com/yogeshcodeshare/learn-from-video-Skill.git
```

That's it. The skill is now available in your Claude Code session.

---

## Prerequisites

Make sure the following are installed on your machine:

| Tool | Install |
|------|---------|
| Python 3 | [python.org](https://python.org) |
| `youtube-transcript-api` | `pip install youtube-transcript-api` |
| `yt-dlp` | `pip install yt-dlp` |
| `ffmpeg` | `brew install ffmpeg` (Mac) / `apt install ffmpeg` (Linux) |
| Node.js + npm | [nodejs.org](https://nodejs.org) |

The skill will attempt to auto-install missing Python packages on first run.

---

## How to Use

Just share a YouTube URL and ask for notes. Claude will trigger this skill automatically.

### Trigger phrases:

- `learn from this video: https://youtube.com/watch?v=...`
- `learnFromVideo https://youtube.com/watch?v=...`
- `create notes from this YouTube video`
- `make notes for this video`
- `summarize this YouTube video in detail`
- `take notes from this lecture`
- `I don't have time to watch this — create notes`

### Single video:
```
learnFromVideo https://www.youtube.com/watch?v=VIDEO_ID
```

### Multiple videos on the same topic:
```
learnFromVideo these two videos and combine the notes:
https://www.youtube.com/watch?v=VIDEO_ID_1
https://www.youtube.com/watch?v=VIDEO_ID_2
```

---

## Output

The skill generates a `.docx` Word document saved to your workspace:

- **Single video** → `[VideoTitle]_LearnFromVideo_Notes.docx`
- **Multiple videos** → `[Topic]_Combined_LearnFromVideo_Notes.docx`

### Document structure:

| Section | Description |
|---------|-------------|
| Cover Page | Title, channel, URL, date, duration |
| Table of Contents | Manual TOC — works in Word, Google Docs, LibreOffice |
| Executive Summary | 3–5 key takeaways, audience, difficulty level |
| Core Content | Adaptive — follows the video's natural flow |
| Quick Reference | Commands, tools, key facts for quick scanning |
| Sources & Resources | Video URLs, mentioned tools and links |

### Within each content section:
- Embedded screenshots at key visual moments
- Reconstructed architecture/workflow diagrams as Mermaid flowcharts
- Code blocks with language labels — captured exactly as shown, then completed
- Inline comments on key code lines
- Timestamp references to jump back to the video
- Visual callout boxes for important on-screen content

---

## Example Output

For a 45-minute video on Claude Code tips, the skill produces a 30–50 page Word document with:

- Full spoken content in natural, flowing prose
- 40–60 embedded screenshots at key moments
- All code shown on screen captured and completed to working examples
- Architecture diagrams recreated as Mermaid flowcharts
- Quick reference table of all commands mentioned
- Timestamps throughout so you can jump to any moment in the video

---

## Multi-Video Support

Provide multiple YouTube URLs on the same topic and the skill will:

- Merge overlapping content by theme (not listed video-by-video)
- Cross-reference where videos agree or offer different perspectives
- Produce one unified document with a "Video Sources" table at the top
- Rank key takeaways by emphasis across all videos

---

## Edge Cases Handled

| Situation | Behavior |
|-----------|----------|
| No captions available | Asks user to paste transcript manually |
| Private / restricted video | Falls back to transcript-only mode |
| Non-English video | Detected automatically, noted in document header |
| Very long video (>1 hour) | Screenshot interval increased, "Reading Guide" added |
| Playlist URL | Each video extracted and processed individually |
| Partial / garbled transcript | Unclear segments marked `[unclear at timestamp]` |

---

## How It Works (Under the Hood)

```
YouTube URL
    │
    ▼
1. Fetch Transcript (youtube-transcript-api)
    │  → timestamps, chapter detection
    │
    ▼
2. Analyze Transcript for Visual Timestamps
    │  → find "as you can see", "here's the code", "this diagram" etc.
    │
    ▼
3. Download Video (yt-dlp) + Extract Frames (ffmpeg)
    │  → every 25s + targeted key moments
    │
    ▼
4. Read & Analyze Every Screenshot
    │  → slides, code, diagrams, terminal output, UI
    │
    ▼
5. Complete Partial Code
    │  → add imports, signatures, mark original vs. added
    │
    ▼
6. Combine Transcript + Visuals
    │  → one unified explanation per topic
    │
    ▼
7. Generate .docx (docx-js)
    │  → embedded images, Mermaid diagrams, code blocks, TOC
    │
    ▼
Output: Professional Word Document
```

---

## Quality Standard

The report should be thorough enough that **reading it gives 90%+ of the value of watching the video**. This means:

- No skipping "minor" points — everything is captured
- Diagrams and code appear **inline** where discussed (never in a separate appendix)
- Code is completed to working examples with clear markers for what was added
- The document reads as one cohesive explanation, not a bullet-point dump

---

## Attribution

Every generated document includes:
- Full video URL and channel name on the cover page
- Footer: *"Notes generated from YouTube video for personal learning use"*
- Final page: *"For the complete experience, watch the original video at [URL]. All content credit to [channel name]."*

This skill is intended for **personal learning use** only. Respect the original creator's content.

---

## Credits

Built as a Claude Code skill by [@yogeshcodeshare](https://github.com/yogeshcodeshare).

Powered by [Claude Code](https://claude.ai/code) + Anthropic Claude.
