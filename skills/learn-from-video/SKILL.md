---
name: learn-from-video
version: "3.1.0"
description: "Create comprehensive, report-style learning notes from any video — called 'learnFromVideo'. Use this skill whenever the user shares a video URL or file and wants notes, a summary, a study guide, or learning material from it. Also triggers when the user says 'learn from this video', 'learnFromVideo', 'create notes from this video', 'make notes for this video', 'I watched this video and need notes', 'summarize this video in detail', 'take notes from this lecture', 'notes from this tutorial', 'I don't have time to watch this video', or shares one or more video URLs/files and asks for any kind of written output about the content. This skill handles single videos and multiple videos on the same topic, producing a professional Word document (.docx) report with full detail — not a brief summary, but a thorough report capturing everything spoken AND shown in the video, including diagrams, workflows, code, and architecture recreated as Mermaid flowcharts."
argument-hint: "<video-url-or-path> [extra instructions]"
allowed-tools: Bash, Read, Write, Task, AskUserQuestion
homepage: https://github.com/yogeshcodeshare/learn-from-video-Skill
repository: https://github.com/yogeshcodeshare/learn-from-video-Skill
author: yogeshcodeshare
license: MIT
user-invocable: true
---

# learnFromVideo — v3.1

Create professional, report-style learning notes from any video. The user provides one or more video URLs or local video files, and you produce a comprehensive Word document that captures EVERYTHING — what was spoken AND what was shown on screen — combined together so the reader understands the complete picture as if they watched the video themselves.

**v3.1 runs on the bundled `watch` ingestion engine** (`skills/watch/scripts/`) instead of ad-hoc shell commands. That gives this skill: any yt-dlp-supported site (not just YouTube), a Whisper transcript fallback when a video has no captions, scene-aware frame selection, automatic near-duplicate frame removal, and a setup preflight that installs missing binaries. You no longer hand-roll `yt-dlp`/`ffmpeg` loops.

## Why This Skill Exists

When people find great learning videos online, they often don't have time to watch them fully. A transcript alone doesn't capture the full picture — it misses diagrams, architecture flows, code shown on screen, and visual explanations. This skill bridges that gap by combining the transcript WITH actual screenshots from the video to produce notes so thorough that reading them is as good as watching the video.

## Core Philosophy: Combined, Not Separated

**IMPORTANT**: This skill does NOT follow a rigid chapter-based template. Every video is different. The report should read like a natural, flowing document where:

- What was SAID and what was SHOWN are woven together in the same paragraphs and sections
- Diagrams, code, and visual content appear INLINE exactly where they are discussed — NOT in a separate "Diagrams" or "Visual References" chapter
- The structure follows the video's natural flow, not a fixed template
- A reader who reads the report should understand BOTH what the speaker said AND what was on screen at that moment
- Code shown on screen is CAPTURED, COMPLETED, and EXPLAINED inline with additional context

Think of it this way: if the speaker says "here's how the architecture works" and shows a diagram, the report should explain what they said AND show the reconstructed diagram RIGHT THERE — not 20 pages later in a "diagrams chapter."

---

## Resolve `SKILL_DIR` and `WATCH_DIR` (do this before any command)

Every `python3 ...` command below runs a bundled script. Set `SKILL_DIR` to the **absolute path of the directory containing THIS SKILL.md you just Read** — your harness told you that path in the Read result. The `watch` engine is always a sibling skill directory:

```
SKILL_DIR = <dir of this SKILL.md>          # …/skills/learn-from-video
WATCH_DIR = <SKILL_DIR>/../watch            # …/skills/watch
```

Guard once at the start of a run:

```bash
SKILL_DIR="<absolute path of the directory containing the SKILL.md you Read>"
WATCH_DIR="$(cd "$SKILL_DIR/../watch" 2>/dev/null && pwd)"
if [ ! -f "$WATCH_DIR/scripts/watch.py" ]; then
  echo "ERROR: watch engine not found at $WATCH_DIR/scripts/watch.py" >&2
  echo "learn-from-video requires the sibling 'watch' skill from the same plugin." >&2
  exit 1
fi
```

This works on every harness (Claude Code, Codex, Cursor, Gemini CLI, …) without relying on any harness-specific environment variable. Do NOT use `${CLAUDE_SKILL_DIR}` — it is unset outside Claude Code.

**Python interpreter:** every `python3 ...` command below is for macOS/Linux. On **Windows**, substitute `python` — the `python3` command on Windows is the Microsoft Store stub and will not run the script.

## Step 0 — Setup preflight (first invocation in a session)

```bash
python3 "${WATCH_DIR}/scripts/setup.py" --json
```

Branch on the output:

- **`can_proceed: true`, `first_run: false`** → proceed silently to Phase 1. Do not announce that setup is complete.
- **`first_run: true`** → run `python3 "${WATCH_DIR}/scripts/setup.py"` (auto-installs `ffmpeg` + `yt-dlp` on macOS via Homebrew, prints exact commands on Linux/Windows, scaffolds `~/.config/watch/.env` at mode `0600`). Then encourage a Whisper API key via `AskUserQuestion` — Groq (`GROQ_API_KEY`, preferred: cheaper and faster) or OpenAI (`OPENAI_API_KEY`). A key is **encouraged, not required**; without one, videos lacking native captions come back frames-only. Write the answer into `~/.config/watch/.env` and set `SETUP_COMPLETE=true`.
- **`can_proceed: false`, `first_run: false`** → environment regressed. Run the installer to remediate, then proceed. Don't re-ask preferences.

On follow-up invocations in the same session use the silent check (`--check`, <100ms, exits 0 and prints nothing when ready) or skip Step 0 entirely.

Do **not** ask the `WATCH_DETAIL` preference question here — this skill sets detail explicitly per mode (below). That question belongs to `/watch`.

The document-generation step additionally needs **Node.js + npm** (for `docx`). Check with `node --version` and tell the user plainly if it's missing.

---

## Speed/Quality Modes

Default is **Detailed Mode** unless the user explicitly requests fast/quick.

| | Fast Mode | Detailed Mode (default) |
|---|---|---|
| Triggers | "quick notes", "fast summary", "brief notes", "just the highlights" | everything else; "detailed", "comprehensive", "full notes" |
| Engine flags | `--detail efficient --resolution 512` | `--detail balanced --resolution 1024` |
| Frames | fast keyframe pass, cap 50 | scene-aware, cap 100, plus transcript-cue frames |
| Code extraction | single pass | multi-pass with focused re-runs and fragment merging |
| Diagrams | described in text only | recreated as Mermaid |
| Agents | sequential | parallel multi-agent pipeline |
| Target | 3-5 min per video | 8-15 min per video |

For an exhaustive pass on a dense video, use `--detail token-burner` (scene-aware, uncapped) — but warn the user about image-token cost first.

**Resolution matters for code.** The engine defaults to 512px wide, which is unreadable for code in an editor. This skill overrides to `--resolution 1024` in Detailed Mode for exactly that reason. 1024px roughly quadruples image tokens per frame versus 512px — a deliberate trade for a skill whose job is transcribing on-screen code.

---

## Multi-Agent Parallel Architecture

5-agent pipeline in 3 phases. Agents 2, 3, and 4 run in PARALLEL after Agent 1 completes.

```
                    ┌─────────────────┐
                    │   Agent 1:      │
                    │   Transcript    │
                    │   Analyst       │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │   Agent 2:   │ │   Agent 3:   │ │   Agent 4:   │
   │  Screenshot  │ │    Code      │ │   Visual     │
   │  Extractor   │ │  Specialist  │ │   Content    │
   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                ┌──────────────────┐
                │    Agent 5:      │
                │    Document      │
                │    Assembler     │
                └──────────────────┘
```

### Phase 1 — Agent 1: Transcript Analyst

Runs FIRST because everything else depends on its timestamp analysis.

**Step 1 — pick a stable working directory** so later passes reuse the same download instead of re-fetching:

```bash
WORK="${TMPDIR:-/tmp}/lfv-<video-slug>"
```

**Step 2 — get the timestamped transcript** with a transcript-only pass (no frames, no video download when captions exist):

```bash
python3 "${WATCH_DIR}/scripts/watch.py" "<SOURCE>" --detail transcript --out-dir "$WORK"
```

This prints a markdown report to stdout with a `## Transcript` section. The header tells you the provenance: `via captions` (yt-dlp pulled native subs) or `via whisper (groq|openai)` (transcribed from audio). **Record which one** — it goes in the document's source table, and Whisper transcripts warrant a light accuracy caveat for proper nouns and technical terms.

If the report says `Transcript: none available`, the video has no captions AND Whisper was unavailable. Options, in order:
1. Offer to set up a Whisper key (`python3 "${WATCH_DIR}/scripts/setup.py"`), then re-run.
2. Ask the user to paste the transcript manually — guide them: "Click the three dots below the video → Open transcript → Select All → Copy."
3. Proceed frames-only and say so plainly in the document.

> **Legacy fallback:** `${SKILL_DIR}/scripts/fetch_transcript.py "<URL>"` is retained as a YouTube-only transcript fetcher for environments where `yt-dlp` cannot be installed. Prefer the engine — it covers every yt-dlp-supported site plus local files.

**Step 3 — analyze the ENTIRE transcript.** Identify every important timestamp and tag each with a content type:

- `[CODE timestamp_start-timestamp_end]` — code shown in editor/terminal
- `[DIAGRAM timestamp]` — architecture, flowchart, or diagram shown
- `[SLIDE timestamp]` — slide with text/bullet points
- `[UI timestamp]` — app interface, dashboard, website shown
- `[TERMINAL timestamp]` — command line output, running commands
- `[DATA timestamp]` — tables, charts, statistics, benchmarks
- `[KEY_CONCEPT timestamp]` — important concept being explained with visual

**Signal phrases to detect:**
- "as you can see", "on the screen", "this slide shows", "looking at this", "let me show you"
- "here we have", "over here", "right here", "on the left/right"
- "this diagram", "this flowchart", "this architecture"
- "let me write some code", "in our editor", "the code looks like"
- "let me run this", "the output is", "you can see the result"
- "the flow goes from X to Y", "the components are", "this connects to"
- "this table shows", "the comparison", "the benchmark"
- Any mention of file names, IDE, terminal, console, specific numbers being shown

These deictic cues are exactly what the engine's `--timestamps` flag exists for: pointing at a slide is often a *low* visual-change moment that scene detection misses. Your tagged list becomes Agent 2's cue list. Ignore rhetorical uses ("look, the point is…") — this is a judgment call, which is why it's done by you and not a regex.

**Step 4 — produce structured JSON:**

```json
{
  "video_id": "abc123",
  "title": "Video Title",
  "duration": "12:34",
  "transcript_source": "captions",
  "work_dir": "/tmp/lfv-abc123",
  "local_video_path": "/tmp/lfv-abc123/download/...",
  "thematic_outline": [
    { "theme": "Introduction", "start": "0:00", "end": "1:30" },
    { "theme": "Core Concept", "start": "1:30", "end": "5:00" }
  ],
  "key_timestamps": [
    { "time": "3:45", "seconds": 225, "type": "CODE", "description": "Shows Express route handler", "duration_hint": "3:45-4:12" },
    { "time": "7:20", "seconds": 440, "type": "DIAGRAM", "description": "System architecture overview" }
  ],
  "cue_list": "3:45,4:05,7:20",
  "transcript_text": "full transcript with timestamps..."
}
```

For multiple videos, run this for each URL — each into its own `--out-dir`.

---

### Phase 2 — Runs in PARALLEL after Agent 1 completes

#### Agent 2: Screenshot Extractor

Extracts frames using the engine. Two passes.

**Pass A — main sweep with pinned transcript cues:**

```bash
python3 "${WATCH_DIR}/scripts/watch.py" "<SOURCE>" \
  --detail balanced \
  --resolution 1024 \
  --timestamps "3:45,4:05,7:20" \
  --out-dir "$WORK"
```

What each piece buys you:
- `--detail balanced` — scene-aware selection (ffmpeg scene-change detection, uniform-sampling fallback for static video), capped at 100 frames.
- `--timestamps` — Agent 1's cue list. These frames are **pinned**: reserved against the cap before scene selection runs, so they can never be evicted. They appear in the report with `reason=transcript-cue`.
- Near-duplicate frames are dropped **automatically** (held slides, static screen recordings). The report's `Frames:` line says how many. Pass `--no-dedup` only if the user needs every sampled frame.
- Reusing `--out-dir "$WORK"` reuses the already-downloaded video — no second download.

**Pass B — focused re-runs on CODE windows.** Scene detection under-samples a coding session, because typing changes few pixels per frame. For each `[CODE]` window Agent 1 tagged, re-run focused on that range against the **local downloaded file** (from `$WORK/download/`, so nothing is re-fetched):

```bash
python3 "${WATCH_DIR}/scripts/watch.py" "$WORK/download/<video-file>" \
  --start 3:45 --end 4:12 --fps 2 --resolution 1024 \
  --out-dir "$WORK/code-3-45"
```

Focused mode auto-scales denser (up to the 2 fps hard cap). This replaces the old hand-rolled `for i in $(seq ...); do ffmpeg -ss ...` loop entirely.

For long videos (>10 min) the engine prints a sparse-coverage warning. Honour it: prefer several focused passes over the sections that matter to one thin full-video scan.

**Produce a manifest JSON** by collecting the frame lines from every pass:

```json
{
  "video_id": "abc123",
  "detail": "balanced",
  "resolution": 1024,
  "total_frames": 45,
  "frames": [
    { "path": "/tmp/lfv-abc123/frames/frame_0225.jpg", "timestamp": "3:45", "seconds": 225, "type": "CODE", "reason": "transcript-cue" },
    { "path": "/tmp/lfv-abc123/frames/frame_0250.jpg", "timestamp": "4:10", "seconds": 250, "type": "CODE", "reason": "scene" }
  ],
  "deduplicated": 8,
  "work_dir": "/tmp/lfv-abc123"
}
```

Map each frame back to a content type by matching its timestamp against Agent 1's `key_timestamps` windows.

Do **not** delete the video yet — Agent 3 may need more focused passes. Cleanup happens in Step 6.

#### Agent 3: Code Specialist (THE KEY AGENT)

Extracts, completes, and explains code from frames. This is one of the most valuable features of the skill — readers get working code they can actually use.

**Receives:** all frames tagged `[CODE]` or `[TERMINAL]` from Agent 2's manifest, plus transcript context from Agent 1. Read frames with the `Read` tool — it renders JPEGs directly as images.

**Multi-Pass Extraction Process:**

1. **First Pass — Extract**: Read each code frame and transcribe EVERY visible line of code exactly as shown. Note the language, filename (from the tab/title bar if visible), and context. Note what's visible vs. cut off (top/bottom cropped, partially scrolled) and whether code is mid-typing.

2. **Gap Detection**: if code appears cut off or partially scrolled, request more frames — re-run Agent 2's Pass B focused on a tighter window around the gap:
   ```bash
   python3 "${WATCH_DIR}/scripts/watch.py" "$WORK/download/<video-file>" \
     --start 3:52 --end 3:58 --fps 2 --resolution 1024 --no-dedup \
     --out-dir "$WORK/gap-3-52"
   ```
   `--no-dedup` matters here: consecutive frames of someone typing are near-identical by pixel delta but each carries new lines.

3. **Second Pass — Combine**: merge fragments from multiple frames of the same code block into one complete block. Remove duplicated lines from overlapping frames, maintain timestamp ordering, note gaps you couldn't fill.

4. **Third Pass — Complete**: using transcript context AND your own knowledge, complete partial code to a working example — missing imports, function signatures, closing braces, boilerplate, error handling the speaker mentioned but didn't show. Fix obvious low-resolution capture typos.

5. **Mark sources clearly:**
   ```
   // === FROM VIDEO [3:45] ===
   const app = express();
   app.get('/api', handler);
   // === FROM VIDEO [3:52] — scrolled down ===
   function handler(req, res) {
     res.json({ status: 'ok' });
   }
   // === ADDED FOR COMPLETENESS ===
   import express from 'express';
   app.listen(3000);
   ```

6. **Add explanations**: for each significant block — what it does (1-2 sentences), key patterns demonstrated, connection to the concept being taught.

**Produces:**
```json
{
  "code_blocks": [
    {
      "id": "code_01",
      "language": "javascript",
      "filename": "server.js",
      "timestamp_range": "3:45-4:12",
      "source_frames": ["frame_0225.jpg", "frame_0228.jpg", "frame_0231.jpg"],
      "raw_captured": "// lines exactly as seen in video",
      "completed_code": "// full working code with FROM VIDEO and ADDED FOR COMPLETENESS markers",
      "explanation": "This code sets up an Express.js server with...",
      "patterns": ["middleware pattern", "error handling"],
      "completeness": "partial_completed"
    }
  ]
}
```

#### Agent 4: Visual Content Analyst

Processes all non-code visual content: diagrams, slides, UI screenshots, data tables.

**Receives:** all frames tagged `[DIAGRAM]`, `[SLIDE]`, `[UI]`, `[DATA]` from Agent 2's manifest.

**For each frame:**
- **Diagrams**: identify all boxes, labels, arrows, connections, flow direction → produce Mermaid diagram code
- **Slides**: extract title, bullet points, key text
- **UI**: describe the interface, button labels, form fields, layout
- **Data**: extract table contents, chart data, statistics, benchmark results

**Smart Screenshot Selection — decide embed vs. skip:**

**EMBED if it shows:** a slide with text/diagram not fully captured in the transcript; code in an editor (must be BOTH transcribed AND embedded); a UI/dashboard hard to describe in text; an architecture diagram or flowchart; data/statistics/benchmark results.

**SKIP if:** just the presenter talking (face cam only); a near-duplicate of an already-embedded frame; content fully described in the transcript already; blurry or unreadable.

The engine's dedup pass already removed *pixel-identical* neighbours; your job is the semantic judgment it can't make.

**Produces:**
```json
{
  "visuals": [
    {
      "id": "vis_01",
      "type": "DIAGRAM",
      "timestamp": "7:20",
      "source_frame": "/tmp/lfv-abc123/frames/frame_0440.jpg",
      "text_extracted": "All text visible in the screenshot",
      "mermaid_code": "graph LR\n    A[Client] --> B[API]",
      "description": "System architecture showing three-tier design",
      "embed_recommended": true
    }
  ]
}
```

---

### Phase 3 — Agent 5: Document Assembler

Receives outputs from ALL 4 agents and builds the final Word document.

1. **Estimate document size** before generating:
   ```
   ~2KB per text paragraph
   ~50KB per embedded screenshot (compressed JPG)
   ~1KB per code block
   ~0.5KB per table
   Expected size = (paragraphs × 2) + (screenshots × 50) + (code_blocks × 1) + (tables × 0.5) KB
   ```
   Log this estimate so the user knows what to expect.

2. **Read the docx skill** for document creation rules.

3. **Read `${SKILL_DIR}/references/report_structure.md`** for formatting guidelines and docx-js code patterns.

4. **Install docx-js** (local, NOT global): `npm install docx`

5. **Build the document** by creating the adaptive structure from Agent 1's thematic outline; weaving transcript content with Agent 4's visual descriptions; embedding screenshots via `ImageRun` only where `embed_recommended: true`; inserting Agent 3's complete code blocks INLINE where discussed; adding Mermaid diagrams INLINE where relevant; adding key-insight callouts, on-screen boxes, and timestamp links.

#### Document Structure — Adaptive, Not Fixed

**Fixed elements (always include):**

1. **Cover Page** — Title, channel/source, URL, date, duration, topic tags
2. **Table of Contents** — MANUAL TOC (see below)
3. **Executive Summary** — 3-5 key takeaways, audience, prerequisites, difficulty level
4. **[ADAPTIVE CORE CONTENT]** — structure driven by the video's actual content
5. **Quick Reference Tables** — commands, tools, key facts for quick scanning
6. **Source Videos & Resources** — video URLs, transcript provenance (`captions` vs `whisper`), mentioned tools, links

**TOC Implementation — Use MANUAL TOC:**
Do NOT rely on the docx-js `TableOfContents` widget — it creates an empty placeholder that only populates when opened in Microsoft Word and manually updated. Build a MANUAL table of contents by listing section headings as Paragraph elements with page references. This works across Word, Google Docs, and LibreOffice.

```javascript
new Paragraph({
  children: [
    new TextRun({ text: "1. Executive Summary", size: 24 }),
    new TextRun({ text: " ............................. ", size: 24, color: "999999" }),
    new TextRun({ text: "3", size: 24 }),
  ]
})
```

**The Adaptive Core Content** — structure it however makes the most sense for THIS video:
- A tutorial: Setup > Step 1 > Step 2 > Step 3 > Results
- A tips video: Level 1 Tips > Level 2 Tips > Level 3 Tips
- A system design video: Problem > Architecture > Components > Trade-offs
- Multiple videos on the same topic: merge by theme, not by video

**Within each content section, combine everything together:** spoken explanation, embedded screenshots via `ImageRun`, text description of what each screenshot shows, code blocks INLINE, Mermaid diagrams INLINE, data tables INLINE, visual callout boxes INLINE, key-insight callouts, and timestamp references so the reader can jump to the video.

**Embedding Actual Screenshots:**

```javascript
const { ImageRun } = require('docx');
const fs = require('fs');

const imageBuffer = fs.readFileSync('/tmp/lfv-abc123/frames/frame_0225.jpg');

new Paragraph({
  children: [new ImageRun({
    data: imageBuffer,
    transformation: { width: 560, height: 315 },  // 16:9 aspect ratio
    type: 'jpg',  // REQUIRED: must specify image type
  })],
  alignment: AlignmentType.CENTER,
});
```

**IMPORTANT ImageRun notes:**
- The `type` parameter is REQUIRED (`'jpg'` for JPEG, `'png'` for PNG)
- Always read the file as a Buffer with `fs.readFileSync()`
- Max width ~560px to fit within 1-inch margins on US Letter
- Add a caption paragraph below each image with the timestamp
- Frame paths come straight from the engine's report — use them verbatim

### Step 6: Save, Present, and Clean Up

Save the .docx to the user's workspace folder with a descriptive filename:
- Single video: `[VideoTitle]_LearnFromVideo_Notes.docx`
- Multiple videos: `[Topic]_Combined_LearnFromVideo_Notes.docx`

Sanitize the filename (remove special characters, limit to 80 chars).

Present the file link with a brief note about what was captured (e.g., "Created 35-page report covering both videos with 15 embedded screenshots, 6 inline diagrams, 8 code blocks with analysis").

**Clean up:** the engine prints its working directory at the end of each run. Once the document is generated and verified, delete the work dirs (`rm -rf "$WORK"`) — they hold the full downloaded video plus every extracted frame. If the user might ask follow-ups that need more frames, leave them and say so.

### Verification Step

After generating the document, verify quality by reading back 3-5 random sections and checking:
- Each section contains BOTH transcript content AND screenshot descriptions woven together
- Code blocks appear inline where discussed (not in a separate chapter)
- Screenshots have captions with timestamps
- No empty sections exist

Validate the file: `python3 <docx-skill-path>/scripts/office/validate.py output.docx`

---

## Multi-Video Handling

When the user provides multiple video URLs:

1. Run Agent 1 for each video, each into its own `--out-dir`
2. Run Agents 2-4 for each video in parallel
3. Agent 5 merges everything into a single document

**Theme Identification and Merge Strategy:**

1. Extract all H2-level topics from each video's transcript using Agent 1's thematic outline
2. Cluster by keyword overlap (>50% shared keywords = same theme)
3. For overlapping themes: present Video 1's perspective, then Video 2's, then synthesize
4. For unique themes: present in the originating video's section
5. Always include a comparison table when 2+ videos cover the same topic
6. Use [Video N] superscript tags to indicate which video a point comes from

**Document structure for multi-video:** a "Video Sources" table at the beginning listing all videos; content organized by THEME, not by video; cross-references where videos cover the same concept; notes where videos agree, disagree, or differ; combined key takeaways ranked by emphasis across videos.

---

## Handling Edge Cases

- **No captions available**: the engine automatically falls back to Whisper (Groq or OpenAI) if a key is configured. If not, offer to set one up, or ask the user to paste the transcript manually.
- **Whisper request fails**: the error goes to stderr (usually an invalid key or rate limit). Audio over the API's 25 MB cap is chunked automatically, so length alone won't fail it; partial transcripts note dropped chunks on stderr. Retry with `--whisper openai` if Groq failed, or vice versa.
- **Download fails**: yt-dlp's error goes to stderr. If it's login-required or region-locked, tell the user plainly — do not keep retrying.
- **Setup preflight fails**: run `python3 "${WATCH_DIR}/scripts/setup.py"` — it auto-installs on macOS and prints exact commands elsewhere.
- **Very long videos (>1 hour)**: the engine warns about sparse coverage. Run focused `--start`/`--end` passes over the sections that matter rather than one thin full scan. Add a "Reading Guide" after the TOC.
- **Non-English videos**: captions and Whisper both handle multiple languages. Note the language in the document header.
- **Live streams or music videos**: tell the user if the transcript contains no educational material.
- **Playlist URLs**: extract individual video IDs and process each one.
- **Partially inaudible/garbled transcript**: mark unclear segments with "[unclear at timestamp]" rather than guessing. For Whisper transcripts especially, flag uncertain proper nouns and technical terms.
- **No audio stream**: the engine reports this and proceeds frames-only.
- **`npm install -g docx` fails**: use a local install (`npm install docx` in the working directory).
- **Read-only skill directory**: skill files may be mounted read-only. Never write into `$SKILL_DIR` — all engine output goes to `--out-dir`.
- **Local video files**: pass the path directly as `<SOURCE>`. No captions exist for local files, so the transcript comes from Whisper — a key is effectively required for local video.

---

## Critical Implementation Notes (Lessons Learned)

### Engine usage
- **Never hand-roll `yt-dlp`/`ffmpeg` loops.** Every download and frame extraction goes through `watch.py`. It handles fallbacks, dedup, 2 fps rate capping, absolute-timestamp alignment, and the 1998px height clamp required for `Read` compatibility.
- **Reuse `--out-dir` across passes** so the video downloads exactly once. Point follow-up passes at the local file in `$WORK/download/`.
- **`--resolution 1024` for code**, 512 for everything else. 512px makes code in an editor unreadable; 1024px roughly quadruples image tokens.
- **`--timestamps` is how you capture deictic moments.** Scene detection misses "as you can see" because pointing at a static slide is a low-visual-change event. Cue frames are pinned against the cap.
- **`--no-dedup` for typing sequences.** Dedup helps everywhere except code being typed, where consecutive frames are near-identical by pixel delta yet each carries new lines.
- Frame timestamps are always **absolute source time**, even in focused mode — safe to align directly against the transcript.

### Document generation
- Use `npm install docx` (local, not global) to avoid permission errors.
- `ImageRun` requires the `type` parameter (`'jpg'` or `'png'`) — mandatory.
- Use a MANUAL TOC instead of the `TableOfContents` widget for cross-platform compatibility.
- Use `ShadingType.CLEAR`, not `ShadingType.SOLID` (SOLID creates black backgrounds).
- Set BOTH `columnWidths` on Table AND `width` on each TableCell.
- Use `LevelFormat.BULLET` for bullet lists (never unicode bullet characters).
- Use `WidthType.DXA`, not `WidthType.PERCENTAGE`, for table widths.

### Parallel agent instructions
For 20+ frames, launch 3 agents in parallel:
- Agent A: frames 0 to N/3
- Agent B: frames N/3 to 2N/3
- Agent C: frames 2N/3 to N

Each returns `{ timestamp, content_type, text, code, diagrams }`.

Read frames in a single message with parallel `Read` calls so you see them together and in order.

---

## Token Budget

Frames dominate cost. Order of magnitude:
- 80 frames at 512px wide ≈ 50-80k image tokens depending on aspect ratio
- At 1024px (this skill's Detailed Mode default) that is roughly 4× higher
- The transcript is cheap — a few thousand tokens for a 10-minute video

Before an expensive run — a long video, or `--detail token-burner` — tell the user what it will cost and offer a focused alternative. If you already extracted frames this session and the user asks a follow-up, do **not** re-run the engine; answer from what you have.

---

## Quality Standards

The document should be thorough enough that someone who reads it gets 90%+ of the value of watching the video:
- No skipping over "minor" points — capture everything
- Preserve the logical flow and sequence of the presentation
- Make implicit visual information explicit in text
- Include timestamps throughout so the reader can jump to specific video moments
- Embed actual screenshots at key moments via `ImageRun` (high-value frames only, skip face-cam-only)
- Recreate all diagrams, workflows, and architecture as Mermaid diagrams — INLINE where discussed
- Format all code as proper code blocks with language identification — INLINE where discussed
- Complete partial code to working examples with clear FROM VIDEO / ADDED FOR COMPLETENESS markers
- Visual callout boxes for on-screen content — INLINE where discussed
- The report should feel like one person explaining the complete video to another
- A reader should NEVER need to flip to a different section to see "what was on screen at this point"

---

## Evaluation and Self-Improvement

This skill includes an automated evaluation framework. See `${SKILL_DIR}/eval/eval.json` for binary assertions and `${SKILL_DIR}/references/self_improve_prompt.md` for the autonomous improvement loop.

**Layer 1 — Skill Activation (Description):** tests whether Claude triggers the skill for the right prompts.
Should trigger: "create notes from this video", "learn from this video", "summarize this lecture".
Should NOT trigger: "summarize this PDF", "write a report about AI", "take notes from this meeting".

Note the boundary with the bundled `/watch` skill: `/watch` answers *questions* about a video in chat; `learn-from-video` produces a *document*. If the user just wants to know what happens at 2:30, that's `/watch`.

**Layer 2 — Output Quality (eval.json):** 30 binary assertions across 3 test types (short tutorial, code-heavy video, multi-video).

---

## Security & Permissions

**What this skill does:**
- Runs `yt-dlp` locally to download video and pull native captions (public data only; requests go directly to the host the URL points at)
- Runs `ffmpeg` / `ffprobe` locally to extract frames and, when Whisper is needed, a mono 16 kHz audio clip
- Sends the extracted **audio only** to Groq's or OpenAI's Whisper API when native captions are missing and a key is configured
- Runs `npm install docx` in the working directory to generate the Word document
- Writes the downloaded video, frames, audio, intermediate transcript, and the final .docx to a working directory
- Reads / creates `~/.config/watch/.env` (mode `0600`) for the Whisper API key(s)

**What this skill does NOT do:**
- Does not upload the video itself to any API — only extracted audio, only when captions are missing
- Does not access any platform account (no login, no session cookies, no posting)
- Does not share API keys between providers
- Does not log, cache, or write API keys to stdout, stderr, or output files

**Bundled scripts:** `${SKILL_DIR}/scripts/fetch_transcript.py` (legacy YouTube-only transcript fallback). The ingestion engine lives in the sibling `watch` skill: `scripts/watch.py`, `download.py`, `frames.py`, `transcribe.py`, `whisper.py`, `setup.py`, `config.py`.

Review scripts before first use to verify behavior.

---

## Attribution and Legal

Every generated document includes:
- Header: Video title | "learnFromVideo Notes"
- Footer: "Notes generated from video for personal learning use | Page X"
- Cover page: full video URL, channel/creator name, creation date
- Final page note: "For the complete experience, watch the original video at [URL]. All content credit to [channel/creator name]."

The ingestion engine bundled at `skills/watch/` is from [bradautomates/claude-video](https://github.com/bradautomates/claude-video), MIT licensed. See the repository LICENSE.
