---
name: learn-from-video
description: "Create comprehensive, report-style learning notes from any video — called 'learnFromVideo'. Use this skill whenever the user shares a video URL or file and wants notes, a summary, a study guide, or learning material from it. Also triggers when the user says 'learn from this video', 'learnFromVideo', 'create notes from this video', 'make notes for this video', 'I watched this video and need notes', 'summarize this video in detail', 'take notes from this lecture', 'notes from this tutorial', 'I don't have time to watch this video', or shares one or more video URLs/files and asks for any kind of written output about the content. This skill handles single videos and multiple videos on the same topic, producing a professional Word document (.docx) report with full detail — not a brief summary, but a thorough report capturing everything spoken AND shown in the video, including diagrams, workflows, code, and architecture recreated as Mermaid flowcharts."
---

# learnFromVideo — v3.0

Create professional, report-style learning notes from any video. The user provides one or more video URLs or local video files, and you produce a comprehensive Word document that captures EVERYTHING — what was spoken AND what was shown on screen — combined together so the reader understands the complete picture as if they watched the video themselves.

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

## Speed/Quality Modes

This skill supports two modes. Default is **Detailed Mode** unless the user explicitly requests fast/quick.

### Fast Mode
Triggers when user says "quick notes", "fast summary", "brief notes", or "just the highlights".

- Download at 480p
- Screenshot interval: 45 seconds (fixed, no adaptive)
- Single-pass code extraction (no gap detection or multi-frame merging)
- Skip Mermaid diagram recreation — describe diagrams in text only
- Sequential processing (no parallel agents)
- Target: 3-5 minutes per video

### Detailed Mode (Default)
Triggers for all other requests, or when user says "detailed", "comprehensive", or "full notes".

- Download at 720p for code readability
- Adaptive screenshot intervals (3-45 seconds based on content type)
- Multi-pass code extraction with gap filling and fragment merging
- Full Mermaid diagram recreation
- Parallel multi-agent pipeline for maximum quality
- Target: 8-15 minutes per video

---

## Multi-Agent Parallel Architecture

This skill uses a 5-agent pipeline organized in 3 phases. Agents 2, 3, and 4 run in PARALLEL after Agent 1 completes.

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

### Phase 1 — Agent 1: Transcript Analyst (runs first, no video download needed)

This agent runs FIRST because everything else depends on its timestamp analysis.

**Steps:**
1. Set PATH for yt-dlp:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

2. Run the bundled transcript fetcher:
   ```bash
   pip install youtube-transcript-api --break-system-packages 2>/dev/null
   python <skill-path>/scripts/fetch_transcript.py "VIDEO_URL"
   ```
   If the skill files are not in the expected path, check these locations:
   - The skill's installed directory (check the path shown when the skill loaded)
   - `/tmp/learn-from-video/scripts/fetch_transcript.py`

3. If the script fails (video has no captions, is private, etc.), tell the user and ask them to paste the transcript manually. Then proceed with the pasted text.

4. **Analyze the ENTIRE transcript** and identify every important timestamp. Tag each with a content type:
   - `[CODE timestamp_start-timestamp_end]` — code shown in editor/terminal
   - `[DIAGRAM timestamp]` — architecture, flowchart, or diagram shown
   - `[SLIDE timestamp]` — slide with text/bullet points
   - `[UI timestamp]` — app interface, dashboard, website shown
   - `[TERMINAL timestamp]` — command line output, running commands
   - `[DATA timestamp]` — tables, charts, statistics, benchmarks
   - `[KEY_CONCEPT timestamp]` — important concept being explained with visual

5. **Signal phrases to detect:**
   - "as you can see", "on the screen", "this slide shows", "looking at this", "let me show you"
   - "here we have", "over here", "right here", "on the left/right"
   - "this diagram", "this flowchart", "this architecture"
   - "let me write some code", "in our editor", "the code looks like"
   - "let me run this", "the output is", "you can see the result"
   - "the flow goes from X to Y", "the components are", "this connects to"
   - "this table shows", "the comparison", "the benchmark"
   - Any mention of file names, IDE, terminal, console, specific numbers being shown

6. **Produce a structured JSON output:**
   ```json
   {
     "video_id": "abc123",
     "title": "Video Title",
     "duration": "12:34",
     "thematic_outline": [
       { "theme": "Introduction", "start": "0:00", "end": "1:30" },
       { "theme": "Core Concept", "start": "1:30", "end": "5:00" }
     ],
     "key_timestamps": [
       { "time": "3:45", "seconds": 225, "type": "CODE", "description": "Shows Express route handler", "duration_hint": "3:45-4:12" },
       { "time": "7:20", "seconds": 440, "type": "DIAGRAM", "description": "System architecture overview" }
     ],
     "transcript_text": "full transcript with timestamps..."
   }
   ```

For multiple videos, run for each URL and process all transcripts.

---

### Phase 2 — Runs in PARALLEL after Agent 1 completes

#### Agent 2: Screenshot Extractor

Downloads the video and extracts frames based on Agent 1's timestamp analysis.

**Steps:**

1. **Set PATH and install yt-dlp:**
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   pip install yt-dlp --break-system-packages 2>/dev/null
   ```

2. **Download the video at 720p** (critical for code readability):
   ```bash
   yt-dlp -f "best[height<=720][ext=mp4]" -o "/tmp/lfv-screenshots/video.mp4" "VIDEO_URL"
   ```

   **Fallback chain if download fails:**
   1. `yt-dlp -f "best[height<=720][ext=mp4]"` (default — good for code readability)
   2. `yt-dlp -f "best[height<=480][ext=mp4]"` (fallback if 720p too large or unavailable)
   3. `python -m yt_dlp -f "best[height<=720][ext=mp4]"` (fallback if yt-dlp binary not in PATH)
   4. Fall back to transcript-only mode — inform user

   For **local video files**, skip download and use the file directly.

3. **Extract frames using ADAPTIVE intervals** based on Agent 1's content type tags:

   **For CODE timestamps**: every 3-5 seconds within the code window
   ```bash
   # Example: code shown 3:45-4:12, extract at 3s intervals
   for i in $(seq 225 3 252); do
     ffmpeg -ss $i -i /tmp/lfv-screenshots/video.mp4 -frames:v 1 -q:v 2 \
       /tmp/lfv-screenshots/code_$(printf "%04d" $i).jpg 2>/dev/null
   done
   ```

   **For DIAGRAM/SLIDE timestamps**: one frame at the start + one at the end
   ```bash
   ffmpeg -ss $START -i /tmp/lfv-screenshots/video.mp4 -frames:v 1 -q:v 2 \
     /tmp/lfv-screenshots/diagram_$(printf "%04d" $START).jpg 2>/dev/null
   ```

   **For UI/DEMO timestamps**: every 10-15 seconds
   
   **For normal talking sections** (no visual content tagged): every 30-45 seconds as safety net

   **Regular interval safety net**: Also extract at 30-second intervals throughout, to catch anything Agent 1 missed.

4. **Deduplicate**: Compare consecutive frames and skip near-identical ones (same slide shown for 2+ minutes).

5. **Delete the video file** after extraction to save disk space.

6. **Produce a manifest JSON:**
   ```json
   {
     "video_id": "abc123",
     "download_quality": "720p",
     "total_frames": 45,
     "frames": [
       { "filename": "frame_0225.jpg", "timestamp": "3:45", "seconds": 225, "type": "CODE", "source": "targeted" },
       { "filename": "frame_0250.jpg", "timestamp": "4:10", "seconds": 250, "type": "CODE", "source": "interval" }
     ],
     "deduplicated": 8,
     "video_deleted": true
   }
   ```

#### Agent 3: Code Specialist (THE KEY AGENT)

This agent specializes in extracting, completing, and explaining code from screenshots. This is one of the most valuable features of the skill — readers get working code they can actually use.

**Receives:** All frames tagged as `[CODE]` or `[TERMINAL]` from Agent 2's manifest, plus the transcript context from Agent 1.

**Multi-Pass Extraction Process:**

1. **First Pass — Extract**: Read each code screenshot and transcribe EVERY visible line of code exactly as shown.
   - Note the language, filename (if visible in tab/title bar), and context
   - Note what's visible vs. cut off (top/bottom cropped, scrolled partially)
   - Note if code is mid-typing or appears incomplete

2. **Gap Detection**: If code appears cut off or partially scrolled:
   - Request additional frames from nearby timestamps (±2-5 seconds)
   - Check if Agent 2 captured frames in the code window at 3-second intervals
   - Look for overlapping lines between consecutive frames

3. **Second Pass — Combine**: Merge code fragments from multiple screenshots of the same code block into one complete block.
   - Remove duplicated lines from overlapping frames
   - Maintain correct ordering based on timestamps
   - Note any gaps that couldn't be filled

4. **Third Pass — Complete**: Using the transcript context (what the speaker was explaining) AND the agent's own knowledge, complete any partial code to a working example:
   - Add missing imports and module declarations
   - Add missing function signatures, closing braces, and boilerplate
   - Add error handling if the speaker mentioned it but didn't show it
   - Fix obvious typos from low-resolution capture

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

6. **Add explanations**: For each significant code block:
   - What the code does (1-2 sentences)
   - Key patterns being demonstrated
   - Connection to the concept being taught in the transcript

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

**Receives:** All frames tagged as `[DIAGRAM]`, `[SLIDE]`, `[UI]`, `[DATA]` from Agent 2's manifest.

**For each screenshot:**

- **Diagrams**: Identify all boxes, labels, arrows, connections, flow direction → produce Mermaid diagram code
- **Slides**: Extract title, bullet points, key text
- **UI**: Describe the interface, button labels, form fields, layout
- **Data**: Extract table contents, chart data, statistics, benchmark results

**Smart Screenshot Selection — decide embed vs. skip:**

**EMBED a screenshot if it shows:**
- A slide with text/diagram not fully captured in transcript
- Code in an editor (must be BOTH transcribed AND embedded)
- A UI/dashboard that's hard to describe in text alone
- An architecture diagram or flowchart
- Data/statistics/benchmark results

**SKIP embedding if:**
- Just the presenter talking (face cam only) — no visual content value
- Near-duplicate of a previously embedded frame
- Content is fully described in the transcript text already
- Blurry or unreadable frame

**Produces:**
```json
{
  "visuals": [
    {
      "id": "vis_01",
      "type": "DIAGRAM",
      "timestamp": "7:20",
      "source_frame": "frame_0440.jpg",
      "text_extracted": "All text visible in the screenshot",
      "mermaid_code": "graph LR\n    A[Client] --> B[API]",
      "description": "System architecture showing three-tier design",
      "embed_recommended": true
    },
    {
      "id": "vis_02",
      "type": "SLIDE",
      "timestamp": "2:00",
      "source_frame": "frame_0120.jpg",
      "text_extracted": "Title: Key Concepts\n- Point 1\n- Point 2",
      "embed_recommended": true
    }
  ]
}
```

---

### Phase 3 — Agent 5: Document Assembler (runs after ALL Phase 2 agents complete)

Receives outputs from ALL 4 agents and builds the final Word document.

**Steps:**

1. **Estimate document size** before generating:
   ```
   ~2KB per text paragraph
   ~50KB per embedded screenshot (compressed JPG)
   ~1KB per code block
   ~0.5KB per table
   Expected size = (paragraphs × 2) + (screenshots × 50) + (code_blocks × 1) + (tables × 0.5) KB
   ```
   Log this estimate so the user knows what to expect.

2. **Read the docx skill** for document creation rules:
   ```
   Read the docx SKILL.md for formatting instructions
   ```

3. **Read `references/report_structure.md`** for formatting guidelines and docx-js code patterns.

4. **Install docx-js** (local, NOT global):
   ```bash
   npm install docx
   ```

5. **Build the complete Word document** by:
   - Creating the adaptive structure based on Agent 1's thematic outline
   - Weaving transcript content with visual descriptions from Agent 4
   - Embedding actual screenshots via ImageRun at key moments (only where Agent 4 marked `embed_recommended: true`)
   - Inserting complete code blocks from Agent 3 INLINE where discussed
   - Adding Mermaid diagrams from Agent 4 INLINE where relevant
   - Adding key insight callouts, on-screen boxes, timestamp links

#### Document Structure — Adaptive, Not Fixed

**Fixed elements (always include):**

1. **Cover Page** — Title, channel/source, URL, date, duration, topic tags
2. **Table of Contents** — Use a MANUAL TOC (see TOC notes below)
3. **Executive Summary** — 3-5 key takeaways, audience, prerequisites, difficulty level
4. **[ADAPTIVE CORE CONTENT]** — Structure driven by the video's actual content
5. **Quick Reference Tables** — Commands, tools, key facts for quick scanning
6. **Source Videos & Resources** — Video URLs, mentioned tools, links

**TOC Implementation — Use MANUAL TOC:**
Do NOT rely on the docx-js `TableOfContents` widget — it creates an empty placeholder that only populates when opened in Microsoft Word and manually updated. Instead, create a MANUAL table of contents by listing the section headings as Paragraph elements with page references. This works reliably across all Word processors (Word, Google Docs, LibreOffice).

```javascript
// Manual TOC entry example
new Paragraph({
  children: [
    new TextRun({ text: "1. Executive Summary", size: 24 }),
    new TextRun({ text: " ............................. ", size: 24, color: "999999" }),
    new TextRun({ text: "3", size: 24 }),
  ]
})
```

**The Adaptive Core Content:**

Structure it however makes the most sense for THIS video:
- A tutorial video might flow as: Setup > Step 1 > Step 2 > Step 3 > Results
- A tips video might flow as: Level 1 Tips > Level 2 Tips > Level 3 Tips
- A system design video might flow as: Problem > Architecture > Components > Trade-offs
- Multiple videos on the same topic should merge by theme, not by video

**Within each content section, combine everything together:**
- Spoken explanation (from transcript)
- Actual embedded screenshots via ImageRun where key visuals were captured
- Text description of what the screenshot shows
- Code blocks INLINE where code was shown/discussed (captured + completed from Agent 3)
- Mermaid diagrams INLINE where architecture/workflows were shown (from Agent 4)
- Data tables INLINE where comparisons/stats were shown
- Visual callout boxes INLINE for important on-screen content
- Key insight callouts for critical points
- Timestamp references so the reader can jump to the video

**Embedding Actual Screenshots:**
Use `ImageRun` from docx-js to embed screenshots directly in the document:

```javascript
const { ImageRun } = require('docx');
const fs = require('fs');

// Read the image file
const imageBuffer = fs.readFileSync('/tmp/lfv-screenshots/frame_0125.jpg');

// Create an image paragraph
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
- The `type` parameter is REQUIRED (use 'jpg' for JPEG, 'png' for PNG)
- Always read the file as a Buffer with `fs.readFileSync()`
- Max width ~560px to fit within 1-inch margins on US Letter
- Add a caption paragraph below each image with the timestamp

### Step 6: Save and Present

Save the generated .docx file to the user's workspace folder. Use a descriptive filename:
- Single video: `[VideoTitle]_LearnFromVideo_Notes.docx`
- Multiple videos: `[Topic]_Combined_LearnFromVideo_Notes.docx`

Sanitize the filename (remove special characters, limit to 80 chars).

Present the file link to the user with a brief note about what was captured (e.g., "Created 35-page report covering both videos with 15 embedded screenshots, 6 inline diagrams, 8 code blocks with analysis").

### Verification Step

After generating the document, verify quality by reading back 3-5 random sections and checking:
- Each section contains BOTH transcript content AND screenshot descriptions woven together
- Code blocks appear inline where discussed (not in a separate chapter)
- Screenshots have captions with timestamps
- No empty sections exist

---

## Multi-Video Handling

When the user provides multiple video URLs:

1. Run Agent 1 (Transcript Analyst) for each video
2. Run Agents 2-4 for each video in parallel
3. Agent 5 merges everything into a single document

**Theme Identification and Merge Strategy:**

1. Extract all H2-level topics from each video's transcript using Agent 1's thematic outline
2. Cluster by keyword overlap (>50% shared keywords = same theme)
3. For overlapping themes: present Video 1's perspective, then Video 2's, then synthesize
4. For unique themes: present in the originating video's section
5. Always include a comparison table when 2+ videos cover the same topic
6. Use [Video N] superscript tags to indicate which video a point comes from

**Document structure for multi-video:**
- Has a "Video Sources" table at the beginning listing all videos
- Organizes content by THEME, not by video — merge overlapping content
- Cross-references between videos where they cover the same concept
- Notes where videos agree, disagree, or offer different perspectives
- Has combined key takeaways ranked by emphasis across videos

---

## Handling Edge Cases

- **No captions available**: Ask the user to paste the transcript manually. Guide them: "Click the three dots below the video > Open transcript > Select All > Copy"
- **yt-dlp download fails**: Follow the fallback chain (720p → 480p → python -m yt_dlp → transcript-only mode)
- **yt-dlp not in PATH**: Always run `export PATH="$HOME/.local/bin:$PATH"` before any yt-dlp command
- **Very large video files**: Start with 720p. If disk space is an issue, fall back to 480p. Always delete video after frame extraction.
- **Non-English videos**: The transcript API supports multiple languages. Note the language in the document header.
- **Very long videos (>1 hour)**: Still capture everything. Increase safety-net interval to 45 seconds. Add a "Reading Guide" after the TOC.
- **Live streams or music videos**: Let the user know if the transcript doesn't contain educational material.
- **Playlist URLs**: Extract individual video IDs and process each one.
- **Partially inaudible/garbled transcript**: Mark unclear segments with "[unclear at timestamp]" rather than guessing.
- **npm install -g docx fails**: Use local install (`npm install docx` in working directory) instead of global install. This is the recommended approach.
- **Read-only skill directory**: Skill files may be mounted read-only. Always copy scripts to a writable location (e.g., `/tmp/learn-from-video/`) before modifying.
- **Local video files**: Skip the yt-dlp download step entirely. Use the local file path directly with ffmpeg for frame extraction. Transcript must be provided by the user or extracted via speech-to-text.

---

## Critical Implementation Notes (Lessons Learned)

These notes come from real-world experience running this skill:

### PATH and Environment
- **yt-dlp installs to `~/.local/bin/`** — ALWAYS run `export PATH="$HOME/.local/bin:$PATH"` before any yt-dlp command
- **Skill directory is read-only (EROFS)** — must copy scripts to `/tmp/` for modification
- Use `--break-system-packages` flag with pip installs to avoid venv errors

### Screenshot Capture
- **720p is the default quality** — critical for code readability. 360p/worst quality makes code blurry and unreadable.
- **yt-dlp + ffmpeg is the PRIMARY method** for capturing screenshots. Reliable and works in all environments.
- Use `ffmpeg -ss TIMESTAMP -i video.mp4 -frames:v 1 -q:v 2 output.jpg` for individual frames.
- Use ADAPTIVE intervals based on content type (3s for code, 30-45s for talking).
- ALWAYS combine targeted key-moment captures with regular interval safety net.
- Delete the video file after extracting all frames to free disk space.

### Code Extraction from Screenshots
- Code shown in videos is often partial — use the multi-pass extraction process (Agent 3).
- 720p vs 360p makes a MASSIVE difference for code readability.
- Clearly mark original code vs. added completions with `FROM VIDEO` and `ADDED FOR COMPLETENESS` markers.
- Use agents to analyze code blocks and add explanations.
- Represent code inline in the document, right where it is discussed.
- Merge code from multiple screenshots when the presenter scrolls through code.

### Document Generation
- Use `npm install docx` (local, not global) to avoid permission errors.
- ImageRun requires the `type` parameter ('jpg' or 'png') — this is mandatory.
- For Table of Contents, use a MANUAL TOC (list of headings as Paragraphs) instead of the `TableOfContents` widget for cross-platform compatibility.
- Use `ShadingType.CLEAR` not `ShadingType.SOLID` for cell shading (SOLID creates black backgrounds).
- Set BOTH `columnWidths` on Table AND `width` on each TableCell.
- Use `LevelFormat.BULLET` for bullet lists (never unicode bullet characters).
- Use `WidthType.DXA` not `WidthType.PERCENTAGE` for table widths.
- Validate the document with `python <docx-skill-path>/scripts/office/validate.py output.docx`.

### Parallel Agent Instructions
For 20+ screenshots, launch 3 agents in parallel:
- Agent A: Analyze frames 0 to N/3
- Agent B: Analyze frames N/3 to 2N/3
- Agent C: Analyze frames 2N/3 to N
Each agent returns: `{ timestamp, content_type, text, code, diagrams }`

---

## Quality Standards

The document should be thorough enough that someone who reads it gets 90%+ of the value of watching the video:
- No skipping over "minor" points — capture everything
- Preserve the logical flow and sequence of the presentation
- Make implicit visual information explicit in text
- Include timestamps throughout so the reader can jump to specific video moments
- Embed actual screenshots at key moments via ImageRun (only high-value frames, skip face-cam-only)
- Recreate all diagrams, workflows, and architecture as Mermaid diagrams — INLINE where discussed
- Format all code as proper code blocks with language identification — INLINE where discussed
- Complete partial code to working examples with clear FROM VIDEO / ADDED FOR COMPLETENESS markers
- Visual callout boxes for on-screen content — INLINE where discussed
- The report should feel like one person explaining the complete video to another
- A reader should NEVER need to flip to a different section to see "what was on screen at this point"

---

## Evaluation and Self-Improvement

This skill includes an automated evaluation framework. See `eval/eval.json` for binary assertions and `references/self_improve_prompt.md` for the autonomous improvement loop.

### Two Layers of Improvement

**Layer 1 — Skill Activation (Description):**
Tests whether Claude triggers the skill for the correct prompts and doesn't trigger for wrong ones.

Should trigger: "create notes from this video", "learn from this video", "summarize this lecture"
Should NOT trigger: "summarize this PDF", "write a report about AI", "take notes from this meeting"

**Layer 2 — Output Quality (eval.json):**
30 binary assertions across 3 test types (short tutorial, code-heavy video, multi-video).
Run the self-improvement loop from `references/self_improve_prompt.md` to autonomously improve this skill.

---

## Attribution and Legal

Every document includes:
- Header: Video title | "learnFromVideo Notes"
- Footer: "Notes generated from video for personal learning use | Page X"
- Cover page: Full video URL, channel/creator name, creation date
- Final page note: "For the complete experience, watch the original video at [URL]. All content credit to [channel/creator name]."
