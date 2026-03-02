"""Tests for photo_qc.py — Photo quality control pipeline."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import photo_qc


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_photos_dir(tmp_path):
    """Create a temporary photos directory structure."""
    photos_dir = tmp_path / "race-photos"
    photos_dir.mkdir()
    return photos_dir


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary race-data directory."""
    data_dir = tmp_path / "race-data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_photo(tmp_path):
    """Create a sample 1200x675 JPEG photo with enough detail to pass size check."""
    import random
    random.seed(42)
    img = Image.new("RGB", (1200, 675))
    pixels = img.load()
    for y in range(675):
        for x in range(1200):
            # Create a landscape-like gradient with noise
            r = min(255, max(0, 80 + y // 5 + random.randint(-20, 20)))
            g = min(255, max(0, 120 + random.randint(-30, 30)))
            b = min(255, max(0, 60 + random.randint(-15, 15)))
            pixels[x, y] = (r, g, b)
    path = tmp_path / "test-photo.jpg"
    img.save(str(path), "JPEG", quality=85)
    return path


@pytest.fixture
def sample_gif(tmp_path):
    """Create a sample animated GIF with 24 frames and enough variation to pass size check."""
    import random
    random.seed(42)
    frames = []
    for i in range(24):
        frame = Image.new("RGB", (400, 225))
        pixels = frame.load()
        for y in range(225):
            for x in range(400):
                r = min(255, max(0, 100 + i * 3 + random.randint(-20, 20)))
                g = min(255, max(0, 150 + random.randint(-25, 25)))
                b = min(255, max(0, 80 + random.randint(-15, 15)))
                pixels[x, y] = (r, g, b)
        frames.append(frame)
    path = tmp_path / "test-preview.gif"
    frames[0].save(
        str(path), save_all=True, append_images=frames[1:],
        duration=125, loop=0, format="GIF"
    )
    return path


@pytest.fixture
def small_photo(tmp_path):
    """Create an undersized photo (wrong dimensions)."""
    img = Image.new("RGB", (640, 480), color=(50, 50, 50))
    path = tmp_path / "small-photo.jpg"
    img.save(str(path), "JPEG", quality=85)
    return path


@pytest.fixture
def race_json_data():
    """Sample race JSON data with photos array."""
    return {
        "race": {
            "slug": "test-race",
            "name": "Test Race",
            "display_name": "Test Race",
            "vitals": {"location": "Test City, Colorado"},
            "photos": [
                {
                    "type": "video-1",
                    "file": "test-race-video-1.jpg",
                    "url": "/race-photos/test-race/test-race-video-1.jpg",
                    "alt": "Course scenery from Test Race race footage",
                    "credit": "YouTube / TestChannel",
                    "primary": True,
                },
                {
                    "type": "video-2",
                    "file": "test-race-video-2.jpg",
                    "url": "/race-photos/test-race/test-race-video-2.jpg",
                    "alt": "Course scenery from Test Race race footage",
                    "credit": "YouTube / TestChannel",
                    "primary": False,
                },
                {
                    "type": "preview-gif",
                    "file": "test-race-preview.gif",
                    "url": "/race-photos/test-race/test-race-preview.gif",
                    "alt": "Course preview from Test Race race footage",
                    "credit": "YouTube / TestChannel",
                    "gif": True,
                },
            ],
        }
    }


# ── Perceptual Hash Tests ─────────────────────────────────────────────────

class TestPerceptualHash:
    def test_compute_phash_returns_int(self):
        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        h = photo_qc.compute_phash(img)
        assert isinstance(h, int)

    def test_identical_images_same_hash(self):
        img1 = Image.new("RGB", (100, 100), color=(128, 128, 128))
        img2 = Image.new("RGB", (100, 100), color=(128, 128, 128))
        assert photo_qc.compute_phash(img1) == photo_qc.compute_phash(img2)

    def test_different_images_different_hash(self):
        # Use gradient images to get genuinely different hashes
        # (solid colors hash to all-same-bits since every pixel == avg)
        img1 = Image.new("L", (100, 100), color=0)
        # Top half bright, bottom dark
        for y in range(50):
            for x in range(100):
                img1.putpixel((x, y), 200)
        img2 = Image.new("L", (100, 100), color=0)
        # Left half bright, right dark
        for y in range(100):
            for x in range(50):
                img2.putpixel((x, y), 200)
        h1 = photo_qc.compute_phash(img1.convert("RGB"))
        h2 = photo_qc.compute_phash(img2.convert("RGB"))
        assert h1 != h2

    def test_hamming_distance_identical(self):
        assert photo_qc.hamming_distance(0b1010, 0b1010) == 0

    def test_hamming_distance_one_bit(self):
        assert photo_qc.hamming_distance(0b1010, 0b1011) == 1

    def test_hamming_distance_all_bits(self):
        assert photo_qc.hamming_distance(0b0000, 0b1111) == 4

    def test_similar_images_low_hamming(self):
        """Slightly different images should have low hamming distance."""
        img1 = Image.new("RGB", (200, 200), color=(100, 150, 80))
        img2 = Image.new("RGB", (200, 200), color=(105, 148, 82))
        h1 = photo_qc.compute_phash(img1)
        h2 = photo_qc.compute_phash(img2)
        dist = photo_qc.hamming_distance(h1, h2)
        assert dist <= photo_qc.PHASH_DUPLICATE_THRESHOLD


# ── Scoring Tests ─────────────────────────────────────────────────────────

class TestScoring:
    def test_score_frame_range(self):
        img = Image.new("RGB", (400, 300), color=(100, 150, 80))
        score = photo_qc.score_frame(img)
        assert 0 <= score <= 100

    def test_bright_image_score(self):
        img = Image.new("RGB", (400, 300), color=(120, 160, 100))
        score = photo_qc.score_frame(img)
        assert score > 0

    def test_black_image_low_score(self):
        img = Image.new("RGB", (400, 300), color=(5, 5, 5))
        score = photo_qc.score_frame(img)
        assert score < 30

    def test_score_brightness_ideal_range(self):
        img = Image.new("L", (100, 100), color=128)
        s = photo_qc.score_brightness(Image.merge("RGB", (img, img, img)))
        assert s == 1.0

    def test_score_brightness_too_dark(self):
        img = Image.new("RGB", (100, 100), color=(10, 10, 10))
        s = photo_qc.score_brightness(img)
        assert s < 0.5

    def test_score_brightness_too_bright(self):
        img = Image.new("RGB", (100, 100), color=(250, 250, 250))
        s = photo_qc.score_brightness(img)
        assert s < 0.5


# ── Photo Check Tests ─────────────────────────────────────────────────────

class TestCheckPhoto:
    def test_valid_photo_passes(self, sample_photo):
        with patch.object(photo_qc, 'PHOTOS_DIR', sample_photo.parent):
            result = photo_qc.check_photo(sample_photo)
        assert result["status"] in ("pass", "warn")
        assert result["checks"]["exists"]["pass"]
        assert result["checks"]["dimensions"]["pass"]
        assert result["checks"]["readable"]["pass"]
        assert "phash" in result

    def test_missing_file_fails(self, tmp_path):
        fake = tmp_path / "nonexistent.jpg"
        with patch.object(photo_qc, 'PHOTOS_DIR', tmp_path):
            result = photo_qc.check_photo(fake)
        assert result["status"] == "fail"
        assert not result["checks"]["exists"]["pass"]

    def test_wrong_dimensions_flagged(self, small_photo):
        with patch.object(photo_qc, 'PHOTOS_DIR', small_photo.parent):
            result = photo_qc.check_photo(small_photo)
        assert not result["checks"]["dimensions"]["pass"]

    def test_phash_present(self, sample_photo):
        with patch.object(photo_qc, 'PHOTOS_DIR', sample_photo.parent):
            result = photo_qc.check_photo(sample_photo)
        assert "phash" in result
        assert isinstance(result["phash"], int)


# ── GIF Check Tests ───────────────────────────────────────────────────────

class TestCheckGif:
    def test_valid_gif_passes(self, sample_gif):
        with patch.object(photo_qc, 'PHOTOS_DIR', sample_gif.parent):
            result = photo_qc.check_gif(sample_gif)
        assert result["status"] == "pass"
        assert result["checks"]["exists"]["pass"]
        assert result["checks"]["readable"]["pass"]
        assert result["type"] == "gif"

    def test_missing_gif_fails(self, tmp_path):
        fake = tmp_path / "nonexistent.gif"
        with patch.object(photo_qc, 'PHOTOS_DIR', tmp_path):
            result = photo_qc.check_gif(fake)
        assert result["status"] == "fail"

    def test_gif_frame_count_checked(self, sample_gif):
        with patch.object(photo_qc, 'PHOTOS_DIR', sample_gif.parent):
            result = photo_qc.check_gif(sample_gif)
        assert "frame_count" in result["checks"]
        assert result["checks"]["frame_count"]["value"] == 24


# ── JSON/Disk Parity Tests ───────────────────────────────────────────────

class TestJsonDiskParity:
    def test_perfect_parity(self, tmp_path):
        slug_dir = tmp_path / "test-race"
        slug_dir.mkdir()
        (slug_dir / "test-race-video-1.jpg").touch()
        (slug_dir / "test-race-preview.gif").touch()

        photos = [
            {"file": "test-race-video-1.jpg"},
            {"file": "test-race-preview.gif"},
        ]
        errors = photo_qc.check_json_disk_parity("test-race", photos, slug_dir)
        assert len(errors) == 0

    def test_orphan_detected(self, tmp_path):
        slug_dir = tmp_path / "test-race"
        slug_dir.mkdir()
        (slug_dir / "test-race-video-1.jpg").touch()
        (slug_dir / "orphan.jpg").touch()

        photos = [{"file": "test-race-video-1.jpg"}]
        errors = photo_qc.check_json_disk_parity("test-race", photos, slug_dir)
        assert len(errors) == 1
        assert errors[0]["type"] == "orphan"

    def test_missing_detected(self, tmp_path):
        slug_dir = tmp_path / "test-race"
        slug_dir.mkdir()

        photos = [{"file": "missing-file.jpg"}]
        errors = photo_qc.check_json_disk_parity("test-race", photos, slug_dir)
        assert len(errors) == 1
        assert errors[0]["type"] == "missing"

    def test_empty_slug_dir(self, tmp_path):
        slug_dir = tmp_path / "test-race"
        photos = [{"file": "test-file.jpg"}]
        errors = photo_qc.check_json_disk_parity("test-race", photos, slug_dir)
        assert len(errors) == 1
        assert errors[0]["type"] == "missing"


# ── Duplicate Detection Tests ─────────────────────────────────────────────

class TestDuplicateDetection:
    def test_no_duplicates(self):
        # Use hashes with >10 bits different (beyond PHASH_DUPLICATE_THRESHOLD)
        results = [
            {"file": "a.jpg", "phash": 0b1111111111111111111100000000000000000000000000000000000000000000},
            {"file": "b.jpg", "phash": 0b0000000000000000000011111111111111111111111111111111111111111111},
        ]
        dups = photo_qc.find_duplicates(results)
        assert len(dups) == 0

    def test_exact_duplicate(self):
        results = [
            {"file": "a.jpg", "phash": 0b11111111},
            {"file": "b.jpg", "phash": 0b11111111},
        ]
        dups = photo_qc.find_duplicates(results)
        assert len(dups) == 1
        assert dups[0]["hamming_distance"] == 0

    def test_near_duplicate(self):
        results = [
            {"file": "a.jpg", "phash": 0b11111111},
            {"file": "b.jpg", "phash": 0b11111110},  # 1 bit different
        ]
        dups = photo_qc.find_duplicates(results)
        assert len(dups) == 1
        assert dups[0]["hamming_distance"] == 1

    def test_results_without_phash_skipped(self):
        results = [
            {"file": "a.jpg"},  # no phash
            {"file": "b.jpg", "phash": 0b11111111},
        ]
        dups = photo_qc.find_duplicates(results)
        assert len(dups) == 0


# ── Layer 1 Integration Tests ─────────────────────────────────────────────

class TestRunLayer1:
    def test_dry_run_produces_empty_results(self, tmp_path):
        with patch.object(photo_qc, 'PROGRESS_FILE', tmp_path / "_progress.json"), \
             patch.object(photo_qc, 'PHOTOS_DIR', tmp_path):
            # Write empty progress
            (tmp_path / "_progress.json").write_text('{"test-race": {"extracted_at": "2026-01-01", "photos": 1}}')
            results = photo_qc.run_layer1(dry_run=True)
        assert results["summary"]["total_races"] == 0

    def test_checks_specific_slug(self, tmp_path, sample_photo, race_json_data):
        slug = "test-race"
        slug_dir = tmp_path / slug
        slug_dir.mkdir()

        # Copy sample photo to slug dir
        import shutil
        shutil.copy(str(sample_photo), str(slug_dir / f"{slug}-video-1.jpg"))

        # Write race JSON
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / f"{slug}.json").write_text(json.dumps(race_json_data))

        # Write progress
        progress = {slug: {"extracted_at": "2026-01-01", "photos": 1}}
        (tmp_path / "_progress.json").write_text(json.dumps(progress))

        with patch.object(photo_qc, 'PHOTOS_DIR', tmp_path), \
             patch.object(photo_qc, 'DATA_DIR', data_dir), \
             patch.object(photo_qc, 'PROGRESS_FILE', tmp_path / "_progress.json"):
            results = photo_qc.run_layer1(slugs=[slug])

        assert slug in results["races"]
        assert results["summary"]["total_photos"] >= 1


# ── SEO Alt Text Tests ────────────────────────────────────────────────────

class TestApplySeoAltText:
    def test_updates_alt_text(self, tmp_path, race_json_data):
        slug = "test-race"
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        json_path = data_dir / f"{slug}.json"
        json_path.write_text(json.dumps(race_json_data))

        ai_results = {
            slug: {
                "reviewed_at": "2026-02-24",
                "photos": [
                    {
                        "index": 1,
                        "relevance": 4,
                        "quality": 5,
                        "issues": [],
                        "description": "Riders on a dusty gravel road through the Colorado mountains",
                        "keywords": ["gravel road", "Colorado", "mountain pass"],
                    },
                    {
                        "index": 2,
                        "relevance": 3,
                        "quality": 4,
                        "issues": [],
                        "description": "Peloton descending a rocky switchback",
                        "keywords": ["peloton", "descent", "switchback"],
                    },
                ],
            }
        }

        with patch.object(photo_qc, 'DATA_DIR', data_dir):
            count = photo_qc.apply_seo_alt_text(ai_results)

        assert count == 1

        # Verify the file was updated
        updated = json.loads(json_path.read_text())
        photos = updated["race"]["photos"]
        # First photo (video-1) should have new alt
        assert "dusty gravel road" in photos[0]["alt"]
        assert photos[0].get("ai_relevance") == 4
        assert photos[0].get("ai_quality") == 5
        # Second photo (video-2) should also be updated
        assert "switchback" in photos[1]["alt"]

    def test_dry_run_no_write(self, tmp_path, race_json_data):
        slug = "test-race"
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        json_path = data_dir / f"{slug}.json"
        json_path.write_text(json.dumps(race_json_data))
        original = json_path.read_text()

        ai_results = {
            slug: {
                "photos": [{"description": "New desc", "relevance": 5, "quality": 5}]
            }
        }

        with patch.object(photo_qc, 'DATA_DIR', data_dir):
            count = photo_qc.apply_seo_alt_text(ai_results, dry_run=True)

        assert count == 0
        assert json_path.read_text() == original

    def test_empty_ai_results_no_update(self, tmp_path, race_json_data):
        slug = "test-race"
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / f"{slug}.json").write_text(json.dumps(race_json_data))

        with patch.object(photo_qc, 'DATA_DIR', data_dir):
            count = photo_qc.apply_seo_alt_text({})
        assert count == 0


# ── Dashboard Tests ───────────────────────────────────────────────────────

class TestDashboard:
    def test_renders_html(self):
        qc_results = {
            "checked_at": "2026-02-24",
            "summary": {"total_races": 1, "total_photos": 2, "total_gifs": 1,
                         "pass": 1, "warn": 0, "fail": 0},
            "races": {
                "test-race": {
                    "status": "pass",
                    "photos": [],
                    "gifs": [],
                    "parity_errors": [],
                    "duplicates": [],
                }
            },
        }
        html = photo_qc.render_qc_dashboard(qc_results)
        assert "<!DOCTYPE html>" in html
        assert "Photo QC Report" in html
        assert "test-race" in html

    def test_includes_summary_stats(self):
        qc_results = {
            "checked_at": "2026-02-24",
            "summary": {"total_races": 5, "total_photos": 15, "total_gifs": 10,
                         "pass": 3, "warn": 1, "fail": 1},
            "races": {},
        }
        html = photo_qc.render_qc_dashboard(qc_results)
        assert ">5<" in html  # total races
        assert ">15<" in html  # total photos
        assert ">10<" in html  # total gifs

    def test_fail_sections_open_by_default(self):
        qc_results = {
            "checked_at": "2026-02-24",
            "summary": {"total_races": 1, "total_photos": 1, "total_gifs": 0,
                         "pass": 0, "warn": 0, "fail": 1},
            "races": {
                "bad-race": {
                    "status": "fail",
                    "photos": [],
                    "gifs": [],
                    "parity_errors": [],
                    "duplicates": [],
                }
            },
        }
        html = photo_qc.render_qc_dashboard(qc_results)
        assert 'open' in html  # fail sections auto-open


# ── Brand Tokens Tests ────────────────────────────────────────────────────

class TestBrandTokens:
    def test_read_brand_tokens_returns_dict(self):
        tokens = photo_qc.read_brand_tokens()
        assert isinstance(tokens, dict)

    def test_read_brand_tokens_with_missing_file(self, tmp_path):
        with patch.object(photo_qc, 'TOKENS_PATH', tmp_path / "missing.css"):
            tokens = photo_qc.read_brand_tokens()
        assert tokens == {}


# ── CLI Tests ─────────────────────────────────────────────────────────────

class TestCli:
    def test_status_flag(self, tmp_path, capsys):
        with patch.object(photo_qc, 'PROGRESS_FILE', tmp_path / "_progress.json"), \
             patch.object(photo_qc, 'QC_RESULTS_FILE', tmp_path / "_qc_results.json"), \
             patch.object(photo_qc, 'QC_PROGRESS_FILE', tmp_path / "_qc_progress.json"):
            photo_qc.print_status()
        captured = capsys.readouterr()
        assert "Photo QC Status" in captured.out

    def test_no_args_errors(self):
        with pytest.raises(SystemExit):
            with patch("sys.argv", ["photo_qc.py"]):
                photo_qc.main()


# ── Encode Image Tests ────────────────────────────────────────────────────

class TestEncodeImage:
    def test_encode_base64_returns_string(self, sample_photo):
        b64 = photo_qc.encode_image_base64(sample_photo)
        assert isinstance(b64, str)
        assert len(b64) > 0

    def test_encode_base64_resize_large(self, tmp_path):
        """Large images should be resized before encoding."""
        img = Image.new("RGB", (3000, 2000), color=(128, 128, 128))
        path = tmp_path / "large.jpg"
        img.save(str(path), "JPEG")
        b64 = photo_qc.encode_image_base64(path, max_size=512)
        assert isinstance(b64, str)


# ── Vision Prompt Tests ───────────────────────────────────────────────────

class TestVisionPrompt:
    def test_prompt_includes_slug(self):
        prompt = photo_qc.build_vision_prompt("unbound-200", ["photo1.jpg", "photo2.jpg"])
        assert "Unbound 200" in prompt
        assert "1-2" in prompt

    def test_prompt_valid_json_structure(self):
        prompt = photo_qc.build_vision_prompt("test-race", ["a.jpg"])
        assert '"relevance"' in prompt
        assert '"quality"' in prompt
        assert '"description"' in prompt
        assert '"keywords"' in prompt
