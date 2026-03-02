"""Tests for scripts/youtube_screenshots.py — frame extraction and scoring."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from PIL import Image, ImageDraw, ImageFilter

from youtube_screenshots import (
    parse_duration_seconds,
    compute_timestamps,
    select_videos,
    score_brightness,
    score_contrast,
    score_sharpness,
    score_nature_color,
    score_composition,
    score_frame,
    score_motion,
    is_black_frame,
    has_text_overlay,
    _has_bright_text_clusters,
    select_best_frames,
    select_best_gif_segments,
    build_photo_entries,
    merge_photos,
    _frame_similarity,
    get_tier_config,
    VALID_PHOTO_TYPES,
    HERO_PRIORITY,
    MIN_DURATION_SEC,
    MAX_DURATION_SEC,
    DEFAULT_TIER_CONFIG,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "race-data"


# ── Helpers ───────────────────────────────────────────────────


def _make_image(width=640, height=360, color=(128, 128, 128)):
    """Create a solid-color test image."""
    return Image.new("RGB", (width, height), color)


def _make_gradient_image(width=640, height=360):
    """Create a vertical gradient image (dark bottom, bright top)."""
    img = Image.new("RGB", (width, height))
    for y in range(height):
        val = int(255 * (1 - y / height))
        for x in range(width):
            img.putpixel((x, y), (val, val, val))
    return img


def _make_green_image(width=640, height=360):
    """Create a nature-green image."""
    return Image.new("RGB", (width, height), (60, 140, 50))


def _make_brown_image(width=640, height=360):
    """Create an earth-brown image."""
    return Image.new("RGB", (width, height), (150, 100, 60))


def _make_blue_image(width=640, height=360):
    """Create a sky-blue image."""
    return Image.new("RGB", (width, height), (100, 130, 220))


def _make_checkerboard(width=640, height=360, block=8):
    """Create a high-contrast checkerboard image."""
    img = Image.new("RGB", (width, height))
    for y in range(height):
        for x in range(width):
            val = 255 if ((x // block) + (y // block)) % 2 == 0 else 0
            img.putpixel((x, y), (val, val, val))
    return img


def _make_text_overlay_image(width=640, height=360):
    """Create an image with high edge density in top/bottom strips (simulates title card)."""
    img = Image.new("RGB", (width, height), (200, 200, 200))
    draw = ImageDraw.Draw(img)
    # Dense lines in top strip
    for y in range(0, height // 4, 3):
        for x in range(0, width, 4):
            draw.rectangle([x, y, x + 2, y + 1], fill=(0, 0, 0))
    # Dense lines in bottom strip
    for y in range(3 * height // 4, height, 3):
        for x in range(0, width, 4):
            draw.rectangle([x, y, x + 2, y + 1], fill=(0, 0, 0))
    return img


def _make_video(video_id="abc12345678", channel="Test Channel",
                duration="34:12", views=50000, curated=True, order=1):
    """Create a mock video dict."""
    return {
        "video_id": video_id,
        "title": f"Test Video {video_id}",
        "channel": channel,
        "view_count": views,
        "upload_date": "20250601",
        "duration_string": duration,
        "curated": curated,
        "curation_reason": "Test",
        "display_order": order,
    }


# ── Duration Parsing ──────────────────────────────────────────


class TestParseDurationSeconds:
    def test_mm_ss(self):
        assert parse_duration_seconds("34:12") == 2052

    def test_m_ss(self):
        assert parse_duration_seconds("2:34") == 154

    def test_h_mm_ss(self):
        assert parse_duration_seconds("1:34:12") == 5652

    def test_zero(self):
        assert parse_duration_seconds("0:00") == 0

    def test_empty_string(self):
        assert parse_duration_seconds("") == 0

    def test_none(self):
        assert parse_duration_seconds(None) == 0

    def test_non_string(self):
        assert parse_duration_seconds(123) == 0

    def test_invalid_format(self):
        assert parse_duration_seconds("abc") == 0

    def test_single_number(self):
        assert parse_duration_seconds("54") == 54

    def test_large_duration(self):
        assert parse_duration_seconds("2:30:00") == 9000


# ── Timestamp Computation ─────────────────────────────────────


class TestComputeTimestamps:
    def test_basic_timestamps(self):
        videos = [_make_video(duration="10:00")]  # 600s
        ts = compute_timestamps(videos)
        assert len(ts) == 5
        expected = [int(600 * p) for p in DEFAULT_TIER_CONFIG["sample_percents"]]
        actual = [t["timestamp"] for t in ts]
        assert actual == expected

    def test_two_videos(self):
        videos = [_make_video(video_id="vid1", duration="10:00"),
                  _make_video(video_id="vid2", duration="20:00")]
        ts = compute_timestamps(videos)
        assert len(ts) == 10

    def test_video_index_assigned(self):
        videos = [_make_video(video_id="vid1", duration="10:00"),
                  _make_video(video_id="vid2", duration="20:00")]
        ts = compute_timestamps(videos)
        v0_ts = [t for t in ts if t["video_index"] == 0]
        v1_ts = [t for t in ts if t["video_index"] == 1]
        assert len(v0_ts) == 5
        assert len(v1_ts) == 5

    def test_zero_duration(self):
        videos = [_make_video(duration="0:00")]
        assert compute_timestamps(videos) == []

    def test_empty_videos(self):
        assert compute_timestamps([]) == []

    def test_channel_preserved(self):
        videos = [_make_video(channel="Goettl Media", duration="10:00")]
        ts = compute_timestamps(videos)
        assert all(t["channel"] == "Goettl Media" for t in ts)


# ── Video Selection ───────────────────────────────────────────


class TestSelectVideos:
    def test_curated_preferred(self):
        race = {"youtube_data": {"videos": [
            _make_video(video_id="v1", curated=False, views=100000, duration="10:00"),
            _make_video(video_id="v2", curated=True, views=50000, duration="10:00"),
        ]}}
        selected = select_videos(race)
        assert selected[0]["video_id"] == "v2"

    def test_max_two_videos(self):
        race = {"youtube_data": {"videos": [
            _make_video(video_id=f"v{i}", duration="10:00")
            for i in range(5)
        ]}}
        selected = select_videos(race)
        assert len(selected) == 2

    def test_duration_filter_short(self):
        """Videos under 3 min are excluded."""
        race = {"youtube_data": {"videos": [
            _make_video(video_id="v1", duration="2:00"),  # 120s < 180s
            _make_video(video_id="v2", duration="10:00"),
        ]}}
        selected = select_videos(race)
        assert len(selected) == 1
        assert selected[0]["video_id"] == "v2"

    def test_duration_filter_long(self):
        """Videos over 2 hours are excluded."""
        race = {"youtube_data": {"videos": [
            _make_video(video_id="v1", duration="2:30:00"),  # 9000s > 7200s
            _make_video(video_id="v2", duration="10:00"),
        ]}}
        selected = select_videos(race)
        assert len(selected) == 1
        assert selected[0]["video_id"] == "v2"

    def test_no_videos(self):
        assert select_videos({}) == []
        assert select_videos({"youtube_data": {}}) == []
        assert select_videos({"youtube_data": {"videos": []}}) == []

    def test_view_count_sorting(self):
        race = {"youtube_data": {"videos": [
            _make_video(video_id="v1", curated=True, views=10000, duration="10:00"),
            _make_video(video_id="v2", curated=True, views=50000, duration="10:00"),
        ]}}
        selected = select_videos(race)
        assert selected[0]["video_id"] == "v2"


# ── Brightness Score ──────────────────────────────────────────


class TestBrightnessScore:
    def test_black_very_low(self):
        img = _make_image(color=(0, 0, 0))
        assert score_brightness(img) < 0.1

    def test_white_low(self):
        img = _make_image(color=(250, 250, 250))
        assert score_brightness(img) < 0.5

    def test_mid_gray_high(self):
        img = _make_image(color=(128, 128, 128))
        assert score_brightness(img) == 1.0

    def test_ideal_range(self):
        for val in [80, 100, 150, 180]:
            img = _make_image(color=(val, val, val))
            assert score_brightness(img) == 1.0


# ── Contrast Score ────────────────────────────────────────────


class TestContrastScore:
    def test_flat_low(self):
        img = _make_image(color=(128, 128, 128))
        assert score_contrast(img) < 0.05

    def test_checkerboard_high(self):
        img = _make_checkerboard()
        assert score_contrast(img) > 0.5


# ── Sharpness Score ───────────────────────────────────────────


class TestSharpnessScore:
    def test_flat_low(self):
        img = _make_image(color=(128, 128, 128))
        assert score_sharpness(img) < 0.15

    def test_edges_high(self):
        img = _make_checkerboard()
        assert score_sharpness(img) > 0.3

    def test_blurred_lower(self):
        """Blurring a sharp image should reduce sharpness score."""
        sharp = _make_checkerboard()
        blurred = sharp.filter(ImageFilter.GaussianBlur(radius=5))
        assert score_sharpness(blurred) < score_sharpness(sharp)


# ── Nature Color Score ────────────────────────────────────────


class TestNatureColorScore:
    def test_green_high(self):
        img = _make_green_image()
        assert score_nature_color(img) > 0.6

    def test_brown_moderate(self):
        img = _make_brown_image()
        assert score_nature_color(img) > 0.4

    def test_blue_low(self):
        img = _make_blue_image()
        assert score_nature_color(img) < 0.3

    def test_gray_low(self):
        img = _make_image(color=(128, 128, 128))
        # Gray has low spread, gets penalized
        assert score_nature_color(img) < 0.3


# ── Composition Score ─────────────────────────────────────────


class TestCompositionScore:
    def test_uniform_penalized(self):
        img = _make_image(color=(128, 128, 128))
        assert score_composition(img) < 1.0

    def test_sky_heavy_penalized(self):
        """Bright top, dark bottom (all sky) should be penalized."""
        img = Image.new("RGB", (640, 360))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 640, 120], fill=(230, 230, 240))
        draw.rectangle([0, 120, 640, 360], fill=(50, 60, 40))
        assert score_composition(img) < 0.8


# ── Black Frame Detection ────────────────────────────────────


class TestIsBlackFrame:
    def test_black_detected(self):
        img = _make_image(color=(5, 5, 5))
        assert is_black_frame(img) is True

    def test_dark_detected(self):
        img = _make_image(color=(10, 10, 10))
        assert is_black_frame(img) is True

    def test_normal_not_detected(self):
        img = _make_image(color=(128, 128, 128))
        assert is_black_frame(img) is False

    def test_dim_not_detected(self):
        img = _make_image(color=(30, 30, 30))
        assert is_black_frame(img) is False


# ── Text Overlay Detection ───────────────────────────────────


class TestHasTextOverlay:
    def test_clean_image(self):
        img = _make_image(color=(128, 128, 128))
        assert has_text_overlay(img) is False

    def test_title_card(self):
        img = _make_text_overlay_image()
        assert has_text_overlay(img) is True


# ── Frame Diversity Selection ─────────────────────────────────


class TestSelectBestFrames:
    def _candidate(self, score, video_index=0, color=(128, 128, 128)):
        img = _make_image(color=color)
        return {"score": score, "video_index": video_index, "img": img,
                "path": "/tmp/test.jpg", "video_id": "test", "channel": "Test",
                "timestamp": 100}

    def test_max_per_video_constraint(self):
        # 5 candidates from same video with distinct colors
        colors = [(50, 50, 50), (100, 100, 100), (150, 150, 150),
                  (200, 200, 200), (80, 120, 80)]
        candidates = [self._candidate(90 - i * 10, video_index=0, color=colors[i])
                      for i in range(5)]
        selected = select_best_frames(candidates, max_frames=3)
        assert len(selected) == 2  # max 2 from same video

    def test_diversity_across_videos(self):
        candidates = [
            self._candidate(90, video_index=0, color=(100, 100, 100)),
            self._candidate(85, video_index=0, color=(110, 110, 110)),
            self._candidate(80, video_index=1, color=(150, 150, 150)),
            self._candidate(75, video_index=1, color=(160, 160, 160)),
        ]
        selected = select_best_frames(candidates, max_frames=3)
        assert len(selected) == 3
        videos = [s["video_index"] for s in selected]
        assert videos.count(0) <= 2
        assert videos.count(1) <= 2

    def test_max_frames_respected(self):
        candidates = [
            self._candidate(90, video_index=0, color=(100, 100, 100)),
            self._candidate(85, video_index=1, color=(200, 200, 200)),
        ]
        selected = select_best_frames(candidates, max_frames=1)
        assert len(selected) == 1
        assert selected[0]["score"] == 90

    def test_near_duplicate_rejected(self):
        """Two candidates with identical images should be deduped."""
        c1 = self._candidate(90, video_index=0, color=(128, 128, 128))
        c2 = self._candidate(85, video_index=1, color=(128, 128, 128))
        selected = select_best_frames([c1, c2], max_frames=3)
        assert len(selected) == 1

    def test_empty_candidates(self):
        assert select_best_frames([], max_frames=3) == []


# ── Frame Similarity ──────────────────────────────────────────


class TestFrameSimilarity:
    def test_identical_images(self):
        img = _make_image(color=(128, 128, 128))
        assert _frame_similarity(img, img) == 1.0

    def test_different_images(self):
        a = _make_image(color=(50, 50, 50))
        b = _make_image(color=(200, 200, 200))
        sim = _frame_similarity(a, b)
        assert sim < 0.5

    def test_similar_images(self):
        a = _make_image(color=(128, 128, 128))
        b = _make_image(color=(130, 130, 130))
        assert _frame_similarity(a, b) > 0.9


# ── Photo Entry Building ─────────────────────────────────────


class TestBuildPhotoEntries:
    def test_basic_entries(self):
        entries = build_photo_entries(
            "unbound-200",
            ["/tmp/a.jpg", "/tmp/b.jpg", "/tmp/c.jpg"],
            ["/tmp/gif.gif"],
            ["Goettl Media"],
        )
        assert len(entries) == 4  # 3 photos + 1 GIF

    def test_multiple_gifs(self):
        entries = build_photo_entries(
            "unbound-200",
            ["/tmp/a.jpg"],
            ["/tmp/g1.gif", "/tmp/g2.gif", "/tmp/g3.gif"],
            ["Goettl Media"],
        )
        gif_entries = [e for e in entries if e.get("gif")]
        assert len(gif_entries) == 3
        assert gif_entries[0]["file"] == "unbound-200-preview.gif"
        assert gif_entries[1]["file"] == "unbound-200-preview-2.gif"
        assert gif_entries[2]["file"] == "unbound-200-preview-3.gif"

    def test_photo_schema(self):
        entries = build_photo_entries("test-race", ["/tmp/a.jpg"], [], ["TestCh"])
        p = entries[0]
        assert p["type"] == "video-1"
        assert p["file"] == "test-race-video-1.jpg"
        assert p["url"] == "/race-photos/test-race/test-race-video-1.jpg"
        assert "Course scenery" in p["alt"]
        assert p["credit"] == "YouTube / TestCh"
        assert p["primary"] is True

    def test_gif_schema(self):
        entries = build_photo_entries("test-race", [], ["/tmp/gif.gif"], ["TestCh"])
        g = entries[0]
        assert g["type"] == "preview-gif"
        assert g["gif"] is True
        assert g["file"] == "test-race-preview.gif"
        assert g["url"] == "/race-photos/test-race/test-race-preview.gif"

    def test_first_photo_is_primary(self):
        entries = build_photo_entries("slug", ["/a.jpg", "/b.jpg"], [], ["Ch"])
        assert entries[0]["primary"] is True
        assert entries[1]["primary"] is False

    def test_no_gif_when_empty(self):
        entries = build_photo_entries("slug", ["/a.jpg"], [], ["Ch"])
        assert len(entries) == 1
        assert all(not e.get("gif") for e in entries)

    def test_credit_format(self):
        entries = build_photo_entries("slug", ["/a.jpg"], [], ["Goettl Media"])
        assert entries[0]["credit"] == "YouTube / Goettl Media"

    def test_valid_types(self):
        entries = build_photo_entries("s", ["/a.jpg", "/b.jpg", "/c.jpg"], ["/g.gif"], ["C"])
        for e in entries:
            assert e["type"] in VALID_PHOTO_TYPES


# ── Merge Photos ──────────────────────────────────────────────


class TestMergePhotos:
    def test_empty_existing(self):
        new = [{"type": "video-1", "primary": True}]
        merged = merge_photos([], new)
        assert len(merged) == 1

    def test_replaces_video_entries(self):
        existing = [
            {"type": "video-1", "file": "old.jpg", "primary": True},
            {"type": "video-2", "file": "old2.jpg"},
        ]
        new = [{"type": "video-1", "file": "new.jpg", "primary": True}]
        merged = merge_photos(existing, new)
        assert len(merged) == 1
        assert merged[0]["file"] == "new.jpg"

    def test_preserves_street_entries(self):
        existing = [
            {"type": "street-1", "file": "street.jpg", "primary": True},
            {"type": "video-1", "file": "old.jpg"},
        ]
        new = [{"type": "video-1", "file": "new.jpg", "primary": True}]
        merged = merge_photos(existing, new)
        assert len(merged) == 2
        types = [p["type"] for p in merged]
        assert "street-1" in types
        assert "video-1" in types

    def test_primary_deferred_to_higher_priority(self):
        """If street-1 exists, video-1 should not be primary."""
        existing = [{"type": "street-1", "file": "street.jpg"}]
        new = [{"type": "video-1", "file": "new.jpg", "primary": True}]
        merged = merge_photos(existing, new)
        video = [p for p in merged if p["type"] == "video-1"][0]
        assert video["primary"] is False

    def test_replaces_preview_gif(self):
        existing = [{"type": "preview-gif", "file": "old.gif", "gif": True}]
        new = [{"type": "preview-gif", "file": "new.gif", "gif": True}]
        merged = merge_photos(existing, new)
        assert len(merged) == 1
        assert merged[0]["file"] == "new.gif"


# ── Composite Score ───────────────────────────────────────────


class TestScoreFrame:
    def test_good_nature_image(self):
        img = _make_green_image()
        score = score_frame(img)
        assert 0 <= score <= 100

    def test_black_very_low(self):
        img = _make_image(color=(5, 5, 5))
        assert score_frame(img) < 20

    def test_mid_gray_moderate(self):
        img = _make_image(color=(128, 128, 128))
        score = score_frame(img)
        assert 10 < score < 50

    def test_checkerboard_high_contrast(self):
        img = _make_checkerboard()
        score = score_frame(img)
        assert score > 30


# ── Integration: Duration Parsing Across Real Data ────────────


class TestDurationParsingIntegration:
    """Verify all duration_strings in real race data parse correctly."""

    def test_all_durations_parse(self):
        if not DATA_DIR.exists():
            pytest.skip("race-data not available")

        failures = []
        total = 0
        for json_file in sorted(DATA_DIR.glob("*.json")):
            try:
                data = json.loads(json_file.read_text())
            except json.JSONDecodeError:
                continue
            race = data.get("race", data)
            for v in race.get("youtube_data", {}).get("videos", []):
                ds = v.get("duration_string", "")
                if not ds:
                    continue
                total += 1
                secs = parse_duration_seconds(ds)
                if secs <= 0:
                    failures.append(f"{json_file.stem}: '{ds}' → {secs}")

        assert not failures, f"{len(failures)} unparseable durations:\n" + "\n".join(failures[:10])
        assert total > 100, f"Expected 100+ durations, got {total}"


class TestCandidateCountIntegration:
    """Verify expected number of races are eligible."""

    def test_eligible_count(self):
        if not DATA_DIR.exists():
            pytest.skip("race-data not available")

        eligible = 0
        for json_file in sorted(DATA_DIR.glob("*.json")):
            try:
                data = json.loads(json_file.read_text())
            except json.JSONDecodeError:
                continue
            race = data.get("race", data)
            videos = race.get("youtube_data", {}).get("videos", [])
            if videos:
                # At least one video in duration range
                for v in videos:
                    dur = parse_duration_seconds(v.get("duration_string", ""))
                    if MIN_DURATION_SEC <= dur <= MAX_DURATION_SEC:
                        eligible += 1
                        break

        # Plan says ~266 races with videos
        assert eligible >= 200, f"Expected 200+ eligible races, got {eligible}"


# ── Tier Config ──────────────────────────────────────────────

class TestGetTierConfig:
    def test_tier1_more_videos(self):
        cfg = get_tier_config(1)
        assert cfg["max_videos"] >= 4
        assert cfg["max_gifs"] >= 5

    def test_tier2_moderate(self):
        cfg = get_tier_config(2)
        assert cfg["max_videos"] >= 3
        assert cfg["max_gifs"] >= 3

    def test_tier3_uses_default(self):
        cfg = get_tier_config(3)
        assert cfg == DEFAULT_TIER_CONFIG

    def test_tier4_uses_default(self):
        cfg = get_tier_config(4)
        assert cfg == DEFAULT_TIER_CONFIG

    def test_unknown_tier_uses_default(self):
        cfg = get_tier_config(99)
        assert cfg == DEFAULT_TIER_CONFIG

    def test_sample_percents_ordered(self):
        for tier in (1, 2, 3, 4):
            percents = get_tier_config(tier)["sample_percents"]
            assert percents == sorted(percents), f"Tier {tier} percents not sorted"


# ── Bright Text Cluster Detection ────────────────────────────

class TestHasBrightTextClusters:
    def test_uniform_dark_no_text(self):
        """Dark image with no bright spots → no text."""
        img = _make_image(color=(40, 40, 40))
        assert _has_bright_text_clusters(img) is False

    def test_uniform_bright_no_text(self):
        """All-white image is not text overlay (too much bright)."""
        img = _make_image(color=(250, 250, 250))
        assert _has_bright_text_clusters(img) is False

    def test_white_text_on_dark(self):
        """White text region on dark background → detected."""
        # Create image with scattered bright blocks on dark bg (like text overlay).
        # Use 100×100 so smaller bright regions reach the edge threshold.
        img = _make_image(width=100, height=100, color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        # Dense small blocks across multiple rows — high edge density
        for y_start in range(20, 80, 5):
            for x_start in range(5, 95, 8):
                draw.rectangle([x_start, y_start, x_start + 4, y_start + 3],
                               fill=(250, 250, 250))
        assert _has_bright_text_clusters(img) is True

    def test_mid_gray_no_detection(self):
        """Mid-gray image → no false positive."""
        img = _make_image(color=(128, 128, 128))
        assert _has_bright_text_clusters(img) is False


# ── Motion Score ─────────────────────────────────────────────

class TestScoreMotion:
    def test_identical_frames_zero(self):
        """Same image repeated → no motion."""
        img = _make_image(color=(100, 100, 100))
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i in range(3):
                p = os.path.join(tmp, f"f{i}.jpg")
                img.save(p)
                paths.append(p)
            assert score_motion(paths) < 0.1

    def test_different_frames_high(self):
        """Very different images → high motion."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            colors = [(0, 0, 0), (255, 255, 255), (0, 0, 0)]
            for i, c in enumerate(colors):
                img = _make_image(color=c)
                p = os.path.join(tmp, f"f{i}.jpg")
                img.save(p)
                paths.append(p)
            assert score_motion(paths) > 0.5

    def test_single_frame_zero(self):
        """One frame → can't compute motion."""
        with tempfile.TemporaryDirectory() as tmp:
            img = _make_image(color=(100, 100, 100))
            p = os.path.join(tmp, "f0.jpg")
            img.save(p)
            assert score_motion([p]) == 0.0

    def test_empty_list_zero(self):
        assert score_motion([]) == 0.0


# ── GIF Segment Selection ────────────────────────────────────

class TestSelectBestGifSegments:
    _color_idx = 0

    def _make_candidate(self, vid_id, ts, motion, quality, video_idx=0):
        # Each candidate gets a distinct color to avoid visual dedup
        self._color_idx += 1
        c = (self._color_idx * 37 % 200 + 30, self._color_idx * 53 % 200 + 30,
             self._color_idx * 71 % 200 + 30)
        return {
            "video_id": vid_id,
            "timestamp": ts,
            "video_index": video_idx,
            "channel": "TestCh",
            "motion_score": motion,
            "frame_score": quality,
            "img": _make_image(color=c),
        }

    def test_selects_top_by_combined_score(self):
        candidates = [
            self._make_candidate("v1", 60, motion=0.9, quality=0.8),
            self._make_candidate("v1", 120, motion=0.2, quality=0.5),
        ]
        selected = select_best_gif_segments(candidates, max_gifs=1)
        assert len(selected) == 1
        assert selected[0]["timestamp"] == 60

    def test_respects_max_gifs(self):
        candidates = [
            self._make_candidate("v1", 60, motion=0.9, quality=0.8),
            self._make_candidate("v2", 120, motion=0.8, quality=0.7, video_idx=1),
            self._make_candidate("v3", 180, motion=0.7, quality=0.6, video_idx=2),
        ]
        selected = select_best_gif_segments(candidates, max_gifs=2)
        assert len(selected) == 2

    def test_timestamp_proximity_filter(self):
        """Candidates within 30s on same video should be deduped."""
        candidates = [
            self._make_candidate("v1", 60, motion=0.9, quality=0.8),
            self._make_candidate("v1", 75, motion=0.85, quality=0.7),  # only 15s apart
        ]
        selected = select_best_gif_segments(candidates, max_gifs=2)
        assert len(selected) == 1

    def test_empty_candidates(self):
        assert select_best_gif_segments([], max_gifs=3) == []

    def test_spreads_when_scores_close(self):
        """When top candidate from each video is close, both get selected."""
        candidates = [
            self._make_candidate("v1", 60, motion=0.9, quality=0.8, video_idx=0),
            self._make_candidate("v2", 60, motion=0.88, quality=0.78, video_idx=1),
        ]
        selected = select_best_gif_segments(candidates, max_gifs=2)
        assert len(selected) == 2
        video_ids = {s["video_id"] for s in selected}
        assert len(video_ids) == 2


# ── Multi-GIF Build Photo Entries ────────────────────────────

class TestMultiGifPhotoEntries:
    def test_five_gifs_t1(self):
        entries = build_photo_entries(
            "unbound-200",
            ["/tmp/a.jpg"],
            [f"/tmp/g{i}.gif" for i in range(5)],
            ["Goettl Media"],
        )
        gif_entries = [e for e in entries if e.get("gif")]
        assert len(gif_entries) == 5
        # All should be preview-gif type
        assert all(e["type"] == "preview-gif" for e in gif_entries)
        # Numbering: preview, preview-2, preview-3, ...
        files = [e["file"] for e in gif_entries]
        assert files[0] == "unbound-200-preview.gif"
        assert files[1] == "unbound-200-preview-2.gif"
        assert files[4] == "unbound-200-preview-5.gif"

    def test_merge_replaces_all_gifs(self):
        existing = [
            {"type": "preview-gif", "file": "old.gif", "gif": True},
            {"type": "preview-gif", "file": "old2.gif", "gif": True},
        ]
        new = [{"type": "preview-gif", "file": "new.gif", "gif": True}]
        merged = merge_photos(existing, new)
        gif_entries = [e for e in merged if e.get("gif")]
        assert len(gif_entries) == 1
        assert gif_entries[0]["file"] == "new.gif"
