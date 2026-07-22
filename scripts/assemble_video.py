#!/usr/bin/env python3
"""Assemble rough-cut videos from production briefs (brief JSON -> MP4).

Pass 1 (no narration): rough cut timed to each beat's time_range —
- B-roll from the race's curated youtube_data.videos[] (yt-dlp segments,
  cached), cut per beat honoring cut_frequency_sec.
- Branded data-cards (brand_tokens colors, Sometype Mono / Source Serif 4)
  when a beat has no usable B-roll, with a slow Ken Burns zoom.
- Kinetic text-on-screen (word-by-word on the hook), neo-brutalist framing.
- Avatar layer per beat: motion loop -> static PNG -> labeled placeholder.
- Music bed slots respecting music_bpm with volume_db ducking envelopes
  (envelope always written as a sidecar; applied when a music track exists).
- Draft SRT captions burned in + emitted as a sidecar.
- Narration kit: <slug>-teleprompter.md with per-beat WPM targets, pause
  markers (used by the batch WAV splitter) and [RIFF HERE] preserved.

Pass 2 (--narration voice.wav): re-time beats to the actual voice using
whisper word timestamps, mix narration over the bed per the brief's ducking
spec, and emit whisper-aligned captions.

Usage:
    python scripts/assemble_video.py --brief video-briefs/tier-reveal/leadville-100.json
    python scripts/assemble_video.py --brief ... --narration voice.wav
    python scripts/assemble_video.py --batch tier-reveal --tier T1
    python scripts/assemble_video.py --batch tier-reveal --tier T1 --no-broll

Outputs to video-output/<format>/<slug>/:
    <slug>-rough.mp4, <slug>-teleprompter.md, <slug>.srt,
    <slug>-envelope.json, <slug>-report.json
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))

from brand_tokens import COLORS, TIER_NAMES  # noqa: E402
from validate_video_briefs import SHORT_FORMATS  # noqa: E402

# ── Paths ─────────────────────────────────────────────────────────────────
BRIEFS_DIR = PROJECT_ROOT / "video-briefs"
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
ASSETS_DIR = PROJECT_ROOT / "assets"
AVATAR_DIR = ASSETS_DIR / "avatar"
LOOPS_DIR = AVATAR_DIR / "loops"
PLACEHOLDER_DIR = AVATAR_DIR / "placeholders"
MUSIC_DIR = ASSETS_DIR / "music"
OUTPUT_DIR = PROJECT_ROOT / "video-output"
BROLL_CACHE = PROJECT_ROOT / "data" / "broll-cache"
FONTS_DIR = PROJECT_ROOT / "guide" / "fonts"

FONT_MONO = FONTS_DIR / "SometypeMono-Regular.ttf"
FONT_MONO_BOLD = FONTS_DIR / "SometypeMono-Bold.ttf"
FONT_SERIF = FONTS_DIR / "SourceSerif4-Variable.ttf"

# ── Render constants ──────────────────────────────────────────────────────
FPS = 30
RES_SHORT = (1080, 1920)   # 9:16
RES_LONG = (1920, 1080)    # 16:9
AVATAR_WIDTH_FRAC = 0.30   # avatar width as fraction of frame width
AVATAR_MARGIN_X = 48
AVATAR_BOTTOM_OFFSET = 180  # px above bottom edge
TEXT_OVERLAY_Y_FRAC = 0.14  # top of text overlay zone
CAPTION_Y_FRAC = 0.66       # caption band top (above avatar, below text)
KINETIC_REVEAL_MAX_SEC = 2.2
CAPTION_MAX_WORDS = 6
DEFAULT_CUT_SEC = 2.5
BROLL_HEIGHT = 1080
SUBPROCESS_TIMEOUT = 240
FFMPEG_TIMEOUT = 600

# Pause inserted between beats in the teleprompter; the batch narration
# splitter looks for silences of at least this length.
SPLIT_SILENCE_SEC = 1.5


class AssemblyError(RuntimeError):
    """Raised when a render step fails; message carries ffmpeg stderr tail."""


# ══════════════════════════════════════════════════════════════════════════
# Pure logic (no subprocess, no PIL) — unit-tested directly
# ══════════════════════════════════════════════════════════════════════════

TIME_RANGE_RE = re.compile(r"^(\d+):(\d{2})-(\d+):(\d{2})$")


def parse_time_range(time_range: str) -> tuple[float, float]:
    """'0:05-0:10' -> (5.0, 10.0). Raises ValueError on bad input."""
    m = TIME_RANGE_RE.match(time_range or "")
    if not m:
        raise ValueError(f"bad time_range: {time_range!r}")
    start = int(m.group(1)) * 60 + int(m.group(2))
    end = int(m.group(3)) * 60 + int(m.group(4))
    if end <= start:
        raise ValueError(f"time_range end <= start: {time_range!r}")
    return float(start), float(end)


def beat_bounds(beat: dict) -> tuple[float, float]:
    """(start, end) seconds for a beat. Pass 2 re-timing stores fractional
    bounds in '_bounds' (time_range can't carry sub-second precision);
    Pass 1 beats fall back to parsing time_range."""
    bounds = beat.get("_bounds")
    if bounds:
        return float(bounds[0]), float(bounds[1])
    return parse_time_range(beat["time_range"])


def parse_tier(value) -> int:
    """'T1' | '1' | 1 -> 1. Raises ValueError otherwise."""
    s = str(value).strip().upper().lstrip("T")
    tier = int(s)
    if tier not in (1, 2, 3, 4):
        raise ValueError(f"bad tier: {value!r}")
    return tier


def beat_cut_plan(beat: dict) -> list[float]:
    """Cut durations for a beat honoring cut_frequency_sec.

    evidence_data overrides the count: one cut per dimension card.
    Durations sum exactly to the beat duration.
    """
    start, end = beat_bounds(beat)
    duration = end - start
    freq_range = beat.get("cut_frequency_sec") or [DEFAULT_CUT_SEC, DEFAULT_CUT_SEC]
    freq = (freq_range[0] + freq_range[1]) / 2
    evidence = beat.get("evidence_data") or []
    if evidence:
        n = len(evidence)
    else:
        n = max(1, round(duration / freq))
    base = duration / n
    cuts = [round(base, 3)] * (n - 1)
    cuts.append(round(duration - sum(cuts), 3))
    return cuts


def chunk_caption_words(text: str, max_words: int = CAPTION_MAX_WORDS) -> list[str]:
    """Split narration into caption-sized chunks, breaking at sentence ends
    when possible."""
    words = (text or "").split()
    if not words:
        return []
    chunks = []
    current: list[str] = []
    for word in words:
        current.append(word)
        sentence_end = word.endswith((".", "!", "?"))
        if len(current) >= max_words or (sentence_end and len(current) >= 3):
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


def srt_timestamp(seconds: float) -> str:
    """73.25 -> '00:01:13,250'"""
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(cues: list[tuple[float, float, str]]) -> str:
    """cues: [(start_sec, end_sec, text)] -> SRT file content."""
    blocks = []
    for i, (start, end, text) in enumerate(cues, 1):
        blocks.append(
            f"{i}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n{text}\n"
        )
    return "\n".join(blocks)


def draft_caption_cues(beats: list[dict]) -> list[tuple[float, float, str]]:
    """Estimate caption cues from beat narration, proportional to word count
    within each beat's time range. Used for the Pass 1 draft SRT.

    The hook beat gets no captions: its kinetic text IS the narration and
    a caption would duplicate it on screen."""
    cues = []
    for beat in beats:
        if beat.get("id") == "hook":
            continue
        start, end = beat_bounds(beat)
        chunks = chunk_caption_words(beat.get("narration", ""))
        if not chunks:
            continue
        total_words = sum(len(c.split()) for c in chunks)
        usable = (end - start) - 0.15  # breathe before the next beat
        t = start
        for chunk in chunks:
            dur = usable * len(chunk.split()) / total_words
            cues.append((round(t, 3), round(t + dur, 3), chunk))
            t += dur
    return cues


def word_reveal_schedule(text: str, beat_start: float,
                         beat_duration: float) -> list[tuple[str, float]]:
    """Kinetic typography: (cumulative_text, appear_time) per word.
    Reveal completes within KINETIC_REVEAL_MAX_SEC or 60% of the beat."""
    words = (text or "").split()
    if not words:
        return []
    window = min(KINETIC_REVEAL_MAX_SEC, beat_duration * 0.6)
    step = window / len(words)
    schedule = []
    for i in range(len(words)):
        cumulative = " ".join(words[: i + 1])
        schedule.append((cumulative, round(beat_start + i * step, 3)))
    return schedule


def ducking_envelope(beats: list[dict]) -> list[dict]:
    """Per-beat music gain spec. volume_db ranges are negative (dB below
    full scale); we take the midpoint."""
    envelope = []
    for beat in beats:
        start, end = beat_bounds(beat)
        db_range = beat.get("volume_db") or [-20, -20]
        target_db = (db_range[0] + db_range[1]) / 2
        envelope.append({
            "beat": beat.get("id", "?"),
            "start": start,
            "end": end,
            "volume_db_range": db_range,
            "target_db": round(target_db, 1),
            "music_bpm": beat.get("music_bpm"),
        })
    return envelope


def envelope_volume_expr(envelope: list[dict]) -> str:
    """ffmpeg volume= expression (linear amplitude) from a ducking envelope.
    Piecewise constant per beat; evaluated per-frame."""
    expr = "0"
    for seg in reversed(envelope):
        amplitude = 10 ** (seg["target_db"] / 20)
        expr = (f"if(between(t,{seg['start']},{seg['end']}),"
                f"{amplitude:.4f},{expr})")
    return expr


BPM_FILE_RE = re.compile(r"(\d{2,3})\s*bpm", re.IGNORECASE)


def pick_music_track(beats: list[dict], music_dir: Path) -> Path | None:
    """Pick one track for the whole video whose filename BPM tag best fits
    the hook beat's music_bpm range. Files: assets/music/*-128bpm.mp3 etc.
    Returns None when no tagged tracks exist (silent bed + sidecar only)."""
    if not music_dir.is_dir():
        return None
    candidates = []
    for f in sorted(music_dir.iterdir()):
        if f.suffix.lower() not in (".mp3", ".m4a", ".wav", ".flac"):
            continue
        m = BPM_FILE_RE.search(f.name)
        if m:
            candidates.append((int(m.group(1)), f))
    if not candidates:
        return None
    hook = beats[0] if beats else {}
    lo, hi = (hook.get("music_bpm") or [100, 120])
    mid = (lo + hi) / 2
    in_range = [(bpm, f) for bpm, f in candidates if lo <= bpm <= hi]
    pool = in_range or candidates
    pool.sort(key=lambda item: abs(item[0] - mid))
    return pool[0][1]


RIFF_RE = re.compile(r"\[RIFF HERE\]", re.IGNORECASE)


def build_teleprompter(brief: dict) -> str:
    """Narration kit markdown: lines per beat, target WPM, pause markers,
    [RIFF HERE] preserved. Pause markers double as batch-split boundaries."""
    feas = brief.get("narration_feasibility", {})
    lines = [
        f"# {brief['race_name']} — {brief['format']} narration kit",
        "",
        f"Total target: {brief.get('estimated_duration_sec', '?')}s, "
        f"{feas.get('total_words', '?')} words, "
        f"{feas.get('overall_wpm', '?')} WPM overall.",
        "",
        "Recording notes:",
        f"- Leave a clear **{SPLIT_SILENCE_SEC}s pause** at every PAUSE marker "
        "— the batch splitter cuts on these silences.",
        "- Deadpan. Specific numbers. Do not perform enthusiasm.",
        "- A riff marker means: one unscripted line in voice, then move on.",
        "",
    ]
    warnings = feas.get("warnings") or []
    if warnings:
        lines.append("**Feasibility warnings:**")
        lines.extend(f"- {w}" for w in warnings)
        lines.append("")
    for i, beat in enumerate(brief.get("beats", []), 1):
        wpm = beat.get("narration_wpm")
        wpm_note = f" — target {wpm:.0f} WPM" if wpm else ""
        flag = ""
        if wpm and wpm > 160:
            flag = "  ⚠ fast: tighten or trim words"
        lines.append(
            f"## {i}. {beat.get('label', beat.get('id', '?'))} "
            f"({beat.get('time_range', '?')}){wpm_note}{flag}"
        )
        lines.append("")
        lines.append(f"> {beat.get('narration', '').strip()}")
        lines.append("")
        note = beat.get("editing_note", "")
        if RIFF_RE.search(note):
            lines.append("**[RIFF HERE]** — one unscripted line, in voice.")
            lines.append("")
        if i < len(brief.get("beats", [])):
            lines.append(f"--- PAUSE {SPLIT_SILENCE_SEC}s ---")
            lines.append("")
    return "\n".join(lines)


def resolve_avatar(pose: str) -> dict:
    """Asset fallback chain: motion loop -> static PNG -> placeholder.

    Loops with an alpha channel (.mov / .webm) are preferred over .mp4.
    Returns {"kind": "loop"|"png"|"placeholder", "path": Path|None}.
    """
    pose = (pose or "neutral").strip()
    for ext in (".mov", ".webm", ".mp4"):
        loop = LOOPS_DIR / f"{pose}{ext}"
        if loop.exists():
            return {"kind": "loop", "path": loop, "pose": pose}
    png = AVATAR_DIR / f"{pose}.png"
    if png.exists():
        return {"kind": "png", "path": png, "pose": pose}
    return {"kind": "placeholder", "path": None, "pose": pose}


def resolution_for_format(fmt: str) -> tuple[int, int]:
    return RES_SHORT if fmt in SHORT_FORMATS else RES_LONG


# ══════════════════════════════════════════════════════════════════════════
# PIL rendering — branded data-cards, text overlays, placeholder avatar
# ══════════════════════════════════════════════════════════════════════════

_FONT_CACHE: dict = {}


def _font(path: Path, size: int, variation: str | None = None):
    from PIL import ImageFont
    key = (str(path), size, variation)
    if key not in _FONT_CACHE:
        font = ImageFont.truetype(str(path), size)
        if variation:
            try:
                font.set_variation_by_name(variation)
            except (OSError, AttributeError):
                pass
        _FONT_CACHE[key] = font
    return _FONT_CACHE[key]


def mono(size: int):
    return _font(FONT_MONO, size)


def mono_bold(size: int):
    return _font(FONT_MONO_BOLD, size)


def serif(size: int, bold: bool = False):
    return _font(FONT_SERIF, size, "Bold" if bold else None)


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    """Greedy word wrap by rendered width."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _frame_border(draw, size: tuple[int, int], color: str, width: int = 3,
                  inset: int = 40):
    w, h = size
    for i in range(width):
        draw.rectangle([inset + i, inset + i, w - inset - i, h - inset - i],
                       outline=color)


def render_text_overlay(text: str, frame_width: int) -> "object":
    """Neo-brutalist text block: near-black box, warm-paper text, 3px border.
    Returns an RGBA PIL image sized to content (caller positions it)."""
    from PIL import Image, ImageDraw
    max_text_width = int(frame_width * 0.8) - 72
    probe = Image.new("RGBA", (8, 8))
    pdraw = ImageDraw.Draw(probe)
    font = mono_bold(56)
    lines = _wrap(pdraw, text, font, max_text_width)
    line_h = 72
    pad = 36
    width = max(int(pdraw.textlength(ln, font=font)) for ln in lines) + pad * 2
    height = line_h * len(lines) + pad * 2
    img = Image.new("RGBA", (width, height), COLORS["near_black"])
    draw = ImageDraw.Draw(img)
    for i in range(3):
        draw.rectangle([i, i, width - 1 - i, height - 1 - i],
                       outline=COLORS["warm_paper"])
    y = pad
    for ln in lines:
        draw.text((pad, y), ln, font=font, fill=COLORS["warm_paper"])
        y += line_h
    return img


def render_placeholder_avatar(pose: str, cache_dir: Path = PLACEHOLDER_DIR) -> Path:
    """Labeled placeholder so rough cuts read correctly before real art
    lands: tan box, dashed near-black border, pose name in mono."""
    from PIL import Image, ImageDraw
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{pose}.png"
    if out.exists():
        return out
    size = 600
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([6, 6, size - 6, size - 6], fill=COLORS["tan"])
    dash, gap = 24, 14
    step = dash + gap
    for x in range(6, size - 6, step):
        draw.line([(x, 6), (min(x + dash, size - 6), 6)], fill=COLORS["near_black"], width=6)
        draw.line([(x, size - 8), (min(x + dash, size - 6), size - 8)], fill=COLORS["near_black"], width=6)
    for y in range(6, size - 6, step):
        draw.line([(6, y), (6, min(y + dash, size - 6))], fill=COLORS["near_black"], width=6)
        draw.line([(size - 8, y), (size - 8, min(y + dash, size - 6))], fill=COLORS["near_black"], width=6)
    label_font = mono(40)
    pose_font = mono_bold(52)
    draw.text((size / 2, size / 2 - 48), "AVATAR", font=label_font,
              fill=COLORS["near_black"], anchor="mm")
    draw.text((size / 2, size / 2 + 24), pose.upper(), font=pose_font,
              fill=COLORS["near_black"], anchor="mm")
    img.save(out)
    return out


def _new_card(size: tuple[int, int], bg: str):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", size, bg)
    return img, ImageDraw.Draw(img)


def render_card_hook(brief: dict, size: tuple[int, int]):
    """Hook background: near-black field, thin warm-paper frame, brand mark.
    The kinetic text overlay carries the message."""
    img, draw = _new_card(size, COLORS["near_black"])
    _frame_border(draw, size, COLORS["warm_paper"], width=3, inset=44)
    w, h = size
    draw.text((w / 2, 110), "G R A V E L   G O D", font=mono(34),
              fill=COLORS["warm_paper"], anchor="mm")
    draw.text((w / 2, h - 110), "RACE INTEL, SCORED.", font=mono(28),
              fill=COLORS["tan"], anchor="mm")
    return img


def render_card_setup(brief: dict, size: tuple[int, int]):
    """Race card: name, location, scoring tease."""
    img, draw = _new_card(size, COLORS["warm_paper"])
    _frame_border(draw, size, COLORS["near_black"], width=3, inset=44)
    w, h = size
    name_font = serif(96, bold=True)
    lines = _wrap(draw, brief["race_name"], name_font, w - 220)
    y = h * 0.30
    for ln in lines:
        draw.text((w / 2, y), ln, font=name_font,
                  fill=COLORS["near_black"], anchor="mm")
        y += 112
    location = ""
    setup = next((b for b in brief.get("beats", []) if b.get("id") == "setup"), {})
    text = setup.get("text_on_screen", "")
    if "|" in text:
        location = text.split("|", 1)[1].strip()
    if location:
        y += 30
        draw.text((w / 2, y), location.upper(), font=mono(40),
                  fill=COLORS["secondary_brown"], anchor="mm")
        y += 90
    # stays above the caption band (CAPTION_Y_FRAC) and the avatar zone
    draw.text((w / 2, h * 0.575), "SCORED ON 15 DIMENSIONS",
              font=mono(32), fill=COLORS["near_black"], anchor="mm")
    bar_w, bar_h, gap = 52, 18, 12
    total = 15 * bar_w + 14 * gap
    x0 = (w - total) / 2
    for i in range(15):
        x = x0 + i * (bar_w + gap)
        draw.rectangle([x, h * 0.575 + 44, x + bar_w, h * 0.575 + 44 + bar_h],
                       fill=COLORS["near_black"])
    return img


def render_card_evidence(dim: dict, size: tuple[int, int]):
    """One dimension score card. Von Restorff: extreme scores (5 or 1) get
    a gold border flash instead of near-black."""
    img, draw = _new_card(size, COLORS["warm_paper"])
    w, h = size
    score = dim.get("score", 0)
    max_score = dim.get("max", 5)
    extreme = score in (max_score, 1)
    border = COLORS["gold"] if extreme else COLORS["near_black"]
    _frame_border(draw, size, border, width=6 if extreme else 3, inset=44)
    draw.text((w / 2, h * 0.30), dim.get("dimension", "?").upper(),
              font=mono_bold(64), fill=COLORS["near_black"], anchor="mm")
    draw.text((w / 2, h * 0.45), f"{score}/{max_score}",
              font=serif(220, bold=True),
              fill=COLORS["gold"] if extreme else COLORS["near_black"],
              anchor="mm")
    block, gap = 120, 24
    total = max_score * block + (max_score - 1) * gap
    x0 = (w - total) / 2
    y0 = h * 0.58
    for i in range(max_score):
        x = x0 + i * (block + gap)
        box = [x, y0, x + block, y0 + 56]
        if i < score:
            draw.rectangle(box, fill=COLORS["near_black"])
        else:
            draw.rectangle(box, outline=COLORS["near_black"], width=4)
    return img


def render_card_reveal(brief: dict, size: tuple[int, int]):
    """Tier badge card on the tier color."""
    tier = parse_tier(brief.get("race_tier", 4))
    img, draw = _new_card(size, COLORS[f"tier_{tier}"])
    w, h = size
    _frame_border(draw, size, COLORS["warm_paper"], width=3, inset=44)
    # name on top so the caption band can't cover it
    name_font = serif(54, bold=True)
    lines = _wrap(draw, brief["race_name"], name_font, w - 260)
    y = h * 0.16
    for ln in lines:
        draw.text((w / 2, y), ln, font=name_font,
                  fill=COLORS["warm_paper"], anchor="mm")
        y += 64
    draw.text((w / 2, h * 0.32), f"TIER {tier}", font=mono_bold(72),
              fill=COLORS["warm_paper"], anchor="mm")
    draw.text((w / 2, h * 0.39), TIER_NAMES.get(tier, "").upper(),
              font=mono(44), fill=COLORS["tan"], anchor="mm")
    draw.text((w / 2, h * 0.52), f"{brief.get('race_score', '?')}/100",
              font=serif(230, bold=True), fill=COLORS["warm_paper"],
              anchor="mm")
    return img


def render_card_cta(brief: dict, size: tuple[int, int]):
    """CTA card. Bottom band echoes the hook card (near-black field +
    brand mark) so the loop point reads seamless on replay."""
    img, draw = _new_card(size, COLORS["warm_paper"])
    w, h = size
    _frame_border(draw, size, COLORS["near_black"], width=3, inset=44)
    cta = next((b for b in brief.get("beats", []) if b.get("id") == "cta"), {})
    url = cta.get("text_on_screen",
                  f"gravelgodcycling.com/race/{brief['slug']}")
    url_font = mono_bold(40)
    while draw.textlength(url, font=url_font) > w - 240 and url_font.size > 24:
        url_font = mono_bold(url_font.size - 4)
    pad = 36
    box_w = draw.textlength(url, font=url_font) + pad * 2
    box_h = url_font.size + pad * 2
    # no headline label: the narration caption ("Full breakdown. Free prep
    # kit.") carries that line — printing it twice reads like a mistake
    x0, y0 = (w - box_w) / 2, h * 0.26
    draw.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=COLORS["near_black"])
    draw.text((w / 2, y0 + box_h / 2), url, font=url_font,
              fill=COLORS["warm_paper"], anchor="mm")
    question = cta.get("engagement_question", "")
    if question:
        q_font = serif(52)
        lines = _wrap(draw, question, q_font, w - 280)
        y = h * 0.52
        for ln in lines:
            draw.text((w / 2, y), ln, font=q_font,
                      fill=COLORS["primary_brown"], anchor="mm")
            y += 66
    band_top = int(h * 0.80)
    draw.rectangle([47, band_top, w - 47, h - 47], fill=COLORS["near_black"])
    draw.text((w / 2, band_top + (h - 47 - band_top) / 2),
              "G R A V E L   G O D", font=mono(34),
              fill=COLORS["warm_paper"], anchor="mm")
    return img


def render_card(beat: dict, brief: dict, size: tuple[int, int],
                cut_index: int = 0):
    """Dispatch a branded card for a beat (used when no B-roll applies)."""
    beat_id = beat.get("id", "")
    evidence = beat.get("evidence_data") or []
    if evidence:
        return render_card_evidence(evidence[min(cut_index, len(evidence) - 1)], size)
    if beat_id == "hook":
        return render_card_hook(brief, size)
    if beat_id == "setup":
        return render_card_setup(brief, size)
    if beat_id == "reveal":
        return render_card_reveal(brief, size)
    if beat_id == "cta":
        return render_card_cta(brief, size)
    return render_card_setup(brief, size)


# ══════════════════════════════════════════════════════════════════════════
# B-roll sourcing (curated youtube_data.videos[] only — constraint 6)
# ══════════════════════════════════════════════════════════════════════════

def load_race(slug: str) -> dict:
    """Race profile dict. Profiles nest everything under a top-level 'race'
    key (d['race']['youtube_data'], per CLAUDE.md) — unwrap it."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)
    return data.get("race", data)


def broll_videos_for_race(race: dict, max_videos: int = 3) -> list[dict]:
    """Curated videos eligible as B-roll sources (reuses the screenshot
    pipeline's selection: curated first, 3min-2hr, by views)."""
    from youtube_screenshots import select_videos
    return select_videos(race, max_videos=max_videos)


def broll_timestamps(videos: list[dict], n_cuts: int) -> list[dict]:
    """Spread n_cuts sample points across the usable middle (15%-85%) of the
    available videos, rotating between videos for variety."""
    from youtube_screenshots import parse_duration_seconds
    if not videos or n_cuts <= 0:
        return []
    plan = []
    for i in range(n_cuts):
        video = videos[i % len(videos)]
        dur = parse_duration_seconds(video.get("duration_string", ""))
        if dur <= 30:
            continue
        # walk through the usable window as cuts progress
        pct = 0.15 + 0.70 * ((i // len(videos)) * len(videos) + (i % len(videos))) / max(n_cuts, 1)
        plan.append({
            "video_id": video.get("video_id", ""),
            "timestamp": int(dur * min(pct, 0.85)),
        })
    return plan


def download_broll_segment(video_id: str, timestamp: int, duration: float,
                           cache_dir: Path = BROLL_CACHE) -> Path | None:
    """Download a video-only segment with yt-dlp, cached on disk.
    Mirrors youtube_screenshots.download_segment but with variable length."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    dur_key = int(math.ceil(duration))
    cached = list(cache_dir.glob(f"{video_id}_{timestamp}_{dur_key}.*"))
    if cached:
        return cached[0]
    out_template = str(cache_dir / f"{video_id}_{timestamp}_{dur_key}.%(ext)s")
    cmd = [
        "yt-dlp",
        f"https://www.youtube.com/watch?v={video_id}",
        "--download-sections", f"*{timestamp}-{timestamp + dur_key + 1}",
        "-f", f"bestvideo[height<={BROLL_HEIGHT}]/best[height<={BROLL_HEIGHT}]",
        "--no-audio",
        "-o", out_template,
        "--no-warnings", "--quiet",
    ]
    try:
        subprocess.run(cmd, timeout=SUBPROCESS_TIMEOUT, check=True,
                       capture_output=True, text=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return None
    for f in cache_dir.glob(f"{video_id}_{timestamp}_{dur_key}.*"):
        if f.suffix in (".mp4", ".webm", ".mkv"):
            return f
    return None


# ══════════════════════════════════════════════════════════════════════════
# ffmpeg assembly
# ══════════════════════════════════════════════════════════════════════════

def run_ffmpeg(args: list[str], timeout: int = FFMPEG_TIMEOUT) -> None:
    # cwd is pinned so relative paths inside filtergraphs (subtitles=,
    # fontsdir=) resolve regardless of where the CLI was launched from.
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y"] + args
    try:
        subprocess.run(cmd, timeout=timeout, check=True,
                       capture_output=True, text=True, cwd=PROJECT_ROOT)
    except subprocess.CalledProcessError as e:
        # drop \r-progress lines so the real error survives the tail
        lines = [ln for ln in (e.stderr or "").replace("\r", "\n").splitlines()
                 if ln.strip() and not ln.startswith(("frame=", "size="))]
        tail = "\n".join(lines[-25:])
        raise AssemblyError(f"ffmpeg failed: {' '.join(cmd[:8])}...\n{tail}") from e
    except subprocess.TimeoutExpired as e:
        raise AssemblyError(f"ffmpeg timed out after {timeout}s") from e


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def probe_resolution(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    try:
        w, h = out.stdout.strip().split("\n")[0].split(",")[:2]
        return int(w), int(h)
    except (ValueError, IndexError):
        return (0, 0)


VIDEO_ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
             "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
             # uniform color tags: B-roll (bt709) and PIL cards (untagged)
             # must produce identical streams or concat breaks downstream
             "-colorspace", "bt709", "-color_primaries", "bt709",
             "-color_trc", "bt709"]


def _cover_filter(width: int, height: int) -> str:
    """Scale-to-cover + center-crop + fps + sar normalize."""
    return (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={FPS},setsar=1")


def card_to_clip(card_path: Path, duration: float, size: tuple[int, int],
                 out_path: Path) -> Path:
    """Still card -> clip with a slow Ken Burns push (zoom 1.0 -> ~1.06).
    Card is pre-rendered at 2x and zoompan output downsamples, which avoids
    the classic single-pixel zoompan jitter."""
    w, h = size
    frames = max(int(duration * FPS), 1)
    zoom_per_frame = 0.06 / frames
    vf = (f"scale={w * 2}:{h * 2},"
          f"zoompan=z='1+{zoom_per_frame:.6f}*in':d=1:"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"s={w}x{h}:fps={FPS},setsar=1")
    run_ffmpeg(["-loop", "1", "-framerate", str(FPS), "-i", str(card_path),
                "-t", f"{duration:.3f}", "-vf", vf] + VIDEO_ENC + [str(out_path)])
    return out_path


def segment_to_clip(segment_path: Path, duration: float,
                    size: tuple[int, int], out_path: Path) -> Path:
    """Normalize a downloaded B-roll segment to the target frame."""
    w, h = size
    run_ffmpeg(["-i", str(segment_path), "-t", f"{duration:.3f}",
                "-vf", _cover_filter(w, h)] + VIDEO_ENC + [str(out_path)])
    return out_path


def concat_clips(clips: list[Path], out_path: Path) -> Path:
    """Concat clips via the concat demuxer, re-encoding to guarantee one
    uniform stream (mixed card/B-roll sources make -c copy fragile)."""
    list_file = out_path.with_suffix(".txt")
    list_file.write_text(
        "".join(f"file '{c.resolve()}'\n" for c in clips)
    )
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file),
                "-vf", f"fps={FPS},setsar=1"] + VIDEO_ENC + [str(out_path)])
    return out_path


def build_beat_background(beat: dict, brief: dict, size: tuple[int, int],
                          tmp: Path, use_broll: bool,
                          race: dict) -> tuple[Path, dict]:
    """Background track for one beat: B-roll cuts when the beat asks for
    real footage and curated videos exist; branded cards otherwise.
    Returns (path, info) where info reports what was used."""
    cuts = beat_cut_plan(beat)
    beat_id = beat.get("id", "beat")
    info = {"beat": beat_id, "source": "cards", "cuts": len(cuts)}

    wants_broll = bool(beat.get("broll_sources")) and not beat.get("evidence_data")
    clips: list[Path] = []
    if use_broll and wants_broll:
        videos = broll_videos_for_race(race)
        plan = broll_timestamps(videos, len(cuts))
        for i, (cut_dur, sample) in enumerate(zip(cuts, plan)):
            seg = download_broll_segment(sample["video_id"],
                                         sample["timestamp"], cut_dur)
            if not seg:
                break
            clips.append(segment_to_clip(
                seg, cut_dur, size, tmp / f"{beat_id}_broll{i}.mp4"))
        if len(clips) == len(cuts):
            info["source"] = "broll"
            info["video_ids"] = [p["video_id"] for p in plan]
        else:
            clips = []  # all-or-nothing per beat: partial B-roll falls back to cards

    if not clips:
        for i, cut_dur in enumerate(cuts):
            card = render_card(beat, brief, size, cut_index=i)
            card_path = tmp / f"{beat_id}_card{i}.png"
            card.save(card_path)
            clips.append(card_to_clip(card_path, cut_dur, size,
                                      tmp / f"{beat_id}_card{i}.mp4"))

    if len(clips) == 1:
        return clips[0], info
    return concat_clips(clips, tmp / f"{beat_id}_bg.mp4"), info


def _beat_shows_overlay_text(beat: dict, bg_source: str) -> bool:
    """Cards already display their info; overlay text would duplicate it.
    Show the text_on_screen overlay on the hook (kinetic) and over B-roll."""
    if beat.get("id") == "hook":
        return True
    return bg_source == "broll"


def render_beat(beat: dict, brief: dict, size: tuple[int, int], tmp: Path,
                use_broll: bool, race: dict) -> tuple[Path, dict]:
    """Compose one beat: background + avatar layer + text overlays."""
    start, end = beat_bounds(beat)
    duration = end - start
    beat_id = beat.get("id", "beat")
    w, h = size

    bg_path, info = build_beat_background(beat, brief, size, tmp,
                                          use_broll, race)

    inputs = ["-i", str(bg_path)]
    filters = []
    last = "[0:v]"
    input_idx = 1

    # ── avatar layer (loop -> png -> placeholder) ──
    avatar = resolve_avatar(beat.get("avatar_pose", ""))
    info["avatar"] = {"pose": avatar["pose"], "kind": avatar["kind"]}
    avatar_w = int(w * AVATAR_WIDTH_FRAC)
    if avatar["kind"] == "loop":
        inputs += ["-stream_loop", "-1", "-i", str(avatar["path"])]
        if avatar["path"].suffix == ".mp4":
            # mp4 loops carry no alpha; generate_avatar_poses.py renders
            # them on solid green, keyed out here
            filters.append(
                f"[{input_idx}:v]colorkey=0x00FF00:0.30:0.08,"
                f"despill=type=green,scale={avatar_w}:-1[av]")
        else:
            filters.append(f"[{input_idx}:v]scale={avatar_w}:-1[av]")
    else:
        path = avatar["path"] or render_placeholder_avatar(avatar["pose"])
        inputs += ["-loop", "1", "-i", str(path)]
        filters.append(f"[{input_idx}:v]scale={avatar_w}:-1[av]")
    filters.append(
        f"{last}[av]overlay=x={AVATAR_MARGIN_X}:"
        f"y=H-h-{AVATAR_BOTTOM_OFFSET}:shortest=0[v{input_idx}]"
    )
    last = f"[v{input_idx}]"
    input_idx += 1

    # ── text overlays ──
    text = (beat.get("text_on_screen") or "").strip()
    kinetic = beat_id == "hook"
    if text and _beat_shows_overlay_text(beat, info["source"]):
        text_y = int(h * TEXT_OVERLAY_Y_FRAC)
        if kinetic:
            schedule = word_reveal_schedule(text, 0.0, duration)
            for j, (cumulative, t_on) in enumerate(schedule):
                img = render_text_overlay(cumulative, w)
                p = tmp / f"{beat_id}_txt{j}.png"
                img.save(p)
                t_off = (schedule[j + 1][1] if j + 1 < len(schedule)
                         else duration)
                inputs += ["-loop", "1", "-i", str(p)]
                filters.append(
                    f"{last}[{input_idx}:v]overlay=x=(W-w)/2:y={text_y}:"
                    f"enable='between(t,{t_on},{t_off})'[v{input_idx}]"
                )
                last = f"[v{input_idx}]"
                input_idx += 1
        else:
            img = render_text_overlay(text, w)
            p = tmp / f"{beat_id}_txt.png"
            img.save(p)
            inputs += ["-loop", "1", "-i", str(p)]
            filters.append(
                f"{last}[{input_idx}:v]overlay=x=(W-w)/2:y={text_y}:"
                f"enable='gte(t,0.2)'[v{input_idx}]"
            )
            last = f"[v{input_idx}]"
            input_idx += 1

    out_path = tmp / f"beat_{beat_id}.mp4"
    filtergraph = ";".join(filters)
    run_ffmpeg(inputs + ["-filter_complex", filtergraph,
                         "-map", last, "-t", f"{duration:.3f}"]
               + VIDEO_ENC + [str(out_path)])
    return out_path, info


def build_audio_graph(beats: list[dict], music_track: Path | None,
                      total_duration: float,
                      narration: Path | None = None,
                      start_idx: int = 1
                      ) -> tuple[list[str], list[str], str]:
    """Audio side of the final render.

    Returns (extra_inputs, filter_chains, audio_map_label). Chains are
    merged into the single -filter_complex alongside the caption burn.
    start_idx is the ffmpeg input index of the first audio input.
    """
    envelope = ducking_envelope(beats)
    if music_track is None and narration is None:
        # silent bed keeps players honest about duration
        return (["-f", "lavfi", "-t", f"{total_duration:.3f}",
                 "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"],
                [], f"{start_idx}:a")
    inputs: list[str] = []
    chains: list[str] = []
    mix_inputs = []
    idx = start_idx
    if music_track is not None:
        inputs += ["-stream_loop", "-1", "-i", str(music_track)]
        expr = envelope_volume_expr(envelope)
        chains.append(
            f"[{idx}:a]atrim=0:{total_duration:.3f},"
            f"volume='{expr}':eval=frame[music]"
        )
        mix_inputs.append("[music]")
        idx += 1
    if narration is not None:
        inputs += ["-i", str(narration)]
        # loudnorm: consistent voice level with true-peak headroom,
        # whatever the recording level was
        chains.append(
            f"[{idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,"
            f"apad,atrim=0:{total_duration:.3f}[voice]")
        mix_inputs.append("[voice]")
        idx += 1
    if len(mix_inputs) == 1:
        chains.append(f"{mix_inputs[0]}anull[aout]")
    else:
        chains.append(
            f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:"
            f"normalize=0[aout]"
        )
    return inputs, chains, "[aout]"


def render_caption_overlay(text: str, frame_width: int) -> "object":
    """Burned caption chunk: solid near-black box, warm-paper mono text.
    (This ffmpeg build has no libass/drawtext, so captions are PIL-rendered
    and overlaid with timed enable windows — which also guarantees brand
    typography instead of font substitution.)"""
    from PIL import Image, ImageDraw
    max_text_width = int(frame_width * 0.84) - 48
    probe = Image.new("RGBA", (8, 8))
    pdraw = ImageDraw.Draw(probe)
    font = mono_bold(44)
    lines = _wrap(pdraw, text, font, max_text_width)
    line_h = 58
    pad = 24
    width = max(int(pdraw.textlength(ln, font=font)) for ln in lines) + pad * 2
    height = line_h * len(lines) + pad * 2
    img = Image.new("RGBA", (width, height), COLORS["near_black"])
    draw = ImageDraw.Draw(img)
    y = pad
    for ln in lines:
        draw.text((width / 2, y + line_h / 2), ln, font=font,
                  fill=COLORS["warm_paper"], anchor="mm")
        y += line_h
    return img


def caption_overlay_graph(cues: list[tuple[float, float, str]],
                          size: tuple[int, int], tmp: Path,
                          first_input_idx: int
                          ) -> tuple[list[str], list[str], str]:
    """Build caption-burn inputs and filter chains for the final render.

    Returns (inputs, chains, last_video_label). Chains start from [0:v].
    """
    w, h = size
    caption_y = int(h * CAPTION_Y_FRAC)
    inputs: list[str] = []
    chains: list[str] = []
    last = "[0:v]"
    idx = first_input_idx
    for i, (start, end, text) in enumerate(cues):
        img = render_caption_overlay(text, w)
        png = tmp / f"caption_{i:03d}.png"
        img.save(png)
        inputs += ["-loop", "1", "-i", str(png)]
        out_label = f"[cap{i}]"
        chains.append(
            f"{last}[{idx}:v]overlay=x=(W-w)/2:y={caption_y}:"
            f"enable='between(t,{start},{end})'{out_label}"
        )
        last = out_label
        idx += 1
    return inputs, chains, last


# ══════════════════════════════════════════════════════════════════════════
# Orchestration
# ══════════════════════════════════════════════════════════════════════════

def load_brief(path: Path) -> dict:
    with open(path) as f:
        brief = json.load(f)
    for key in ("slug", "format", "race_name", "beats"):
        if key not in brief:
            raise AssemblyError(f"{path}: brief missing '{key}'")
    if not brief["beats"]:
        raise AssemblyError(f"{path}: brief has no beats")
    return brief


def assemble(brief_path: Path, *, use_broll: bool = True,
             music_dir: Path = MUSIC_DIR, narration: Path | None = None,
             output_root: Path = OUTPUT_DIR,
             keep_temp: bool = False) -> dict:
    """Assemble one brief into a rough cut + narration kit. Returns report."""
    brief = load_brief(brief_path)
    slug, fmt = brief["slug"], brief["format"]
    size = resolution_for_format(fmt)
    race = load_race(slug)
    out_dir = output_root / fmt / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    beats = brief["beats"]
    if narration is not None:
        from narration_align import retime_beats_to_narration
        beats, align_report = retime_beats_to_narration(brief, narration)
    else:
        align_report = None

    total_duration = beat_bounds(beats[-1])[1]

    # narration kit + envelope + draft captions (always emitted)
    teleprompter_path = out_dir / f"{slug}-teleprompter.md"
    teleprompter_path.write_text(build_teleprompter(brief))
    envelope = ducking_envelope(beats)
    envelope_path = out_dir / f"{slug}-envelope.json"
    envelope_path.write_text(json.dumps(envelope, indent=2))
    srt_path = out_dir / f"{slug}.srt"
    if align_report and align_report.get("cues"):
        cues = align_report["cues"]
    else:
        cues = draft_caption_cues(beats)
    srt_path.write_text(build_srt(cues))

    tmp_root = Path(tempfile.mkdtemp(prefix=f"assemble-{slug}-"))
    beat_infos = []
    try:
        beat_clips = []
        for beat in beats:
            clip, info = render_beat(beat, brief, size, tmp_root,
                                     use_broll, race)
            beat_clips.append(clip)
            beat_infos.append(info)
        body = concat_clips(beat_clips, tmp_root / "body.mp4")

        music = pick_music_track(beats, music_dir)
        cap_inputs, cap_chains, last_video = caption_overlay_graph(
            cues, size, tmp_root, first_input_idx=1)
        audio_inputs, audio_chains, audio_map = build_audio_graph(
            beats, music, total_duration, narration,
            start_idx=1 + len(cues))
        chains = cap_chains + audio_chains
        video_map = last_video.strip("[]") if last_video == "[0:v]" else last_video
        final_path = out_dir / f"{slug}-rough.mp4"
        cmd = ["-i", str(body)] + cap_inputs + audio_inputs
        if chains:
            cmd += ["-filter_complex", ";".join(chains)]
        cmd += ["-map", video_map, "-map", audio_map,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-t", f"{total_duration:.3f}",
                "-movflags", "+faststart", str(final_path)]
        run_ffmpeg(cmd)
    finally:
        if keep_temp:
            print(f"  temp kept: {tmp_root}")
        else:
            shutil.rmtree(tmp_root, ignore_errors=True)

    actual = probe_duration(final_path)
    width, height = probe_resolution(final_path)
    report = {
        "slug": slug,
        "format": fmt,
        "output": str(final_path.relative_to(PROJECT_ROOT)),
        "duration_sec": round(actual, 2),
        "duration_target_range": brief.get("duration_target_range"),
        "resolution": f"{width}x{height}",
        "beats": beat_infos,
        "music_track": str(music) if music else None,
        "narration": str(narration) if narration else None,
        "alignment": align_report,
        "placeholder_poses": sorted({
            i["avatar"]["pose"] for i in beat_infos
            if i.get("avatar", {}).get("kind") == "placeholder"
        }),
        "broll_beats": [i["beat"] for i in beat_infos
                        if i["source"] == "broll"],
    }
    report_path = out_dir / f"{slug}-report.json"
    report_path.write_text(json.dumps(report, indent=2))
    return report


def write_session_script(brief_paths: list[Path], out_dir: Path) -> Path:
    """One markdown script for a whole batch recording session: every
    race's teleprompter in assembly order, separated by the long-gap
    markers the WAV splitter cuts on."""
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = [
        "# Batch narration session script",
        "",
        f"{len(brief_paths)} takes, in this exact order. Within a take, "
        "pause 1.5s at PAUSE markers. **Between takes, stay silent for at "
        "least 3 seconds** — the splitter cuts on those gaps.",
        "",
    ]
    for i, path in enumerate(brief_paths, 1):
        try:
            brief = load_brief(path)
        except (AssemblyError, json.JSONDecodeError):
            continue
        parts.append(f"\n\n━━━ TAKE {i}/{len(brief_paths)} ━━━\n")
        parts.append(build_teleprompter(brief))
        if i < len(brief_paths):
            parts.append("\n**■ STOP. 3+ seconds of silence before the "
                         "next take. ■**")
    script_path = out_dir / "batch-session-script.md"
    script_path.write_text("\n".join(parts))
    return script_path


def find_briefs(fmt: str, tier: int | None) -> list[Path]:
    paths = sorted((BRIEFS_DIR / fmt).glob("*.json"))
    if tier is None:
        return paths
    selected = []
    for p in paths:
        try:
            with open(p) as f:
                brief = json.load(f)
            if parse_tier(brief.get("race_tier", 0)) == tier:
                selected.append(p)
        except (json.JSONDecodeError, ValueError):
            continue
    return selected


def main():
    parser = argparse.ArgumentParser(
        description="Assemble rough-cut videos from production briefs.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--brief", type=Path, help="Path to one brief JSON")
    source.add_argument("--batch", metavar="FORMAT",
                        help="Assemble all briefs of a format")
    parser.add_argument("--tier", help="With --batch: only this tier (T1..T4)")
    parser.add_argument("--narration", type=Path,
                        help="Recorded voice for Pass 2 re-timing + captions. "
                             "With --batch: one session WAV, split on the "
                             "teleprompter's long pauses (one take per video)")
    parser.add_argument("--batch-silence", type=float, default=2.5,
                        help="Min silence (s) separating takes in a "
                             "session recording (default 2.5)")
    parser.add_argument("--no-broll", action="store_true",
                        help="Skip YouTube B-roll (cards only, offline)")
    parser.add_argument("--music-dir", type=Path, default=MUSIC_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--limit", type=int, help="With --batch: stop after N")
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    if args.narration and not args.narration.exists():
        parser.error(f"narration file not found: {args.narration}")

    if args.brief:
        brief_paths = [args.brief]
    else:
        tier = parse_tier(args.tier) if args.tier else None
        brief_paths = find_briefs(args.batch, tier)
        if args.limit:
            brief_paths = brief_paths[: args.limit]
        if not brief_paths:
            print(f"No briefs found for format={args.batch} tier={args.tier}")
            sys.exit(1)

    # batch recording order is the sorted brief order; the session script
    # tells the narrator exactly what to read and where the long gaps go
    if args.batch and len(brief_paths) > 1:
        write_session_script(brief_paths, args.output_dir / args.batch)

    # batch narration: split the session WAV into one take per brief,
    # in the same (sorted) order the briefs are assembled
    narrations: list[Path | None] = [args.narration] * len(brief_paths)
    if args.batch and args.narration:
        from narration_align import split_batch_wav
        takes_dir = args.output_dir / args.batch / "narration-takes"
        narrations = list(split_batch_wav(
            args.narration, len(brief_paths), takes_dir,
            min_silence=args.batch_silence))
        print(f"Session WAV split into {len(narrations)} takes "
              f"→ {takes_dir}")

    results, failures = [], []
    for path, narration in zip(brief_paths, narrations):
        label = path.stem
        print(f"▸ {label}")
        try:
            report = assemble(
                path,
                use_broll=not args.no_broll,
                music_dir=args.music_dir,
                narration=narration,
                output_root=args.output_dir,
                keep_temp=args.keep_temp,
            )
            lo, hi = report.get("duration_target_range") or (0, 10 ** 6)
            in_range = lo <= report["duration_sec"] <= hi + 1
            flag = "" if in_range else "  ⚠ duration off-target"
            print(f"  ✓ {report['duration_sec']}s {report['resolution']} "
                  f"broll={len(report['broll_beats'])} "
                  f"placeholders={len(report['placeholder_poses'])}{flag}")
            results.append(report)
        except (AssemblyError, ValueError, OSError) as e:
            print(f"  ✗ {e}")
            failures.append({"brief": str(path), "error": str(e)})

    if args.batch:
        summary = {
            "format": args.batch,
            "tier": args.tier,
            "assembled": len(results),
            "failed": len(failures),
            "results": results,
            "failures": failures,
        }
        summary_path = args.output_dir / args.batch / "batch-report.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"\nBatch: {len(results)} assembled, {len(failures)} failed "
              f"→ {summary_path}")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
