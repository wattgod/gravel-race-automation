#!/usr/bin/env python3
"""Pass 2: re-time brief beats to a recorded human narration.

Pipeline:
1. Transcribe the narration with local whisper (mlx-whisper on Apple
   Silicon, openai-whisper fallback) with word-level timestamps.
2. Align transcript words to the brief's per-beat narration scripts
   (difflib sequence matching on normalized words — robust to riffs,
   re-reads and small wording drift).
3. Emit new fractional beat bounds ('_bounds', consumed by
   assemble_video.beat_bounds) plus whisper-aligned caption cues.

Also provides the batch narration flow: one long session WAV split on the
teleprompter's long-pause markers (silence detection), one segment per
video.

No TTS anywhere in this module — it only listens to the human voice.
"""
from __future__ import annotations

import difflib
import re
import subprocess
from pathlib import Path

# Tunables
WHISPER_MODEL_MLX = "mlx-community/whisper-base-mlx"
WHISPER_MODEL_OPENAI = "base"
CAPTION_MAX_WORDS = 6
CAPTION_GAP_SEC = 0.6        # pause that forces a caption break
TAIL_PAD_SEC = 0.8           # video continues briefly after the last word
MIN_BEAT_SEC = 1.0
BATCH_SILENCE_DB = -35
BATCH_SILENCE_SEC = 2.5      # between-video gap in a session recording


class AlignmentError(RuntimeError):
    pass


def transcribe_words(narration_path: Path) -> list[dict]:
    """Word-level transcript: [{'word', 'start', 'end'}, ...]."""
    try:
        import mlx_whisper
        result = mlx_whisper.transcribe(
            str(narration_path),
            path_or_hf_repo=WHISPER_MODEL_MLX,
            word_timestamps=True,
        )
    except ImportError:
        try:
            import whisper
        except ImportError as e:
            raise AlignmentError(
                "No whisper backend. Install one:\n"
                "  pip install mlx-whisper   (Apple Silicon, fast)\n"
                "  pip install openai-whisper"
            ) from e
        model = whisper.load_model(WHISPER_MODEL_OPENAI)
        result = model.transcribe(str(narration_path),
                                  word_timestamps=True)
    words = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            token = (w.get("word") or "").strip()
            if token:
                words.append({
                    "word": token,
                    "start": float(w["start"]),
                    "end": float(w["end"]),
                })
    if not words:
        raise AlignmentError(
            f"whisper produced no words for {narration_path}")
    return words


_NORM_RE = re.compile(r"[^a-z0-9]+")


def _norm(word: str) -> str:
    return _NORM_RE.sub("", word.lower())


def _script_word_spans(beats: list[dict]) -> tuple[list[str], list[tuple[int, int]]]:
    """Flatten beat narrations into one word list, recording each beat's
    [first, last] global word index span."""
    words: list[str] = []
    spans: list[tuple[int, int]] = []
    for beat in beats:
        tokens = (beat.get("narration") or "").split()
        start = len(words)
        words.extend(tokens)
        spans.append((start, len(words) - 1) if tokens else (start, start - 1))
    return words, spans


def align_beat_bounds(beats: list[dict],
                      transcript: list[dict]) -> tuple[list[tuple[float, float]], float]:
    """Map each beat to (start, end) seconds in the recording.

    Returns (bounds_per_beat, matched_ratio). Beats whose words found no
    match inherit interpolated bounds from their neighbors.
    """
    script_words, spans = _script_word_spans(beats)
    norm_script = [_norm(w) for w in script_words]
    norm_trans = [_norm(w["word"]) for w in transcript]

    matcher = difflib.SequenceMatcher(None, norm_script, norm_trans,
                                      autojunk=False)
    script_to_trans: dict[int, int] = {}
    for a, b, n in matcher.get_matching_blocks():
        for k in range(n):
            script_to_trans[a + k] = b + k
    matched_ratio = len(script_to_trans) / max(len(norm_script), 1)

    # raw timing per beat from matched words
    raw: list[tuple[float, float] | None] = []
    for lo, hi in spans:
        hits = [script_to_trans[j] for j in range(lo, hi + 1)
                if j in script_to_trans]
        if hits:
            raw.append((transcript[min(hits)]["start"],
                        transcript[max(hits)]["end"]))
        else:
            raw.append(None)

    # fill unmatched beats by interpolation between neighbors
    total_end = transcript[-1]["end"]
    for i, value in enumerate(raw):
        if value is not None:
            continue
        prev_end = next((raw[j][1] for j in range(i - 1, -1, -1)
                         if raw[j] is not None), 0.0)
        next_start = next((raw[j][0] for j in range(i + 1, len(raw))
                           if raw[j] is not None), total_end)
        raw[i] = (prev_end, max(next_start, prev_end + MIN_BEAT_SEC))

    # beat boundaries at the midpoint of inter-beat pauses; enforce
    # monotonic, minimum-length beats
    bounds: list[tuple[float, float]] = []
    for i, (start, end) in enumerate(raw):
        if i == 0:
            t0 = 0.0
        else:
            prev_end = raw[i - 1][1]
            t0 = max(bounds[i - 1][0] + MIN_BEAT_SEC,
                     (prev_end + start) / 2)
        bounds.append((round(t0, 3), 0.0))
    for i in range(len(bounds)):
        t1 = (bounds[i + 1][0] if i + 1 < len(bounds)
              else raw[-1][1] + TAIL_PAD_SEC)
        t1 = max(t1, bounds[i][0] + MIN_BEAT_SEC)
        bounds[i] = (bounds[i][0], round(t1, 3))

    return bounds, matched_ratio


def caption_cues_from_words(transcript: list[dict],
                            skip_windows: list[tuple[float, float]] | None = None
                            ) -> list[tuple[float, float, str]]:
    """Group whisper words into caption cues: break on chunk size, sentence
    punctuation, or audible pauses. Cues inside skip_windows are dropped
    (e.g. the hook beat, whose kinetic text already shows the words)."""
    skip_windows = skip_windows or []
    cues = []
    chunk: list[dict] = []

    def flush():
        if not chunk:
            return
        start = chunk[0]["start"]
        if cues:
            start = max(start, cues[-1][1])  # never overlap the previous cue
        end = max(chunk[-1]["end"] + 0.15, start + 0.3)
        mid = (start + end) / 2
        if not any(lo <= mid <= hi for lo, hi in skip_windows):
            text = " ".join(w["word"] for w in chunk)
            cues.append((round(start, 3), round(end, 3), text))
        chunk.clear()

    for i, word in enumerate(transcript):
        chunk.append(word)
        gap_break = (i + 1 < len(transcript)
                     and transcript[i + 1]["start"] - word["end"]
                     > CAPTION_GAP_SEC)
        sentence_break = (word["word"].rstrip().endswith((".", "!", "?"))
                          and len(chunk) >= 3)
        if len(chunk) >= CAPTION_MAX_WORDS or gap_break or sentence_break:
            flush()
    flush()
    return cues


def retime_beats_to_narration(brief: dict, narration_path: Path
                              ) -> tuple[list[dict], dict]:
    """Main Pass 2 entry: beats with '_bounds' + alignment report."""
    beats = [dict(b) for b in brief.get("beats", [])]
    transcript = transcribe_words(Path(narration_path))
    bounds, matched_ratio = align_beat_bounds(beats, transcript)
    for beat, (start, end) in zip(beats, bounds):
        beat["_bounds"] = [start, end]
    skip = [bounds[i] for i, b in enumerate(beats) if b.get("id") == "hook"]
    cues = caption_cues_from_words(transcript, skip_windows=skip)
    report = {
        "narration": str(narration_path),
        "matched_ratio": round(matched_ratio, 3),
        "beat_bounds": [{"id": b.get("id"), "start": s, "end": e}
                        for b, (s, e) in zip(beats, bounds)],
        "cues": cues,
        "transcript_words": len(transcript),
    }
    if matched_ratio < 0.5:
        report["warning"] = (
            f"only {matched_ratio:.0%} of script words matched the "
            "recording — check that the right WAV was paired with this brief")
    return beats, report


# ── batch session splitting ───────────────────────────────────────────────

_SILENCE_START_RE = re.compile(r"silence_start:\s*([\d.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([\d.]+)")


def detect_long_silences(wav_path: Path,
                         min_silence: float = BATCH_SILENCE_SEC,
                         noise_db: int = BATCH_SILENCE_DB
                         ) -> list[tuple[float, float]]:
    """(start, end) of every silence of at least min_silence seconds."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav_path),
         "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=600,
    )
    starts = [float(m) for m in _SILENCE_START_RE.findall(out.stderr or "")]
    ends = [float(m) for m in _SILENCE_END_RE.findall(out.stderr or "")]
    return list(zip(starts, ends))


def split_batch_wav(wav_path: Path, expected_segments: int,
                    out_dir: Path,
                    min_silence: float = BATCH_SILENCE_SEC) -> list[Path]:
    """Split one session recording into per-video narration files, cutting
    at the midpoint of each long silence (the teleprompter instructs a
    clear gap between videos). Raises when the count doesn't match."""
    wav_path = Path(wav_path)
    silences = detect_long_silences(wav_path, min_silence)
    # ignore leading/trailing room tone
    cut_points = [
        (s + e) / 2 for s, e in silences
        if s > 1.0
    ]
    if len(cut_points) != expected_segments - 1:
        raise AlignmentError(
            f"expected {expected_segments} takes but found "
            f"{len(cut_points) + 1} (silences >= {min_silence}s). "
            "Re-record with clearer gaps or adjust --batch-silence.")
    out_dir.mkdir(parents=True, exist_ok=True)
    edges = [0.0] + cut_points + [None]
    segments = []
    for i in range(expected_segments):
        seg_path = out_dir / f"{wav_path.stem}-take{i + 1:02d}.wav"
        cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y",
               "-i", str(wav_path), "-ss", f"{edges[i]:.3f}"]
        if edges[i + 1] is not None:
            cmd += ["-to", f"{edges[i + 1]:.3f}"]
        cmd += ["-c", "copy", str(seg_path)]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=300)
        if result.returncode != 0:
            raise AlignmentError(
                f"ffmpeg failed splitting take {i + 1}: "
                f"{(result.stderr or '')[-400:]}")
        segments.append(seg_path)
    return segments
