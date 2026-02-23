"""Tests for validate_citations.py and extract_citations.py citation quality checks."""

import sys
from pathlib import Path

import pytest

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from validate_citations import (
    is_generic_homepage,
    is_suspicious_reddit_url,
    validate_race_citations,
    DOMAINS_REQUIRING_PATH,
)
from extract_citations import (
    is_generic_homepage as extract_is_generic_homepage,
    is_relevant_to_race,
)


# ── is_generic_homepage ───────────────────────────────────────────────


class TestIsGenericHomepage:
    """Test generic homepage detection."""

    def test_bare_domain(self):
        assert is_generic_homepage("https://velonews.com") is True

    def test_bare_domain_trailing_slash(self):
        assert is_generic_homepage("https://velonews.com/") is True

    def test_www_bare_domain(self):
        assert is_generic_homepage("https://www.velonews.com/") is True

    def test_language_prefix_en(self):
        assert is_generic_homepage("https://cyclingtips.com/en") is True

    def test_language_prefix_en_slash(self):
        assert is_generic_homepage("https://cyclingtips.com/en/") is True

    def test_language_prefix_fr(self):
        assert is_generic_homepage("https://example.com/fr") is True

    def test_language_prefix_de(self):
        assert is_generic_homepage("https://example.com/de/") is True

    def test_specific_article_not_homepage(self):
        assert is_generic_homepage(
            "https://velonews.com/gravel/unbound-gravel-race-report"
        ) is False

    def test_specific_path_not_homepage(self):
        assert is_generic_homepage(
            "https://ridinggravel.com/events/red-granite-grinder/"
        ) is False

    def test_subreddit_not_homepage(self):
        assert is_generic_homepage(
            "https://reddit.com/r/gravelcycling"
        ) is False

    def test_empty_url(self):
        # Empty string parses as no-path — is_generic_homepage returns True,
        # but empty URLs are caught earlier by the "empty URL" check
        assert is_generic_homepage("") is True

    def test_malformed_url(self):
        assert is_generic_homepage("not-a-url") is False

    def test_extract_citations_version_matches(self):
        """Both copies of is_generic_homepage should agree."""
        test_urls = [
            "https://velonews.com/",
            "https://velonews.com/en/",
            "https://velonews.com/gravel/report",
            "https://reddit.com/r/cycling",
        ]
        for url in test_urls:
            assert is_generic_homepage(url) == extract_is_generic_homepage(url), (
                f"Mismatch on {url}"
            )


# ── is_suspicious_reddit_url ──────────────────────────────────────────


class TestIsSuspiciousRedditUrl:
    """Test Reddit URL format validation."""

    def test_valid_post_url(self):
        assert is_suspicious_reddit_url(
            "https://www.reddit.com/r/gravelcycling/comments/abc123/my_race_report/"
        ) is False

    def test_valid_subreddit_listing(self):
        assert is_suspicious_reddit_url(
            "https://reddit.com/r/gravelcycling"
        ) is False

    def test_user_profile_rejected(self):
        assert is_suspicious_reddit_url(
            "https://reddit.com/user/someuser123"
        ) is True

    def test_u_prefix_profile_rejected(self):
        assert is_suspicious_reddit_url(
            "https://www.reddit.com/u/someuser123"
        ) is True

    def test_share_link_rejected(self):
        assert is_suspicious_reddit_url(
            "https://reddit.com/r/gravelcycling/s/abc123def"
        ) is True

    def test_non_reddit_url_passes(self):
        assert is_suspicious_reddit_url(
            "https://velonews.com/gravel/report"
        ) is False

    def test_reddit_homepage_not_suspicious(self):
        # Homepage is caught by the generic homepage check, not this one
        assert is_suspicious_reddit_url("https://reddit.com/") is False

    def test_valid_comments_url_with_title(self):
        assert is_suspicious_reddit_url(
            "https://www.reddit.com/r/Velo/comments/1f2g3h4/unbound_200_race_thread/"
        ) is False


# ── validate_race_citations integration ───────────────────────────────


class TestValidateRaceCitations:
    """Integration tests for the full validation function."""

    def test_clean_citations_pass(self):
        citations = [
            {"url": "https://velonews.com/gravel/race-report", "category": "media", "label": "VeloNews"},
            {"url": "https://ridewithgps.com/routes/12345", "category": "route", "label": "RideWithGPS"},
        ]
        errors = validate_race_citations("test-race", citations)
        assert errors == []

    def test_generic_homepage_flagged(self):
        citations = [
            {"url": "https://velonews.com/", "category": "media", "label": "VeloNews"},
        ]
        errors = validate_race_citations("test-race", citations)
        assert any("generic homepage" in e for e in errors)

    def test_generic_homepage_no_slash_flagged(self):
        citations = [
            {"url": "https://ridinggravel.com", "category": "community", "label": "Riding Gravel"},
        ]
        errors = validate_race_citations("test-race", citations)
        assert any("generic homepage" in e for e in errors)

    def test_reddit_user_profile_flagged(self):
        citations = [
            {"url": "https://reddit.com/user/gravel_fan", "category": "community", "label": "Reddit"},
        ]
        errors = validate_race_citations("test-race", citations)
        assert any("suspicious Reddit" in e for e in errors)

    def test_language_prefix_homepage_flagged(self):
        citations = [
            {"url": "https://cyclingtips.com/en/", "category": "media", "label": "CyclingTips"},
        ]
        errors = validate_race_citations("test-race", citations)
        assert any("generic homepage" in e for e in errors)

    def test_duplicate_still_caught(self):
        citations = [
            {"url": "https://example.com/a", "category": "other", "label": "A"},
            {"url": "https://example.com/a", "category": "other", "label": "A"},
        ]
        errors = validate_race_citations("test-race", citations)
        assert any("duplicate" in e.lower() for e in errors)

    def test_max_cap_enforced(self):
        citations = [
            {"url": f"https://example.com/page-{i}", "category": "other", "label": f"Page {i}"}
            for i in range(25)
        ]
        errors = validate_race_citations("test-race", citations)
        assert any("exceeds cap" in e for e in errors)

    def test_missing_url_flagged(self):
        citations = [
            {"url": "", "category": "other", "label": "Empty"},
        ]
        errors = validate_race_citations("test-race", citations)
        assert any("empty URL" in e for e in errors)

    def test_malformed_url_flagged(self):
        citations = [
            {"url": "not-a-url", "category": "other", "label": "Bad"},
        ]
        errors = validate_race_citations("test-race", citations)
        assert any("malformed" in e for e in errors)


# ── is_relevant_to_race with homepage rejection ──────────────────────


class TestIsRelevantToRaceHomepageRejection:
    """Test that is_relevant_to_race rejects homepages for always-relevant domains."""

    def test_velonews_homepage_rejected(self):
        assert is_relevant_to_race(
            "https://velonews.com/", "unbound-200", "Unbound Gravel 200"
        ) is False

    def test_velonews_article_accepted(self):
        assert is_relevant_to_race(
            "https://velonews.com/gravel/unbound-gravel-preview", "unbound-200", "Unbound Gravel 200"
        ) is True

    def test_ridinggravel_homepage_rejected(self):
        assert is_relevant_to_race(
            "https://ridinggravel.com", "red-granite-grinder", "Red Granite Grinder"
        ) is False

    def test_ridinggravel_event_page_accepted(self):
        assert is_relevant_to_race(
            "https://ridinggravel.com/events/red-granite-grinder/",
            "red-granite-grinder", "Red Granite Grinder"
        ) is True

    def test_cyclingtips_language_prefix_rejected(self):
        assert is_relevant_to_race(
            "https://cyclingtips.com/en/", "unbound-200", "Unbound Gravel 200"
        ) is False

    def test_strava_homepage_rejected(self):
        assert is_relevant_to_race(
            "https://strava.com/", "unbound-200", "Unbound Gravel 200"
        ) is False

    def test_strava_segment_accepted(self):
        assert is_relevant_to_race(
            "https://strava.com/segments/12345", "unbound-200", "Unbound Gravel 200"
        ) is True

    def test_wikipedia_homepage_rejected(self):
        assert is_relevant_to_race(
            "https://wikipedia.org/", "unbound-200", "Unbound Gravel 200"
        ) is False

    def test_wikipedia_article_accepted(self):
        assert is_relevant_to_race(
            "https://en.wikipedia.org/wiki/Unbound_Gravel",
            "unbound-200", "Unbound Gravel 200"
        ) is True


# ── DOMAINS_REQUIRING_PATH completeness ──────────────────────────────


class TestDomainsRequiringPath:
    """Ensure all cycling media domains are in the path-required set."""

    def test_velonews_in_set(self):
        assert 'velonews.com' in DOMAINS_REQUIRING_PATH

    def test_reddit_in_set(self):
        assert 'reddit.com' in DOMAINS_REQUIRING_PATH

    def test_cycling_media_covered(self):
        expected = {
            'velonews.com', 'cyclingtips.com', 'bikeradar.com',
            'gravelcyclist.com', 'ridinggravel.com', 'cxmagazine.com',
        }
        assert expected.issubset(DOMAINS_REQUIRING_PATH)
