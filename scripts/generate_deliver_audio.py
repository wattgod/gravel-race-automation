#!/usr/bin/env python3
"""
Generate the 8 Deliver guided-audio exercises via ElevenLabs TTS.

Reads the narration scripts from ~/endure-mind/scripts/audio/*.md, strips the
metadata header, converts [N-second silence/pause] cues into <break> tags, and
synthesizes each file in Matt's cloned voice per PRODUCTION.md settings
(stability 0.5, similarity_boost 0.75, 44.1kHz).

Masters are written to data/courses/deliver/audio-masters/ (the recordings cost
real money — keep them) and copied into wordpress/output/course/deliver/audio/
where the lesson pages reference them.

Usage:
    export ELEVENLABS_API_KEY=...
    python3 scripts/generate_deliver_audio.py --list-voices   # find the clone's voice id
    export ELEVENLABS_VOICE_ID=...
    python3 scripts/generate_deliver_audio.py --dry-run       # char counts, no spend
    python3 scripts/generate_deliver_audio.py                 # generate all 8
    python3 scripts/generate_deliver_audio.py --only six-two-seven-guided
"""

import argparse
import json
import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = Path.home() / "endure-mind" / "scripts" / "audio"
MASTERS_DIR = PROJECT_ROOT / "data" / "courses" / "deliver" / "audio-masters"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "course" / "deliver" / "audio"

API_BASE = "https://api.elevenlabs.io/v1"
MODEL_ID = "eleven_multilingual_v2"
VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75}
OUTPUT_FORMAT = "mp3_44100_128"  # 44.1kHz per PRODUCTION.md
CHUNK_LIMIT = 4000  # chars per request; stitched via previous_request_ids

# narration script -> output mp3 (must match lesson block srcs)
SCRIPT_MAP = {
    "01-6-2-7-breathing.md": "six-two-seven-guided.mp3",
    "02-progressive-muscle-relaxation.md": "progressive-muscle-relaxation.mp3",
    "03-highlight-reel.md": "m3-highlight-reel.mp3",
    "04-pre-race-warmup.md": "pre-race-mental-warmup.mp3",
    "05-breathing-space.md": "m3-breathing-space.mp3",
    "06-grit-stack.md": "grit-stack-walkthrough.mp3",
    "07-post-race-debrief.md": "post-race-debrief.mp3",
    "08-daily-5.md": "daily-5-guided.mp3",
}


def parse_script(md_path: Path) -> str:
    """Extract narration text: drop metadata header, convert cue markers."""
    text = md_path.read_text()
    # Everything after the "## Script" heading is narration
    m = re.search(r"^## Script\s*$", text, flags=re.MULTILINE)
    if m:
        text = text[m.end():]
    # [3-second silence] / [2-second pause] -> <break> tags (3s max each, chained)
    def cue_to_breaks(match):
        secs = int(match.group(1))
        tags = []
        while secs > 0:
            step = min(secs, 3)
            tags.append(f'<break time="{step}.0s" />')
            secs -= step
        return " ".join(tags)
    text = re.sub(r"\[(\d+)-second[^\]]*\]", cue_to_breaks, text)
    # Drop any leftover bracketed stage directions ([music fades] etc.)
    text = re.sub(r"\[[^\]]+\]", "", text)
    # Markdown emphasis/heading residue
    text = re.sub(r"^#+\s.*$", "", text, flags=re.MULTILINE)
    text = text.replace("**", "").replace("*", "")
    # Collapse blank runs
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def chunk_text(text: str) -> list:
    """Split on paragraph boundaries into <=CHUNK_LIMIT chunks."""
    chunks, current = [], ""
    for para in text.split("\n\n"):
        if current and len(current) + len(para) + 2 > CHUNK_LIMIT:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def api_request(path: str, api_key: str, payload=None, extra_headers=None):
    headers = {"xi-api-key": api_key}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(f"{API_BASE}{path}", data=data, headers=headers)
    return urllib.request.urlopen(req, timeout=300)


def list_voices(api_key: str):
    with api_request("/voices", api_key) as resp:
        voices = json.load(resp)["voices"]
    for v in voices:
        print(f"{v['voice_id']}  {v['name']}  ({v.get('category', '?')})")


def synthesize(name: str, text: str, api_key: str, voice_id: str) -> bytes:
    """Generate one file, stitching chunks for prosody continuity."""
    audio = b""
    request_ids = []
    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        payload = {
            "text": chunk,
            "model_id": MODEL_ID,
            "voice_settings": VOICE_SETTINGS,
        }
        if request_ids:
            payload["previous_request_ids"] = request_ids[-3:]
        print(f"  chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)...")
        with api_request(
            f"/text-to-speech/{voice_id}?output_format={OUTPUT_FORMAT}",
            api_key, payload,
        ) as resp:
            rid = resp.headers.get("request-id")
            if rid:
                request_ids.append(rid)
            audio += resp.read()
    return audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="basename of a single output mp3 (no extension)")
    args = ap.parse_args()

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        sys.exit("ELEVENLABS_API_KEY not set")

    if args.list_voices:
        list_voices(api_key)
        return

    targets = {
        SCRIPTS_DIR / md: mp3 for md, mp3 in SCRIPT_MAP.items()
        if not args.only or mp3 == f"{args.only}.mp3"
    }
    if not targets:
        sys.exit(f"--only {args.only!r} matches nothing; options: "
                 + ", ".join(v[:-4] for v in SCRIPT_MAP.values()))

    parsed = {mp3: parse_script(md) for md, mp3 in targets.items()}
    total_chars = sum(len(t) for t in parsed.values())
    for mp3, text in parsed.items():
        print(f"{mp3}: {len(text)} chars, {len(chunk_text(text))} chunk(s)")
    print(f"TOTAL: {total_chars} chars (~${total_chars / 1000 * 0.12:.2f} at Pro tier)")
    if args.dry_run:
        return

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    if not voice_id:
        sys.exit("ELEVENLABS_VOICE_ID not set (find it with --list-voices)")

    MASTERS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for mp3, text in parsed.items():
        print(f"\nGenerating {mp3}...")
        audio = synthesize(mp3, text, api_key, voice_id)
        master = MASTERS_DIR / mp3
        master.write_bytes(audio)
        shutil.copy2(master, OUTPUT_DIR / mp3)
        print(f"  wrote {master} ({len(audio) // 1024} KB) + copied to output")

    print("\nDone. Listen to each file before deploy — check pacing, "
          "pronunciation, and that cue pauses landed.")


if __name__ == "__main__":
    main()
