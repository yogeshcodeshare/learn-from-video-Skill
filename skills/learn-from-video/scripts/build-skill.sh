#!/usr/bin/env bash
# build-skill.sh — package the learn-from-video skill as a claude.ai-upload-ready
# .skill file. Usage: bash skills/learn-from-video/scripts/build-skill.sh
#
# Produces dist/learn-from-video.skill, a zip with a single top-level
# `learn-from-video/` directory containing SKILL.md, references/, eval/ and the
# scripts/ runtime.
#
# NOTE: the standalone bundle does NOT contain the sibling `watch` engine, which
# lives in its own skill folder. Uploaded on its own to claude.ai, this skill
# falls back to scripts/fetch_transcript.py (YouTube captions only) and cannot
# extract frames. For the full pipeline install the plugin from the repo, which
# ships both skills together.
#
# Adapted from skills/watch/scripts/build-skill.sh (bradautomates/claude-video, MIT).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "error: working tree is dirty; commit or stash before building" >&2
  exit 1
fi

mkdir -p dist
OUT="dist/learn-from-video.skill"
git archive --format=zip --prefix=learn-from-video/ --output="$OUT" HEAD:skills/learn-from-video

COUNT=$(unzip -l "$OUT" | tail -1 | awk '{print $2}')
SIZE=$(du -h "$OUT" | cut -f1)

if [ "$COUNT" -gt 200 ]; then
  echo "error: $COUNT files in zip, claude.ai's cap is 200" >&2
  echo "       trim the skills/learn-from-video/ tree or add a .gitattributes export-ignore entry" >&2
  exit 1
fi

SKILL_MD_COUNT=$(unzip -l "$OUT" | grep -c "SKILL.md" || true)
if [ "$SKILL_MD_COUNT" -ne 1 ]; then
  echo "error: expected exactly one SKILL.md, found $SKILL_MD_COUNT" >&2
  exit 1
fi

echo "built $OUT ($COUNT files, $SIZE)"
echo "upload via the claude.ai skill UI"
