#!/usr/bin/env python3
"""
Generate placeholder audio files for the Deliver course.

Creates minimal valid MP3 files (silent, 1 second) for each audio block
reference so the course can render without 404s. Replace with real
recordings or TTS before launch.

Usage:
    python scripts/generate_deliver_audio_placeholders.py
"""
import struct
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "course" / "deliver"

# Audio files referenced in lesson blocks
AUDIO_FILES = {
    "audio/deliver/daily-5-guided.mp3": {
        "title": "The Daily 5 — Guided Exercise",
        "description": "5-minute guided mental rehearsal covering: gratitude, intention, visualization, affirmation, breath.",
        "duration_target": "5:00",
    },
    "audio/deliver/grit-stack-walkthrough.mp3": {
        "title": "The Grit Stack — Guided Walkthrough",
        "description": "Guided walk through the 5 steps: Breathe, Detach, Reframe, Execute, Segment.",
        "duration_target": "4:00",
    },
    "audio/deliver/m3-breathing-space.mp3": {
        "title": "3-Minute Breathing Space",
        "description": "Short mindfulness exercise: awareness, gathering, expanding. Based on MBCT protocol.",
        "duration_target": "3:00",
    },
    "audio/deliver/m3-highlight-reel.mp3": {
        "title": "Highlight Reel Visualization",
        "description": "Guided visualization replaying peak performance moments with full sensory detail.",
        "duration_target": "6:00",
    },
    "audio/deliver/post-race-debrief.mp3": {
        "title": "Post-Race Debrief — Guided Reflection",
        "description": "Structured audio guide walking through the post-race debrief process.",
        "duration_target": "5:00",
    },
    "audio/deliver/pre-race-mental-warmup.mp3": {
        "title": "Pre-Race Mental Warm-Up",
        "description": "10-minute pre-race routine: centering breath, performance cues, race visualization, activation.",
        "duration_target": "10:00",
    },
}


def create_silent_mp3(path: Path, duration_seconds: float = 1.0):
    """Create a minimal valid MP3 file with silence.

    Uses a single MPEG audio frame (MPEG1 Layer3, 128kbps, 44100Hz, stereo)
    filled with zeros. This is the simplest valid MP3 that any player will
    accept without error.
    """
    # MPEG1 Layer 3, 128kbps, 44100Hz, stereo frame header
    # 0xFFFB9004 = sync(11) + version(2:MPEG1) + layer(2:III) + protection(1:none)
    #              + bitrate(4:128k) + samplerate(2:44100) + padding(1:0) + private(1:0)
    #              + channel(2:stereo) + ...
    header = b'\xff\xfb\x90\x04'
    # Frame size for 128kbps @ 44100Hz = 417 bytes (header + data)
    frame_data = header + b'\x00' * (417 - 4)

    # 44100 samples per frame / 44100Hz = ~0.026s per frame
    # For 1 second we need ~38 frames
    frames_needed = int(duration_seconds * 44100 / 1152) + 1

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        for _ in range(frames_needed):
            f.write(frame_data)


def main():
    print("Generating audio placeholders for Deliver course...")
    print(f"Output: {OUTPUT_DIR}\n")

    # Also write metadata manifest
    manifest = {}

    for rel_path, meta in AUDIO_FILES.items():
        full_path = OUTPUT_DIR / rel_path
        create_silent_mp3(full_path)
        size_kb = full_path.stat().st_size / 1024
        print(f"  {rel_path} ({size_kb:.0f} KB)")
        print(f"    → {meta['title']} [{meta['duration_target']}]")
        manifest[rel_path] = meta

    print(f"\n{len(AUDIO_FILES)} placeholder audio files created.")
    print("\nIMPORTANT: Replace these with real recordings or TTS before launch.")
    print("Each file contains silent MP3 frames — valid but inaudible.")

    # Write manifest for tracking
    import json
    manifest_path = OUTPUT_DIR / "audio" / "deliver" / "audio-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nManifest: {manifest_path}")


if __name__ == "__main__":
    main()
