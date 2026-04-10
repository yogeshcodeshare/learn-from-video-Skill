---
name: learn-from-video
description: "Create comprehensive, report-style learning notes from YouTube videos — called 'learnFromVideo'. Use this skill whenever the user shares a YouTube video link and wants notes, a summary, a study guide, or learning material from it. Also triggers when the user says 'learn from this video', 'learnFromVideo', 'create notes from YouTube', 'make notes for this video', 'I watched this video and need notes', 'summarize this YouTube video in detail', 'take notes from this lecture', 'notes from this tutorial', 'I don't have time to watch this video', or shares one or more YouTube URLs and asks for any kind of written output about the content. This skill handles single videos and multiple videos on the same topic, producing a professional Word document (.docx) report with full detail — not a brief summary, but a thorough report capturing everything spoken AND shown in the video, including diagrams, workflows, code, and architecture recreated as Mermaid flowcharts."
---

# learnFromVideo

Create professional, report-style learning notes from YouTube videos. The user provides one or more YouTube URLs, and you produce a comprehensive Word document that captures EVERYTHING — what was spoken AND what was shown on screen — combined together so the reader understands the complete picture as if they watched the video themselves.

## Why This Skill Exists

When people find great learning videos on YouTube, they often don't have time to watch them fully. A transcript alone doesn't capture the full picture — it misses diagrams, architecture flows, code shown on screen, and visual explanations. This skill bridges that gap by combining the transcript WITH actual screenshots from the video to produce notes so thorough that reading them is as good as watching the video.

## Core Philosophy: Combined, Not Separated

**IMPORTANT**: This skill does NOT follow a rigid chapter-based template. Every video is different. The report should read like a natural, flowing document where:

- What was SAID and what was SHOWN are woven together in the same paragraphs and sections
- Diagrams, code, and visual content appear INLINE exactly where they are discussed — NOT in a separate "Diagrams" or "Visual References" chapter
- The structure follows the video's natural flow, not a fixed template
- A reader who reads the report should understand BOTH what the speaker said AND what was on screen at that moment
- Code shown on screen is CAPTURED, COMPLETED, and EXPLAINED inline with additional context

Think of it this way: if the speaker says "here's how the architecture works" and shows a diagram, the report should explain what they said AND show the reconstructed diagram RIGHT THERE — not 20 pages later in a "diagrams chapter."

## Workflow

### Step 1: Extract the Transcript (ALWAYS DO THIS FIRST)

The transcript is your primary source of truth. It tells you WHAT was discussed and WHEN — which drives all subsequent steps including screenshot timing.

For each YouTube URL the user provides, run the bundled transcript fetcher:

```bash
pip install youtube-transcript-api --break-system-packages  # if not already installed
python <skill-path>/scripts/fetch_transcript.py "YOUTUBE_URL"
```

If the skill files are not in the expected path, check these locations:
- The skill's installed directory (check the path shown when the skill loaded)
- `/tmp/learn-from-video/scripts/fetch_transcript.py`

This script:
- Accepts a full YouTube URL or just a video ID
- Fetches the transcript with timestamps using the `youtube_transcript_api` library
- Auto-detects chapter breaks from the transcript
- Saves the raw transcript to a JSON file and a formatted text file
- Returns the path to the output files

If the script fails (video has no captions, is private, etc.), tell the user and ask them to paste the transcript manually (from YouTube's "Show Transcript" button, or browser extensions like Glasp or NoteGPT). Then proceed with the pasted text.

For multiple videos, run the script for each URL and process all transcripts together.

#### 1b. Analyze the Transcript for Key Visual Timestamps

After fetching the transcript, scan it BEFORE taking any screenshots. Identify:

**Signal phrases that indicate important visual content:**
- "as you can see", "on the screen", "this slide shows", "looking at this", "let me show you"
- "here we have", "over here", "right here", "on the left/right"
- "this diagram", "this flowchart", "this architecture"
- "let me write some code", "in our editor", "the code looks like"
- "let me run this", "the output is", "you can see the result"
- "the flow goes from X to Y", "the components are", "this connects to"
- "this table shows", "the comparison", "the benchmark"
- Any mention of file names, IDE, terminal, console, specific numbers being shown

Build a list of KEY TIMESTAMPS where visual content is likely being shown. These will be used for targeted screenshots in Step 2.

### Step 2: Capture Visual Content with Screenshots (yt-dlp + ffmpeg)

This is the critical step that makes these notes far more valuable than a plain transcript. You MUST capture what is SHOWN on screen — not just what is said.

#### 2a. Download the Video with yt-dlp

Use yt-dlp to download the video at the lowest quality sufficient for readable screenshots:

```bash
pip install yt-dlp --break-system-packages  # if not already installed

# Download lowest quality mp4 (saves time and disk space)
yt-dlp -f "worst[ext=mp4]" -o "/tmp/lfv-screenshots/video.mp4" "YOUTUBE_URL"

# If worst quality is too low resolution, use:
yt-dlp -f "best[height<=480][ext=mp4]" -o "/tmp/lfv-screenshots/video.mp4" "YOUTUBE_URL"
```

#### 2b. Extract Frames with ffmpeg

Use ffmpeg to extract individual frames at specific timestamps. Use BOTH approaches together:

**Approach 1: Regular Interval Screenshots (every 20-30 seconds)**
This ensures nothing visual is missed:

```bash
# Extract a frame every 25 seconds throughout the entire video
# Use -q:v 2 for high quality JPEG output
for i in $(seq 0 25 TOTAL_SECONDS); do
  timestamp=$(printf "%02d:%02d:%02d" $((i/3600)) $(((i%3600)/60)) $((i%60)))
  ffmpeg -ss $i -i /tmp/lfv-screenshots/video.mp4 -frames:v 1 -q:v 2 \
    /tmp/lfv-screenshots/frame_$(printf "%04d" $i).jpg 2>/dev/null
done
```

**Approach 2: Targeted Screenshots at Key Visual Moments**
Using the timestamps identified in Step 1b, extract frames at those exact moments:

```bash
# For each key timestamp identified from transcript analysis
ffmpeg -ss SECONDS -i /tmp/lfv-screenshots/video.mp4 -frames:v 1 -q:v 2 \
  /tmp/lfv-screenshots/key_LABEL.jpg
```

#### 2c. Read and Analyze Every Screenshot

This is critical — you must actually READ each captured frame:

1. Use the Read tool to view each extracted JPEG image
2. For every screenshot, identify and extract:
   - **Slide text**: Title, bullet points, any text on the slide
   - **Diagrams/Architecture**: All boxes, labels, arrows, connections, and flow directions
   - **Code**: Every line of code visible in an editor or terminal — capture it EXACTLY as shown
   - **Terminal/Console output**: Command prompts, output text, error messages
   - **UI elements**: What the app or website looks like, button labels, form fields
   - **URLs/Links**: Any web addresses shown on screen
   - **Data/Numbers**: Tables, charts, statistics, benchmarks visible on screen
   - **Annotations/Highlights**: Any text the presenter has highlighted or annotated

**Use agents for parallel analysis**: When there are many screenshots (20+), launch multiple agents to analyze groups of screenshots in parallel. Each agent should return structured data about what it found in each frame.

### Step 3: Analyze and Extract Code from Screenshots

This step is specifically for code content — one of the most valuable parts of technical videos.

#### 3a. Capture Code Exactly as Shown
When a screenshot shows code in an editor, terminal, or slide:
- Transcribe every visible line of code EXACTLY as shown
- Note the language, file name (if visible), and context
- Note if the code is partial (scrolled, cropped, or mid-typing)

#### 3b. Complete Partial Code
Videos often show code snippets that are incomplete (only showing the key part). For each code snippet:
- If the code is partial, COMPLETE it to a working example
- Add proper imports, function signatures, error handling
- Clearly mark which parts are from the video vs. added for completeness:
  ```
  // === FROM VIDEO [timestamp] ===
  const agent = new Agent(config);
  // === ADDED FOR COMPLETENESS ===
  import { Agent } from './agent';
  const config = { model: 'claude-3', maxTokens: 1024 };
  ```

#### 3c. Add Analysis and Explanation
For each significant code block, use an agent to:
- Explain what the code does line by line
- Identify patterns and best practices being demonstrated
- Note any potential improvements or alternatives
- Add inline comments explaining non-obvious logic
- Connect the code to the broader concept being taught

#### 3d. Represent Code in the Report
Code should appear INLINE in the report right where it is discussed, formatted as proper code blocks with:
- Language label (JavaScript, Python, bash, etc.)
- File name or context label if known
- The captured code (with completion markers if extended)
- Brief inline comments on key lines

### Step 4: Build the Combined Content and Generate the Document

Now combine the transcript AND the visual captures into a unified understanding.

#### 4a. Understand the Video's Natural Structure
- Read through the entire transcript
- Review all screenshots in sequence
- Identify the video's natural flow: What topics does it cover? In what order? How do they connect?
- Map out a logical structure that follows the video but groups related ideas together
- For multiple videos on the same topic: identify overlapping themes and merge them

#### 4b. Combine Spoken + Visual for Each Point
For every key point or concept in the video, merge together:
- What the speaker SAID about it (from transcript)
- What was SHOWN on screen at that moment (from screenshots)
- Any code, diagrams, or data that was visible
- Code analysis and completions from Step 3

This combined information becomes ONE unified explanation in the report.

#### 4c. Generate the Word Document

Read the docx skill first:
```
Read the docx SKILL.md for formatting instructions
```

Then use `docx-js` (`npm install docx` — use local install, NOT global) to create a professional Word document. Read `references/report_structure.md` for formatting guidelines and docx-js code patterns.

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
    transformation: { width: 580, height: 326 },  // Adjust to maintain aspect ratio
    type: 'jpg',  // REQUIRED: must specify image type
  })],
  alignment: AlignmentType.CENTER,
});
```

**IMPORTANT ImageRun notes:**
- The `type` parameter is REQUIRED (use 'jpg' for JPEG, 'png' for PNG)
- Always read the file as a Buffer with `fs.readFileSync()`
- Adjust `transformation` dimensions to fit within page margins (max width ~580px for US Letter)
- Add a caption paragraph below each image with the timestamp

#### Document Structure — Adaptive, Not Fixed

The document has a few fixed structural elements but the CORE CONTENT sections are completely adaptive to the video's content.

**Fixed elements (always include):**

1. **Cover Page** — Title, channel, URL, date, duration, topic tags
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
- Code blocks INLINE where code was shown/discussed (captured + completed)
- Mermaid diagrams INLINE where architecture/workflows were shown
- Data tables INLINE where comparisons/stats were shown
- Visual callout boxes INLINE for important on-screen content
- Key insight callouts for critical points
- Timestamp references so the reader can jump to the video

### Step 5: Save and Present

Save the generated .docx file to the user's workspace folder. Use a descriptive filename:
- Single video: `[VideoTitle]_LearnFromVideo_Notes.docx`
- Multiple videos: `[Topic]_Combined_LearnFromVideo_Notes.docx`

Sanitize the filename (remove special characters, limit to 80 chars).

Present the file link to the user with a brief note about what was captured (e.g., "Created 35-page report covering both videos with 15 embedded screenshots, 6 inline diagrams, 8 code blocks with analysis").

## Multi-Video Handling

When the user provides multiple YouTube URLs:

1. Fetch transcripts for all videos
2. Download all videos and extract frames from each
3. Identify the common topic/theme across videos
4. Create a single consolidated document that:
   - Has a "Video Sources" table at the beginning listing all videos
   - Organizes content by THEME, not by video — merge overlapping content
   - Cross-references between videos where they cover the same concept
   - Notes where videos agree, disagree, or offer different perspectives
   - Has combined key takeaways ranked by emphasis across videos
5. If videos cover completely different sub-topics, organize as separate major sections clearly labeled

## Handling Edge Cases

- **No captions available**: Ask the user to paste the transcript manually. Guide them: "Click the three dots below the video > Open transcript > Select All > Copy"
- **yt-dlp download fails**: Try alternative format selectors. If video is restricted/private, inform the user and fall back to transcript-only mode.
- **Very large video files**: Use `worst[ext=mp4]` format to minimize file size. Delete video after frame extraction to save disk space.
- **Non-English videos**: The transcript API supports multiple languages. Note the language in the document header.
- **Very long videos (>1 hour)**: Still capture everything. May need to increase screenshot interval to 30-40 seconds. Consider adding a "Reading Guide" after the TOC.
- **Live streams or music videos**: Let the user know if the transcript doesn't contain educational material.
- **Playlist URLs**: Extract individual video IDs and process each one.
- **Partially inaudible/garbled transcript**: Mark unclear segments with "[unclear at timestamp]" rather than guessing.
- **npm install -g docx fails**: Use local install (`npm install docx` in working directory) instead of global install. This is the recommended approach.
- **Read-only skill directory**: Skill files may be mounted read-only. Always copy scripts to a writable location (e.g., `/tmp/learn-from-video/`) before modifying.

## Critical Implementation Notes (Lessons Learned)

These notes come from real-world experience running this skill:

### Screenshot Capture
- **yt-dlp + ffmpeg is the PRIMARY method** for capturing screenshots. This is reliable and works in all environments without browser dependencies.
- Download at lowest usable quality (`worst[ext=mp4]` or `best[height<=480]`) to save time and disk space.
- Use `ffmpeg -ss TIMESTAMP -i video.mp4 -frames:v 1 -q:v 2 output.jpg` for individual frames.
- 20-30 second intervals give dense coverage. For a 30-min video, this produces ~60-90 frames.
- ALWAYS combine regular intervals with targeted key-moment captures.
- Delete the video file after extracting all frames to free disk space.

### Transcript-First Workflow
- ALWAYS fetch and analyze the transcript FIRST before downloading the video.
- The transcript tells you exactly WHEN to look for visual content.
- This saves time and produces more targeted screenshots.
- Build a timestamp map of key visual moments from the transcript analysis.

### Code Extraction from Screenshots
- Code shown in videos is often partial — complete it to a working example.
- Clearly mark original code vs. added completions.
- Use agents to analyze code blocks and add explanations.
- Represent code inline in the document, right where it is discussed.
- This is one of the most valuable features — readers get working code they can use.

### Document Generation
- Use `npm install docx` (local, not global) to avoid permission errors.
- ImageRun requires the `type` parameter ('jpg' or 'png') — this is mandatory.
- For Table of Contents, use a MANUAL TOC (list of headings as Paragraphs) instead of the `TableOfContents` widget for cross-platform compatibility.
- Use `ShadingType.CLEAR` not `ShadingType.SOLID` for cell shading.
- Set BOTH `columnWidths` on Table AND `width` on each TableCell.
- Use `LevelFormat.BULLET` for bullet lists (never unicode bullet characters).
- Validate the document with `python <docx-skill-path>/scripts/office/validate.py output.docx`.

## Quality Standards

The document should be thorough enough that someone who reads it gets 90%+ of the value of watching the video:
- No skipping over "minor" points — capture everything
- Preserve the logical flow and sequence of the presentation
- Make implicit visual information explicit in text
- Include timestamps throughout so the reader can jump to specific video moments
- Embed actual screenshots at key moments via ImageRun
- Recreate all diagrams, workflows, and architecture as Mermaid diagrams — INLINE where discussed
- Format all code as proper code blocks with language identification — INLINE where discussed
- Complete partial code to working examples with clear markers
- Visual callout boxes for on-screen content — INLINE where discussed
- The report should feel like one person explaining the complete video to another
- A reader should NEVER need to flip to a different section to see "what was on screen at this point"

## Attribution and Legal

Every document includes:
- Header: Video title | "learnFromVideo Notes"
- Footer: "Notes generated from YouTube video for personal learning use | Page X"
- Cover page: Full video URL, channel name, creation date
- Final page note: "For the complete experience, watch the original video at [URL]. All content credit to [channel name]."
