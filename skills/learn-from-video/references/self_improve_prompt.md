# Self-Improvement Prompt Template for learn-from-video

Use this prompt to run an autonomous Karpathy-style improvement loop on the learn-from-video skill.

## How to Use

Paste the prompt below into Claude Code and let it run. Do NOT interrupt unless you want it to stop.

## The Prompt

---

Run a self-improvement loop on the learn-from-video skill using the eval/eval.json file.

**Setup:**
1. Read the SKILL.md, references/report_structure.md, and eval/eval.json
2. Note the current git state (branch/commit)

**For each iteration cycle:**
1. Run the skill on each test in eval.json (use a real short video URL — under 5 minutes)
2. For each test output, validate ALL binary assertions
3. Calculate the pass_rate: (assertions_passed / total_assertions) x 100
4. Log the results:
   - Iteration number
   - Score (e.g., 27/30)
   - Pass rate (e.g., 90%)
   - Which assertions FAILED (list by ID)
   - Time taken for this iteration

**Decision:**
- If score IMPROVED from previous iteration -> git commit with message "skill: improve learn-from-video (score X/30 -> Y/30)"
- If score DROPPED or stayed same -> git reset to previous commit, try a DIFFERENT change
- If score is PERFECT (30/30) -> stop and report

**Making changes:**
- Make only ONE change to SKILL.md per iteration
- Focus on the FAILING assertions — fix the most impactful one first
- Changes can be: adding instructions, clarifying existing rules, adding examples, fixing edge cases
- Do NOT remove existing working instructions — only add or refine

**Rules:**
- Do NOT ask for my permission. Keep looping autonomously.
- Do NOT pause to ask if you should continue.
- Log everything to eval/improvement_log.md
- Keep looping until you hit perfect score OR I manually interrupt you.
- You are autonomous. The human might be asleep.

**Improvement History:**
After each iteration, append to eval/improvement_log.md:

| Iteration | Score | Pass Rate | Failed | Change Made | Time |
|-----------|-------|-----------|--------|-------------|------|

This history is valuable — future models can pick up where you left off.

---

## Two Layers of Improvement

### Layer 1: Skill Activation (Description)
Tests whether Claude triggers the skill for correct prompts and doesn't trigger for wrong ones.

**Should trigger:**
- "create notes from this video"
- "learn from this video"
- "learnFromVideo [url]"
- "summarize this lecture"
- "take notes from this tutorial"
- "I don't have time to watch this"

**Should NOT trigger:**
- "summarize this PDF"
- "write a report about AI"
- "take notes from this meeting"
- "convert this document"

Optimization: Adjust the YAML `description` field in SKILL.md frontmatter to improve activation accuracy.

### Layer 2: Output Quality (This Loop)
Uses binary assertions from eval.json:
- Tests whether the generated document meets quality standards
- Optimizes SKILL.md instructions
- Runs autonomously overnight using the prompt above

### Limitations — What This Loop Cannot Test
- Tone and writing quality (subjective)
- Whether visual descriptions are accurate (needs human review)
- Creative quality of explanations (subjective)
- For these: use qualitative review with human-in-the-loop

## Cost Tracking

Each improvement iteration should log tokens used and approximate cost:

| Iteration | Input Tokens | Output Tokens | Est. Cost |
|-----------|-------------|---------------|-----------|

This helps the user understand the ROI of running the self-improvement loop.
