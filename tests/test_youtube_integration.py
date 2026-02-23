"""Tests for YouTube integration — From the Field section + schema validation.

Covers:
  - youtube_data schema validation across profiles
  - HTML builder (empty data → empty string, XSS safety, nocookie domain, lazy loading)
  - Normalize passthrough (curated filtering, max 3)
  - Video ID format validation
  - Quote cross-references to valid video IDs
"""

import json
import re
import sys
from pathlib import Path

import pytest

# Ensure wordpress/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from generate_neo_brutalist import (
    build_from_the_field,
    build_toc,
    _format_view_count,
    esc,
    generate_page,
    normalize_race_data,
)


RACE_DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"

# Valid video_id regex: 11-char alphanumeric + hyphen/underscore
VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def minimal_race():
    """Minimal race data without youtube_data — should produce no section."""
    return {
        "race": {
            "name": "Test Race",
            "slug": "test-race",
            "display_name": "Test Race",
            "vitals": {
                "distance_mi": 50,
                "elevation_ft": 3000,
                "location": "Somewhere, Colorado",
                "date": "July annually",
                "date_specific": "2026: July 10",
                "field_size": "200",
            },
            "gravel_god_rating": {
                "overall_score": 55,
                "tier": 3,
                "tier_label": "TIER 3",
                "logistics": 3, "length": 3, "technicality": 2,
                "elevation": 3, "climate": 2, "altitude": 2, "adventure": 2,
                "prestige": 2, "race_quality": 3, "experience": 3,
                "community": 2, "field_depth": 2, "value": 3, "expenses": 3,
                "discipline": "gravel",
            },
            "biased_opinion": {"verdict": "OK", "summary": "Fine."},
            "biased_opinion_ratings": {},
        }
    }


@pytest.fixture
def race_with_youtube(minimal_race):
    """Race data with full youtube_data block."""
    minimal_race["race"]["youtube_data"] = {
        "researched_at": "2026-02-22",
        "videos": [
            {
                "video_id": "vKCSt1e392M",
                "title": "Riding Beyond the Race | Migration Gravel Race",
                "channel": "Far Beyond by EF Pro Cycling",
                "view_count": 68980,
                "upload_date": "20250904",
                "duration_string": "15:31",
                "curated": True,
                "curation_reason": "First-person epic with course details",
                "display_order": 1,
            },
            {
                "video_id": "abc123DEF_-",
                "title": "Another Great Video",
                "channel": "Cycling Channel",
                "view_count": 12000,
                "upload_date": "20250801",
                "duration_string": "8:42",
                "curated": True,
                "curation_reason": "Good recap",
                "display_order": 2,
            },
            {
                "video_id": "notcurated1",
                "title": "Raw Search Result",
                "channel": "Random",
                "view_count": 500,
                "curated": False,
                "display_order": 99,
            },
        ],
        "quotes": [
            {
                "text": "The landscapes here are harsh. The reality of survival illuminates itself.",
                "source_video_id": "vKCSt1e392M",
                "source_channel": "Far Beyond by EF Pro Cycling",
                "source_view_count": 68980,
                "category": "race_atmosphere",
                "curated": True,
            },
            {
                "text": "Not curated quote.",
                "source_video_id": "notcurated1",
                "source_channel": "Random",
                "source_view_count": 500,
                "category": "generic",
                "curated": False,
            },
        ],
    }
    return minimal_race


# ── Normalize Passthrough ─────────────────────────────────────

class TestNormalizeYouTubePassthrough:
    """Test that normalize_race_data correctly passes through youtube data."""

    def test_no_youtube_data_produces_empty_lists(self, minimal_race):
        rd = normalize_race_data(minimal_race)
        assert rd['youtube_videos'] == []
        assert rd['youtube_quotes'] == []

    def test_curated_videos_only(self, race_with_youtube):
        rd = normalize_race_data(race_with_youtube)
        assert len(rd['youtube_videos']) == 2
        assert all(v['curated'] for v in rd['youtube_videos'])

    def test_curated_quotes_only(self, race_with_youtube):
        rd = normalize_race_data(race_with_youtube)
        assert len(rd['youtube_quotes']) == 1
        assert rd['youtube_quotes'][0]['curated'] is True

    def test_max_3_videos(self, race_with_youtube):
        """Even with many curated videos, max 3 are passed through."""
        vids = race_with_youtube["race"]["youtube_data"]["videos"]
        for i in range(5):
            vids.append({
                "video_id": f"extra{i:06d}X",
                "title": f"Extra {i}",
                "channel": "Test",
                "view_count": 1000,
                "curated": True,
                "display_order": 10 + i,
            })
        rd = normalize_race_data(race_with_youtube)
        assert len(rd['youtube_videos']) <= 3

    def test_max_3_quotes(self, race_with_youtube):
        """Even with many curated quotes, max 3 are passed through."""
        quotes = race_with_youtube["race"]["youtube_data"]["quotes"]
        for i in range(5):
            quotes.append({
                "text": f"Quote number {i}",
                "source_video_id": "vKCSt1e392M",
                "source_channel": "Test",
                "source_view_count": 1000,
                "category": "generic",
                "curated": True,
            })
        rd = normalize_race_data(race_with_youtube)
        assert len(rd['youtube_quotes']) <= 3


# ── HTML Builder ──────────────────────────────────────────────

class TestBuildFromTheField:
    """Test the build_from_the_field() HTML builder."""

    def test_empty_data_returns_empty_string(self, minimal_race):
        rd = normalize_race_data(minimal_race)
        assert build_from_the_field(rd) == ''

    def test_returns_section_with_youtube_data(self, race_with_youtube):
        rd = normalize_race_data(race_with_youtube)
        html = build_from_the_field(rd)
        assert html != ''
        assert 'id="from-the-field"' in html
        assert 'From the Field' in html

    def test_section_kicker_is_04(self, race_with_youtube):
        rd = normalize_race_data(race_with_youtube)
        html = build_from_the_field(rd)
        assert '[04]' in html

    def test_nocookie_domain_in_js(self):
        """Ensure the lite-youtube JS uses youtube-nocookie.com."""
        from generate_neo_brutalist import build_inline_js
        js = build_inline_js()
        assert 'youtube-nocookie.com' in js

    def test_quotes_are_html_escaped(self, race_with_youtube):
        """XSS: quote text must be escaped."""
        race_with_youtube["race"]["youtube_data"]["quotes"][0]["text"] = '<script>alert("xss")</script>'
        race_with_youtube["race"]["youtube_data"]["quotes"][0]["curated"] = True
        rd = normalize_race_data(race_with_youtube)
        html = build_from_the_field(rd)
        assert '<script>' not in html
        assert '&lt;script&gt;' in html

    def test_video_title_is_html_escaped(self, race_with_youtube):
        """XSS: video title in alt/aria must be escaped."""
        race_with_youtube["race"]["youtube_data"]["videos"][0]["title"] = 'Test "onload=alert(1)'
        rd = normalize_race_data(race_with_youtube)
        html = build_from_the_field(rd)
        assert '"onload=' not in html

    def test_channel_name_is_html_escaped(self, race_with_youtube):
        """XSS: channel name with HTML tags must be escaped (no valid tags in output)."""
        race_with_youtube["race"]["youtube_data"]["quotes"][0]["source_channel"] = '<img src=x onerror=alert(1)>'
        rd = normalize_race_data(race_with_youtube)
        html = build_from_the_field(rd)
        # The literal tag opener must be escaped — <img becomes &lt;img in cite
        cite_match = re.search(r'<cite[^>]*>(.*?)</cite>', html)
        assert cite_match, "Expected a <cite> element"
        cite_content = cite_match.group(1)
        assert '<img' not in cite_content
        assert '&lt;img' in cite_content

    def test_video_thumbnails_use_lazy_loading(self, race_with_youtube):
        rd = normalize_race_data(race_with_youtube)
        html = build_from_the_field(rd)
        assert 'loading="lazy"' in html

    def test_video_thumbnails_use_ytimg(self, race_with_youtube):
        rd = normalize_race_data(race_with_youtube)
        html = build_from_the_field(rd)
        assert 'i.ytimg.com' in html

    def test_teal_accent_class(self, race_with_youtube):
        rd = normalize_race_data(race_with_youtube)
        html = build_from_the_field(rd)
        assert 'gg-section--teal-accent' in html

    def test_teal_header_class(self, race_with_youtube):
        rd = normalize_race_data(race_with_youtube)
        html = build_from_the_field(rd)
        assert 'gg-section-header--teal' in html

    def test_video_ordering_by_display_order(self, race_with_youtube):
        """Videos should be ordered by display_order."""
        rd = normalize_race_data(race_with_youtube)
        html = build_from_the_field(rd)
        # First video (display_order=1) should appear before second (display_order=2)
        pos1 = html.index('vKCSt1e392M')
        pos2 = html.index('abc123DEF_-')
        assert pos1 < pos2

    def test_quotes_only_no_videos(self, minimal_race):
        """Section should render with quotes only (no videos)."""
        minimal_race["race"]["youtube_data"] = {
            "researched_at": "2026-02-22",
            "videos": [],
            "quotes": [{
                "text": "Amazing race atmosphere.",
                "source_video_id": "test1234567",
                "source_channel": "Test Channel",
                "source_view_count": 5000,
                "category": "race_atmosphere",
                "curated": True,
            }],
        }
        rd = normalize_race_data(minimal_race)
        html = build_from_the_field(rd)
        assert html != ''
        assert 'gg-field-quote' in html
        assert 'gg-lite-youtube' not in html

    def test_videos_only_no_quotes(self, minimal_race):
        """Section should render with videos only (no quotes)."""
        minimal_race["race"]["youtube_data"] = {
            "researched_at": "2026-02-22",
            "videos": [{
                "video_id": "test1234567",
                "title": "Test Video",
                "channel": "Test",
                "view_count": 1000,
                "curated": True,
                "curation_reason": "Good",
                "display_order": 1,
            }],
            "quotes": [],
        }
        rd = normalize_race_data(minimal_race)
        html = build_from_the_field(rd)
        assert html != ''
        assert 'gg-lite-youtube' in html
        assert 'gg-field-quote' not in html


# ── View Count Formatting ─────────────────────────────────────

class TestFormatViewCount:
    def test_zero(self):
        assert _format_view_count(0) == ''

    def test_none(self):
        assert _format_view_count(None) == ''

    def test_small_number(self):
        assert _format_view_count(500) == '500'

    def test_thousands(self):
        assert _format_view_count(12000) == '12K'

    def test_thousands_decimal(self):
        assert _format_view_count(12500) == '12.5K'

    def test_millions(self):
        assert _format_view_count(1000000) == '1M'

    def test_millions_decimal(self):
        assert _format_view_count(2500000) == '2.5M'

    def test_69k(self):
        assert _format_view_count(68980) == '69K'


# ── Schema Validation (across live profiles) ──────────────────

class TestYouTubeSchemaAcrossProfiles:
    """Validate youtube_data structure in any enriched race profiles."""

    @pytest.fixture
    def enriched_profiles(self):
        """Collect all race profiles that have youtube_data."""
        if not RACE_DATA_DIR.exists():
            pytest.skip("race-data directory not found")
        profiles = []
        for f in RACE_DATA_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                race = data.get("race", data)
                if "youtube_data" in race:
                    profiles.append((f.name, race["youtube_data"]))
            except (json.JSONDecodeError, IOError):
                continue
        return profiles

    def test_video_ids_are_valid_format(self, enriched_profiles):
        violations = []
        for fname, yt in enriched_profiles:
            for v in yt.get("videos", []):
                vid = v.get("video_id", "")
                if not VIDEO_ID_RE.match(vid):
                    violations.append(f"{fname}: invalid video_id '{vid}'")
        assert not violations, "\n".join(violations)

    def test_quotes_reference_valid_video_ids(self, enriched_profiles):
        violations = []
        for fname, yt in enriched_profiles:
            video_ids = {v["video_id"] for v in yt.get("videos", [])}
            for q in yt.get("quotes", []):
                src = q.get("source_video_id", "")
                if src and src not in video_ids:
                    violations.append(f"{fname}: quote references unknown video_id '{src}'")
        assert not violations, "\n".join(violations)

    def test_display_orders_unique_per_race(self, enriched_profiles):
        violations = []
        for fname, yt in enriched_profiles:
            orders = [v["display_order"] for v in yt.get("videos", []) if "display_order" in v]
            if len(orders) != len(set(orders)):
                violations.append(f"{fname}: duplicate display_order values")
        assert not violations, "\n".join(violations)

    def test_curated_videos_have_curation_reason(self, enriched_profiles):
        violations = []
        for fname, yt in enriched_profiles:
            for v in yt.get("videos", []):
                if v.get("curated") and not v.get("curation_reason"):
                    violations.append(f"{fname}: curated video '{v.get('video_id')}' missing curation_reason")
        assert not violations, "\n".join(violations)

    def test_quote_text_has_no_html(self, enriched_profiles):
        violations = []
        html_re = re.compile(r'<[a-z][^>]*>', re.IGNORECASE)
        for fname, yt in enriched_profiles:
            for q in yt.get("quotes", []):
                text = q.get("text", "")
                if html_re.search(text):
                    violations.append(f"{fname}: quote contains HTML: '{text[:60]}...'")
        assert not violations, "\n".join(violations)

    def test_researched_at_is_valid_date(self, enriched_profiles):
        date_re = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        violations = []
        for fname, yt in enriched_profiles:
            ra = yt.get("researched_at", "")
            if ra and not date_re.match(ra):
                violations.append(f"{fname}: invalid researched_at date '{ra}'")
        assert not violations, "\n".join(violations)


# ── TOC Integration ───────────────────────────────────────────

class TestTocIntegration:
    """Verify From the Field appears in TOC when active."""

    def test_toc_includes_from_the_field_when_active(self):
        toc = build_toc({'course', 'from-the-field', 'ratings', 'training'})
        assert 'from-the-field' in toc
        assert '04 From the Field' in toc

    def test_toc_excludes_from_the_field_when_not_active(self):
        toc = build_toc({'course', 'ratings', 'training'})
        assert 'from-the-field' not in toc


# ── DNS Prefetch ──────────────────────────────────────────────

class TestDnsPrefetch:
    """Verify YouTube thumbnail domain is prefetched."""

    def test_dns_prefetch_in_generated_page(self, race_with_youtube):
        rd = normalize_race_data(race_with_youtube)
        html = generate_page(rd)
        assert 'dns-prefetch" href="https://i.ytimg.com"' in html
