---
name: learn-from-video
version: "3.3.0"
description: "Create comprehensive, report-style learning notes from any video — called 'learnFromVideo'. Use this skill whenever the user shares a video URL or file and wants notes, a summary, a study guide, or learning material from it. Also triggers when the user says 'learn from this video', 'learnFromVideo', 'create notes from this video', 'make notes for this video', 'I watched this video and need notes', 'summarize this video in detail', 'take notes from this lecture', 'notes from this tutorial', 'I don't have time to watch this video', or shares one or more video URLs/files and asks for any kind of written output about the content. This skill handles single videos and multiple videos on the same topic, producing a professional Word document (.docx) report with full detail — not a brief summary, but a thorough report capturing everything spoken AND shown in the video, including diagrams, workflows, code, and architecture recreated as Mermaid flowcharts."
argument-hint: "<video-url-or-path> [extra instructions]"
allowed-tools: Bash, Read, Write, Task, AskUserQuestion
homepage: https://github.com/yogeshcodeshare/learn-from-video-Skill
repository: https://github.com/yogeshcodeshare/learn-from-video-Skill
author: yogeshcodeshare
license: MIT
user-invocable: true
---

# learnFromVideo — v3.3

Produce a Word document so thorough that reading it is as good as watching the video. Not a summary — a **replacement**.

## The one failure mode that matters

This skill's characteristic failure is a document that **looks** finished and **is** empty. Images are embedded, headings are styled, tables are formatted — and the actual content is a summary of a summary. The reader learns that topics were discussed, not what was said about them.

It happens because reading a long transcript and then writing produces an *impression* of the video, not a *record* of it. The impression is always shorter than the truth.

**Two mechanical defences are built in and are not optional:**

1. `scripts/segment.py` slices the transcript into windows. You write one subsection per window, with that window's verbatim text in front of you.
2. `scripts/verify_docx.py` measures the finished document against the transcript and **fails the run** if it is too thin or skips windows.

If verification fails, the document is not delivered. You regenerate it.

---

## Resolve `SKILL_DIR` and `WATCH_DIR`

Set `SKILL_DIR` to the **absolute path of the directory containing THIS SKILL.md you just Read** — your harness reported that path in the Read result. The `watch` engine is a sibling skill directory:

```
SKILL_DIR = <dir of this SKILL.md>          # …/skills/learn-from-video
WATCH_DIR = <SKILL_DIR>/../watch            # …/skills/watch
```

Do NOT use `${CLAUDE_SKILL_DIR}` — it is unset outside Claude Code.

**Python interpreter:** on macOS/Linux use `python3`. On **Windows** substitute `python` — `python3` there is a Microsoft Store stub and will not run.

## Step 0 — Preflight (once per session)

```bash
python3 "${SKILL_DIR}/scripts/preflight.py" --json
```

This checks the engine, ffmpeg/yt-dlp/Whisper (by delegating to the engine's own `setup.py`), **and Node + npm**, which the document step needs.

| `status` | Meaning | Action |
|---|---|---|
| `ready` | Everything present | Proceed silently. Do not announce it. |
| `needs_node` | Ingestion fine, no Node/npm | **Tell the user now, before extracting frames.** Discovering this after an hour of work wastes the whole run. Offer to continue to a Markdown deliverable instead. |
| `engine_missing` | Sibling `watch` skill absent | Stop. The skill cannot run. |

If the engine reports `first_run`, run `python3 "${WATCH_DIR}/scripts/setup.py"` and encourage a Whisper key (Groq preferred — cheaper, faster). A key is **effectively required for local video files**, which never have captions.

---

## Step 1 — Cost gate

Get the duration first (`ffprobe`, or a `--detail transcript` pass).

**Videos over 20 minutes, or any request implying `token-burner`: tell the user the cost and get agreement before extracting frames.** State the frame count, the resolution, and the rough image-token cost. Offer the focused alternative (`--start`/`--end` over the sections that matter). This is a rule, not a judgment call.

Rough arithmetic: 80 frames at 512px ≈ 50–80k image tokens; at 1024px roughly 4× that.

---

## Step 2 — Ingest (Agent 1: Transcript Analyst)

**Always go through the wrapper, never call `watch.py` directly:**

```bash
WORK="${TMPDIR:-/tmp}/lfv-<video-slug>"
python3 "${SKILL_DIR}/scripts/ingest.py" "<SOURCE>" --work "$WORK" --detail transcript --json
```

`ingest.py` adds three things the engine lacks, each from an observed real-world failure:

- **UTF-8 safety.** On Windows the engine crashes with `UnicodeEncodeError` on Devanagari, CJK, Cyrillic or emoji — *after* the Whisper call has completed and been paid for. The wrapper forces UTF-8 so a non-English transcript cannot destroy itself.
- **Transcript caching.** The engine caches extracted audio but not the transcript. The wrapper caches the full report per (source, flags) in `$WORK/.lfv-cache/`. Re-running is then free, and a crash later in the pipeline costs nothing to recover from.
- **Retries.** Groq/OpenAI return HTTP 5xx under load. The wrapper retries with exponential backoff instead of letting one 500 abort the run.

It accepts every engine flag and passes them through. `--json` returns `{status, cache_hit, attempts, has_transcript, report_path, work_dir}`.

**Record the transcript provenance** — `captions` or `whisper (groq|openai)`. It goes in the document's source table, and Whisper output needs an accuracy caveat (below).

### Then segment it

```bash
python3 "${SKILL_DIR}/scripts/segment.py" "$WORK/.lfv-cache/report-<key>.md" --window 120 --json
```

Returns every window with its verbatim text, plus `min_document_words` — the floor your document must clear. **Keep this JSON. It is your work plan.**

### Record state as you go

```bash
python3 "${SKILL_DIR}/scripts/state.py" "$WORK" init --source "<SOURCE>" --title "..."
python3 "${SKILL_DIR}/scripts/state.py" "$WORK" set transcript --json-file t.json
python3 "${SKILL_DIR}/scripts/state.py" "$WORK" set frames --json-file manifest.json
python3 "${SKILL_DIR}/scripts/state.py" "$WORK" status
```

Phases: `transcript · windows · frames · code · visuals · document`.

Write each phase's output to state **as it completes**. `ingest.py` caches the transcript, but the *analysis* — which timestamps matter, what each frame shows, code reconstructed across frames — costs image tokens that are already spent. Losing it to a crash at Agent 4 means paying twice.

On any resumed run, check `state.py "$WORK" status` first and read back completed phases instead of re-deriving them.

### Then tag the visual moments

Read the transcript and mark every timestamp where something is shown:

`[CODE start-end]` · `[DIAGRAM t]` · `[SLIDE t]` · `[UI t]` · `[TERMINAL t]` · `[DATA t]` · `[KEY_CONCEPT t]`

Signal phrases: "as you can see", "on the screen", "let me show you", "here we have", "over here", "right here", "this diagram", "let me run this", "the output is", "this table shows", plus any filename, menu name, or number being read aloud.

These become the `--timestamps` cue list. Pointing at a static slide is a *low* visual-change event that scene detection reliably misses — cue frames are how you catch it. **Ignore rhetorical uses** ("look, the point is…"); that judgment is why this is done by you and not a regex.

---

## Step 3 — Extract frames (Agent 2: Screenshot Extractor)

```bash
python3 "${SKILL_DIR}/scripts/ingest.py" "<SOURCE>" --work "$WORK" \
  --detail balanced --resolution 1024 --max-frames 52 \
  --timestamps "3:45,4:05,7:20,..."
```

- `--resolution 1024`, not the engine's 512 default. On-screen code and UI labels are unreadable at 512px. This is the deliberate cost of a skill whose job is transcribing what is on screen.
- Cue frames are **pinned** — reserved against the cap before scene selection, so they can never be evicted.
- `--max-frames` keeps the bill predictable. Cues are reserved first, scene frames fill the remainder.
- Near-duplicates are dropped automatically. Use `--no-dedup` **only** for typing sequences, where consecutive frames are near-identical by pixel delta yet each carries new lines.

**Focused re-runs** for code windows and any region needing detail, pointed at the local file so nothing is re-downloaded:

```bash
python3 "${SKILL_DIR}/scripts/ingest.py" "$WORK/download/<file>" --work "$WORK/code-3-45" \
  --start 3:45 --end 4:12 --fps 2 --resolution 1024 --no-dedup
```

Read every frame with `Read` — in a single message, parallel calls, so you see them in order.

---

## Step 4 — CONTENT DEPTH (the part that is usually skipped)

**Write the document window by window from `segment.py` output. Never from a remembered overview.**

For each window, with its verbatim text in front of you, record:

1. **What was said** — the actual explanation, reasoning and analogy. Not that an explanation occurred.
2. **What was shown** — exact field names, menu paths, dropdown options, button labels, values typed, from the frames.
3. **Why it matters** — the reason given, and the consequence of getting it wrong.
4. **Every number, name and worked example** — in full. Never "he gives an example"; reproduce the example with its values.

### Anti-patterns — these are the failure, verbatim

| Never write | Write instead |
|---|---|
| "The instructor explains the difference between X and Y." | The actual difference, stated. |
| "He demonstrates how to create a tag." | Manage → Tags → Add Tag → name it `1.1 NEW LEAD` → Save. |
| "Various options are available." | The options, listed. |
| "He gives a real-estate example." | The example with its actual figures. |
| "This section covers filtering." | How filtering works, including the operator semantics. |

The test for any sentence: **could a reader act on it without watching the video?** If not, it is a label, not content.

### Hard requirements

- **One subsection per window.** 20 windows → 20 subsections. Do not merge windows to save effort; merge only when genuinely one continuous topic, and then cover both windows' content in full.
- **Clear `min_document_words`** from `segment.py`. It is a floor, not a target.
- **Coverage target is 100%. The gate fails below 90%.** Every transcript window gets written up. The 10% tolerance exists only for genuinely empty stretches — silence, dead air, an unrelated aside — never for content that was merely hard to write up.
- Coverage is measured by **words attributed to each window**, not by mentions. Naming a timestamp and writing nothing does not count; the verifier attributes prose following each timestamp to that window and requires a real share.
- **Every screenshot needs surrounding narrative** from its own timestamp — a caption alone is not coverage.
- **Reproduce all lists in full.** If a dropdown has 7 options, all 7 appear.
- **Long videos produce long documents.** A 40-minute tutorial is 25–40 pages. If yours is 10, you summarised.

---

## Step 5 — Code (Agent 3) and Visuals (Agent 4)

**Code Specialist.** Transcribe every visible line exactly. Detect gaps where code is scrolled or cropped and request tighter focused frames with `--no-dedup`. Merge fragments across frames into one block, then complete it to a working example using transcript context and your own knowledge. Mark sources explicitly:

```
// === FROM VIDEO [3:45] ===
const app = express();
// === FROM VIDEO [3:52] — scrolled down ===
function handler(req, res) { res.json({ status: 'ok' }); }
// === ADDED FOR COMPLETENESS ===
import express from 'express';
app.listen(3000);
```

Then explain each block: what it does, the pattern shown, how it connects to the concept.

**Visual Content Analyst.** Diagrams → Mermaid. Slides → title and every bullet. UI → every field, button and label. Data → the full table.

Embed vs skip: **embed** slides, editor code, dashboards, architecture diagrams, data. **Skip** face-cam-only, semantic duplicates, blurry frames. The engine removed pixel-duplicates; yours is the semantic judgment it cannot make.

**Label third-party software.** If the presenter switches to a different product for comparison, say so explicitly in the caption — otherwise a newcomer believes it is the same tool.

---

## Step 6 — Assemble the document (Agent 5)

**Do not hand-write docx-js.** Produce a JSON spec and render it:

```bash
npm install docx                     # local, never global
python3 -c "..."                     # write spec.json
node "${SKILL_DIR}/scripts/build_docx.js" spec.json
```

`build_docx.js` owns every docx-js gotcha once, correctly, and is covered by tests. Block types: `h2` `h3` `p` `ts` `bullets` `image` `table` `callout` `code` `mermaid` `spacer` `pagebreak`. See the header comment in the script for the full schema. It returns JSON with counts and warnings (e.g. missing images), so you can check the render before verifying.

Read `${SKILL_DIR}/references/report_structure.md` for structural guidance.

**Fixed elements:** Cover · Manual TOC · Executive Summary · **[adaptive core content]** · Quick Reference tables · Source & Attribution.

**Adaptive core** follows the video's own flow — a tutorial goes Setup → Step 1 → Step 2; a system-design talk goes Problem → Architecture → Trade-offs. Within each section weave spoken content, screenshots, code and diagrams together **inline**. A reader must never flip elsewhere to see what was on screen.

### docx-js gotchas — handled for you

`build_docx.js` already applies all of these. They are listed only so you do not reintroduce them if you ever bypass it: `ImageRun` requires `type`; images clamp to 560px; the TOC must be manual because the widget renders empty outside Word; `ShadingType.CLEAR` not `SOLID`; tables need width in two places and `WidthType.DXA`; `LevelFormat.BULLET` for bullets. Oversized table widths are scaled to fit rather than overflowing the page.

### Non-English and machine transcripts

State the language on the cover. For Whisper output, add an explicit caveat: proper nouns, product names and numbers may be mis-transcribed — **but UI details read from screenshots are reliable**. Say which is which; it tells the reader what to trust.

If the file's timeline differs from any timeline the user supplies, use the file's and say so.

---

## Step 7 — Verify, then deliver

```bash
python3 "${SKILL_DIR}/scripts/verify_docx.py" "<OUT.docx>" \
  --report "$WORK/.lfv-cache/report-<key>.md" --window 120
```

| Exit | Meaning |
|---|---|
| `0` | Passed — deliver |
| `1` | File invalid or unreadable |
| `4` | **Density failure — do NOT deliver.** Regenerate with real content in the windows it flags. |

On exit 4 the tool names the problem and lists each thin window as `MM:SS (Nw written, need >= Mw)`. Go back to those windows in the `segment.py` output, write them up properly from their verbatim text, and re-run. **Never lower `--min-coverage` or `--min-words` to make it pass** — that reintroduces the exact defect the gate exists to catch.

Then read back 3–5 random sections and confirm each has both spoken content and on-screen detail woven together, code inline where discussed, and captioned screenshots.

**Save as** `[VideoTitle]_LearnFromVideo_Notes.docx` (sanitised, ≤80 chars), or `[Topic]_Combined_...` for multi-video.

**Clean up:** work dirs hold the downloaded video, extracted audio and every frame. Remove them once verified — unless the user may want more screenshots, in which case say they were kept.

---

## Multi-video

Run Steps 2–5 per video, each in its own `--work` directory, then merge **by theme, not by video**. Cluster topics by keyword overlap (>50% shared = same theme). For overlapping themes give each video's take, then synthesise. Tag points with `[Video N]`, include a comparison table, and open with a "Video Sources" table. Depth rules apply per video — a 3-video set has 3× the windows to cover.

---

## Edge cases

- **No transcript at all** — captions missing and Whisper unavailable. Offer to set up a key, or ask the user to paste the transcript. Proceeding frames-only must be stated plainly in the document.
- **Whisper failed** — `ingest.py` already retried. If it still fails, try `--whisper openai`. Audio over 25 MB is chunked automatically, so length alone is never the cause.
- **Download fails** — if login-required or region-locked, say so and stop. Do not keep retrying.
- **Very long (>1 hour)** — run focused passes over the sections that matter rather than one thin full scan. Add a Reading Guide after the TOC.
- **Local files** — no captions ever exist; Whisper is effectively required.
- **No audio stream** — the engine reports it; proceed frames-only and say so.
- **Playlists** — extract individual IDs and process each.
- **Garbled audio** — mark `[unclear at MM:SS]` rather than guessing.
- **Read-only skill dir** — never write into `$SKILL_DIR`; all output goes to `--work`.
- **npm global install fails** — use a local `npm install docx`.

---

## Token budget

Frames dominate. If you already extracted frames this session, **do not re-run** — answer from what you have. `ingest.py`'s cache makes repeat ingestion free, but re-reading frames is not.

---

## Evaluation

`${SKILL_DIR}/eval/eval.json` holds output-quality assertions; `${SKILL_DIR}/references/self_improve_prompt.md` holds the improvement loop. `tests/` covers the scripts.

Boundary with the bundled `/watch` skill: **`/watch` answers questions in chat, `learn-from-video` produces a document.** "What happens at 2:30?" is `/watch`.

---

## Security & Permissions

Runs `yt-dlp` and `ffmpeg`/`ffprobe` locally. Sends **extracted audio only** — never the video — to Groq or OpenAI, and only when captions are missing. Runs `npm install docx` in the working directory. Writes video, frames, audio, transcript cache and the .docx to the working directory. Reads/creates `~/.config/watch/.env` (mode `0600`) for API keys.

Does not access any platform account, does not share keys between providers, does not log keys anywhere.

**Bundled scripts:** `ingest.py` (cached, retrying, encoding-safe engine wrapper) · `preflight.py` (dependency check) · `segment.py` (transcript windows + coverage plan) · `state.py` (durable phase state for resume) · `build_docx.js` (spec → .docx renderer) · `verify_docx.py` (density gate) · `fetch_transcript.py` (legacy YouTube-only fallback). The engine itself lives in the sibling `watch` skill.

Review scripts before first use.

---

## Attribution

Every document includes the video title and source, the creator's name, the transcript provenance, and a closing note crediting the original creator. Notes are for personal learning use; respect the creator's content.

The ingestion engine at `skills/watch/` is from [bradautomates/claude-video](https://github.com/bradautomates/claude-video), MIT licensed, vendored byte-identical to upstream. This skill's scripts wrap it rather than modifying it, so that parity is preserved.
