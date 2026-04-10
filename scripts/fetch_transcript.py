#!/usr/bin/env python3
"""
Fetch YouTube video transcript given a URL or video ID.
Uses youtube_transcript_api to get captions with timestamps.

Usage:
    python fetch_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
    python fetch_transcript.py "VIDEO_ID"
    python fetch_transcript.py "URL1" "URL2" "URL3"

Output:
    For each video, creates two files in the output directory:
    - {video_id}_transcript.json  (structured data with timestamps)
    - {video_id}_transcript.txt   (human-readable formatted text)
"""

import sys
import os
import json
import re
from urllib.parse import urlparse, parse_qs

def extract_video_id(url_or_id):
    """Extract YouTube video ID from various URL formats or a bare ID."""
    url_or_id = url_or_id.strip()

    # Already a bare video ID (11 chars, alphanumeric + dash + underscore)
    if re.match(r'^[A-Za-z0-9_-]{11}$', url_or_id):
        return url_or_id

    # Handle various YouTube URL formats
    patterns = [
        # Standard: youtube.com/watch?v=ID
        r'(?:youtube\.com/watch\?.*v=)([A-Za-z0-9_-]{11})',
        # Short: youtu.be/ID
        r'(?:youtu\.be/)([A-Za-z0-9_-]{11})',
        # Embed: youtube.com/embed/ID
        r'(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})',
        # Shorts: youtube.com/shorts/ID
        r'(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})',
        # Live: youtube.com/live/ID
        r'(?:youtube\.com/live/)([A-Za-z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    # Try parsing as URL and checking query params
    try:
        parsed = urlparse(url_or_id)
        qs = parse_qs(parsed.query)
        if 'v' in qs:
            return qs['v'][0]
    except Exception:
        pass

    return None


def fetch_transcript(video_id, languages=None):
    """
    Fetch transcript for a given video ID.
    Returns a list of transcript segments with text, start time, and duration.
    Compatible with youtube_transcript_api v1.2.x (instance-based API).
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    if languages is None:
        languages = ['en', 'en-US', 'en-GB', 'hi', 'es', 'fr', 'de', 'pt', 'ja', 'ko', 'zh']

    api = YouTubeTranscriptApi()

    try:
        # Try to fetch transcript (v1.2.x API uses instance methods)
        result = api.fetch(video_id, languages=languages)
        return result.to_raw_data(), None
    except Exception as e1:
        try:
            # Fallback: list available transcripts and pick the best one
            transcript_list = api.list(video_id)
            # Try manually created transcripts first
            for transcript in transcript_list:
                if not transcript.is_generated:
                    fetched = transcript.fetch()
                    return fetched.to_raw_data(), None
            # Fall back to auto-generated
            for transcript in transcript_list:
                fetched = transcript.fetch()
                return fetched.to_raw_data(), None
        except Exception as e2:
            return None, f"Could not fetch transcript: {str(e2)}"


def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS or MM:SS format."""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_transcript_text(segments):
    """Create a human-readable transcript with timestamps."""
    lines = []
    for seg in segments:
        timestamp = format_timestamp(seg['start'])
        text = seg['text'].strip()
        lines.append(f"[{timestamp}] {text}")
    return '\n'.join(lines)


def detect_chapters(segments, min_gap=5.0):
    """
    Attempt to detect natural chapter breaks in the transcript.
    Looks for longer pauses and topic-shift phrases.
    """
    chapter_phrases = [
        'let\'s move on', 'next up', 'moving on', 'now let\'s talk about',
        'the next thing', 'another important', 'let\'s look at',
        'so the first', 'the second thing', 'number one', 'number two',
        'step one', 'step two', 'first of all', 'secondly',
        'let\'s start with', 'let\'s begin', 'in this section',
        'chapter', 'part one', 'part two', 'section',
        'now we\'re going to', 'let me show you', 'let\'s dive into',
    ]

    chapters = []
    for i, seg in enumerate(segments):
        text_lower = seg['text'].lower().strip()

        # Check for topic-shift phrases
        is_chapter = False
        for phrase in chapter_phrases:
            if text_lower.startswith(phrase) or ('. ' + phrase) in text_lower:
                is_chapter = True
                break

        # Check for long gaps between segments
        if i > 0:
            gap = seg['start'] - (segments[i-1]['start'] + segments[i-1].get('duration', 0))
            if gap > min_gap:
                is_chapter = True

        if is_chapter:
            chapters.append({
                'timestamp': seg['start'],
                'timestamp_formatted': format_timestamp(seg['start']),
                'text_hint': seg['text'][:100]
            })

    return chapters


def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_transcript.py <youtube_url_or_id> [url2] [url3] ...")
        print("       python fetch_transcript.py --output-dir /path/to/dir <url>")
        sys.exit(1)

    args = sys.argv[1:]
    output_dir = '/tmp/learn-from-video/transcripts'

    # Parse --output-dir flag
    if '--output-dir' in args:
        idx = args.index('--output-dir')
        output_dir = args[idx + 1]
        args = args[:idx] + args[idx+2:]

    os.makedirs(output_dir, exist_ok=True)

    results = []

    for url in args:
        video_id = extract_video_id(url)
        if not video_id:
            print(f"ERROR: Could not extract video ID from: {url}")
            results.append({'url': url, 'error': 'Invalid URL or video ID', 'video_id': None})
            continue

        print(f"Fetching transcript for video: {video_id}...")
        segments, error = fetch_transcript(video_id)

        if error:
            print(f"ERROR: {error}")
            results.append({'url': url, 'error': error, 'video_id': video_id})
            continue

        # Detect chapters
        chapters = detect_chapters(segments)

        # Build output data
        data = {
            'video_id': video_id,
            'url': url,
            'segment_count': len(segments),
            'total_duration_seconds': int(segments[-1]['start'] + segments[-1].get('duration', 0)) if segments else 0,
            'total_duration_formatted': format_timestamp(segments[-1]['start'] + segments[-1].get('duration', 0)) if segments else '0:00',
            'detected_chapters': chapters,
            'segments': segments
        }

        # Save JSON
        json_path = os.path.join(output_dir, f'{video_id}_transcript.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Save formatted text
        txt_path = os.path.join(output_dir, f'{video_id}_transcript.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"YouTube Video Transcript\n")
            f.write(f"Video ID: {video_id}\n")
            f.write(f"URL: {url}\n")
            f.write(f"Duration: {data['total_duration_formatted']}\n")
            f.write(f"Segments: {data['segment_count']}\n")
            if chapters:
                f.write(f"\nDetected Chapters:\n")
                for ch in chapters:
                    f.write(f"  [{ch['timestamp_formatted']}] {ch['text_hint']}\n")
            f.write(f"\n{'='*60}\n\n")
            f.write(format_transcript_text(segments))

        print(f"SUCCESS: Saved to {json_path}")
        print(f"         Text version: {txt_path}")
        print(f"         Duration: {data['total_duration_formatted']}, Segments: {data['segment_count']}")
        if chapters:
            print(f"         Detected {len(chapters)} potential chapters")

        results.append({
            'url': url,
            'video_id': video_id,
            'json_path': json_path,
            'txt_path': txt_path,
            'duration': data['total_duration_formatted'],
            'segments': data['segment_count'],
            'chapters': len(chapters),
            'error': None
        })

    # Print summary
    print(f"\n{'='*60}")
    print(f"SUMMARY: Processed {len(results)} video(s)")
    for r in results:
        status = "OK" if not r.get('error') else f"FAILED: {r['error']}"
        print(f"  {r.get('video_id', 'unknown')}: {status}")

    # Save results manifest
    manifest_path = os.path.join(output_dir, 'manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nManifest saved to: {manifest_path}")


if __name__ == '__main__':
    main()
