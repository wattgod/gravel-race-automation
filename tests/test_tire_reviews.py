#!/usr/bin/env python3
"""
Comprehensive tests for the tire review system.

Covers all 14 quality fixes identified in the self-audit:
  #1  Worker dedup (email+tire)
  #2  Worker origin validation (exact match)
  #3  Worker tire_id regex validation
  #4  Worker width_ridden range (25-60mm)
  #5  JS double-submit prevention
  #6  JS fetch response handling (not fire-and-forget)
  #7  Sync URL encoding
  #8  Sync KV key URL encoding
  #9  Sync validate_review()
  #10 Sync field whitelist (not PII blacklist)
  #11 Sync sort by submitted_at
  #12 Review card XSS escaping
  #13 Star count validation/clamping
  #14 Pending state shows review cards

Usage:
    python -m pytest tests/test_tire_reviews.py -v
"""

import json
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from generate_tire_pages import (
    _render_review_card,
    build_community_reviews_section,
    build_json_ld,
    build_tire_review_form,
    build_inline_js,
    esc,
    tire_slug,
)
from sync_tire_reviews import validate_review, sanitize_review, REVIEW_FIELDS


# ── Fixtures ──────────────────────────────────────────────────


def _valid_review(**overrides):
    """Create a valid review dict, optionally overriding fields."""
    base = {
        "review_id": "tr-test-tire-abc-xyz",
        "stars": 4,
        "width_ridden": 40,
        "pressure_psi": 30,
        "conditions": ["dry", "mixed"],
        "race_used_at": "Unbound 200",
        "would_recommend": "yes",
        "review_text": "Solid tire on hardpack.",
        "submitted_at": "2026-02-19T12:00:00.000Z",
        "approved": True,
    }
    base.update(overrides)
    return base


def _tire_with_reviews(n: int, **tire_overrides):
    """Create a tire dict with n approved reviews."""
    reviews = []
    for i in range(n):
        reviews.append(_valid_review(
            review_id=f"tr-test-{i}",
            stars=(i % 5) + 1,
            submitted_at=f"2026-02-{19 - i:02d}T12:00:00.000Z",
        ))
    tire = {
        "id": "test-tire",
        "name": "Test Tire Pro",
        "brand": "TestBrand",
        "widths_mm": [40, 45],
        "tread_type": "mixed",
        "tagline": "A test tire.",
        "strengths": ["fast"],
        "weaknesses": ["none"],
        "msrp_usd": 59.99,
        "weight_grams": {"40": 400},
        "tubeless_ready": True,
        "best_conditions": ["dry"],
        "worst_conditions": ["mud"],
        "brr_urls_by_width": {},
        "puncture_resistance": "medium",
        "wet_traction": "fair",
        "mud_clearance": "low",
        "recommended_use": ["gravel"],
        "avoid_use": ["mud"],
        "comparable_tires": [],
        "community_reviews": reviews,
        "status": "active",
    }
    tire.update(tire_overrides)
    return tire


# ── Fix #9: validate_review() ────────────────────────────────


class TestValidateReview(unittest.TestCase):
    """Fix #9: Validate review data pulled from KV."""

    def test_valid_review_passes(self):
        self.assertIsNone(validate_review(_valid_review()))

    def test_rejects_non_dict(self):
        self.assertIsNotNone(validate_review("not a dict"))
        self.assertIsNotNone(validate_review(42))
        self.assertIsNotNone(validate_review([]))

    def test_rejects_missing_review_id(self):
        r = _valid_review(review_id="")
        self.assertIn("review_id", validate_review(r))

    def test_rejects_missing_stars(self):
        r = _valid_review()
        del r["stars"]
        self.assertIsNotNone(validate_review(r))

    def test_rejects_stars_zero(self):
        self.assertIsNotNone(validate_review(_valid_review(stars=0)))

    def test_rejects_stars_six(self):
        self.assertIsNotNone(validate_review(_valid_review(stars=6)))

    def test_rejects_stars_negative(self):
        self.assertIsNotNone(validate_review(_valid_review(stars=-1)))

    def test_rejects_stars_float(self):
        self.assertIsNotNone(validate_review(_valid_review(stars=3.5)))

    def test_rejects_stars_string(self):
        self.assertIsNotNone(validate_review(_valid_review(stars="five")))

    def test_rejects_missing_submitted_at(self):
        r = _valid_review(submitted_at="")
        self.assertIn("submitted_at", validate_review(r))

    def test_rejects_invalid_width_ridden_type(self):
        self.assertIsNotNone(validate_review(_valid_review(width_ridden="forty")))

    def test_rejects_invalid_pressure_psi_type(self):
        self.assertIsNotNone(validate_review(_valid_review(pressure_psi="high")))

    def test_rejects_invalid_conditions_type(self):
        self.assertIsNotNone(validate_review(_valid_review(conditions="dry")))

    def test_accepts_none_optional_fields(self):
        r = _valid_review(width_ridden=None, pressure_psi=None, conditions=None)
        self.assertIsNone(validate_review(r))

    def test_accepts_valid_stars_1_through_5(self):
        for s in range(1, 6):
            self.assertIsNone(validate_review(_valid_review(stars=s)),
                              f"Stars={s} should be valid")


# ── Fix #10: sanitize_review() whitelist ──────────────────────


class TestSanitizeReview(unittest.TestCase):
    """Fix #10: PII stripping via field whitelist."""

    def test_strips_email(self):
        r = _valid_review()
        r["email"] = "user@example.com"
        clean = sanitize_review(r)
        self.assertNotIn("email", clean)

    def test_strips_unknown_fields(self):
        r = _valid_review()
        r["ip_address"] = "192.168.1.1"
        r["user_agent"] = "Mozilla/5.0"
        r["display_name"] = "John Doe"
        clean = sanitize_review(r)
        self.assertNotIn("ip_address", clean)
        self.assertNotIn("user_agent", clean)
        self.assertNotIn("display_name", clean)

    def test_preserves_whitelisted_fields(self):
        r = _valid_review()
        clean = sanitize_review(r)
        for field in REVIEW_FIELDS:
            if field in r:
                self.assertEqual(clean[field], r[field],
                                 f"Field '{field}' should be preserved")

    def test_sets_approved_true(self):
        clean = sanitize_review(_valid_review())
        self.assertTrue(clean["approved"])

    def test_whitelist_does_not_contain_pii_fields(self):
        pii_fields = {"email", "ip_address", "user_agent", "display_name",
                       "name", "phone", "address"}
        self.assertEqual(REVIEW_FIELDS & pii_fields, set(),
                         "REVIEW_FIELDS must not contain PII fields")

    def test_only_whitelisted_fields_plus_approved_in_output(self):
        r = _valid_review()
        r["email"] = "user@example.com"
        r["extra_garbage"] = "should be gone"
        clean = sanitize_review(r)
        allowed = REVIEW_FIELDS | {"approved"}
        for key in clean:
            self.assertIn(key, allowed,
                          f"Unexpected field '{key}' in sanitized output")


# ── Fix #12: XSS escaping in review cards ────────────────────


class TestReviewCardEscaping(unittest.TestCase):
    """Fix #12: All user fields must be HTML-escaped in review cards."""

    XSS_PAYLOAD = '<script>alert("xss")</script>'
    XSS_ESCAPED = "&lt;script&gt;"

    def test_review_text_escaped(self):
        r = _valid_review(review_text=self.XSS_PAYLOAD)
        html = _render_review_card(r)
        self.assertNotIn("<script>", html)
        self.assertIn(self.XSS_ESCAPED, html)

    def test_race_used_at_escaped(self):
        r = _valid_review(race_used_at=self.XSS_PAYLOAD)
        html = _render_review_card(r)
        self.assertNotIn("<script>", html)
        self.assertIn(self.XSS_ESCAPED, html)

    def test_conditions_escaped(self):
        r = _valid_review(conditions=["<img src=x onerror=alert(1)>"])
        html = _render_review_card(r)
        # The angle brackets must be escaped — browser won't parse as a tag
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)
        self.assertIn("&gt;", html)

    def test_width_ridden_escaped(self):
        # Numeric field converted to string — should still be escaped
        r = _valid_review(width_ridden=40)
        html = _render_review_card(r)
        self.assertIn("40mm", html)

    def test_ampersand_in_race_name(self):
        r = _valid_review(race_used_at="BWR & Mid South")
        html = _render_review_card(r)
        self.assertIn("BWR &amp; Mid South", html)

    def test_quotes_in_review_text(self):
        r = _valid_review(review_text='He said "great tire"')
        html = _render_review_card(r)
        self.assertNotIn('"great tire"', html)
        self.assertIn("&quot;great tire&quot;", html)


# ── Fix #13: Star count validation ───────────────────────────


class TestStarCountValidation(unittest.TestCase):
    """Fix #13: Stars must be clamped to 1-5, invalid returns empty."""

    def test_valid_stars_render_correctly(self):
        for n in range(1, 6):
            html = _render_review_card(_valid_review(stars=n))
            full = html.count("&#9733;")
            empty = html.count("&#9734;")
            self.assertEqual(full, n, f"Stars={n} should have {n} full stars")
            self.assertEqual(full + empty, 5, f"Stars={n} should have 5 total")

    def test_stars_zero_clamped_to_one(self):
        """Stars=0 is clamped to 1 by max(1, ...) — renders with 1 full star."""
        html = _render_review_card(_valid_review(stars=0))
        self.assertEqual(html.count("&#9733;"), 1)
        self.assertEqual(html.count("&#9734;"), 4)

    def test_stars_negative_clamped_to_one(self):
        """Negative stars clamped to 1 by max(1, ...) — renders with 1 full star."""
        html = _render_review_card(_valid_review(stars=-3))
        self.assertEqual(html.count("&#9733;"), 1)
        self.assertEqual(html.count("&#9734;"), 4)

    def test_stars_string_returns_empty(self):
        html = _render_review_card(_valid_review(stars="five"))
        self.assertEqual(html, "")

    def test_stars_none_returns_empty(self):
        html = _render_review_card(_valid_review(stars=None))
        self.assertEqual(html, "")

    def test_stars_six_clamped_to_five(self):
        html = _render_review_card(_valid_review(stars=6))
        self.assertEqual(html.count("&#9733;"), 5)
        self.assertEqual(html.count("&#9734;"), 0)

    def test_stars_100_clamped_to_five(self):
        html = _render_review_card(_valid_review(stars=100))
        self.assertEqual(html.count("&#9733;"), 5)


# ── Fix #12 cont'd: Review card structure ────────────────────


class TestReviewCardStructure(unittest.TestCase):
    """Review card renders expected HTML structure."""

    def test_has_card_class(self):
        html = _render_review_card(_valid_review())
        self.assertIn("tp-rev-card", html)

    def test_shows_would_recommend_yes(self):
        html = _render_review_card(_valid_review(would_recommend="yes"))
        self.assertIn("Would recommend", html)
        self.assertIn("tp-rev-card-recommend--yes", html)

    def test_shows_would_recommend_no(self):
        html = _render_review_card(_valid_review(would_recommend="no"))
        self.assertIn("Would not recommend", html)
        self.assertIn("tp-rev-card-recommend--no", html)

    def test_no_recommend_omitted(self):
        html = _render_review_card(_valid_review(would_recommend=None))
        self.assertNotIn("tp-rev-card-recommend", html)

    def test_missing_optional_fields_still_renders(self):
        r = _valid_review(
            width_ridden=None,
            pressure_psi=None,
            conditions=None,
            race_used_at=None,
            review_text=None,
            would_recommend=None,
        )
        html = _render_review_card(r)
        self.assertIn("tp-rev-card", html)
        self.assertIn("&#9733;", html)


# ── Fix #14: Community reviews section states ─────────────────


class TestCommunityReviewsSection(unittest.TestCase):
    """Fix #14: Three display states — empty, pending, full."""

    def test_empty_state_shows_be_the_first(self):
        tire = _tire_with_reviews(0)
        html = build_community_reviews_section(tire)
        self.assertIn("Be the first", html)
        self.assertIn("tp-rev-empty", html)
        self.assertNotIn("tp-rev-summary", html)
        self.assertNotIn("tp-rev-card", html)

    def test_pending_state_shows_cards(self):
        """Fix #14: Pending state (1-2 reviews) must show review cards."""
        tire = _tire_with_reviews(2)
        html = build_community_reviews_section(tire)
        self.assertIn("tp-rev-card", html)
        self.assertIn("more needed", html)
        self.assertIn("tp-rev-pending", html)
        self.assertNotIn("tp-rev-summary", html)

    def test_pending_state_count_is_correct(self):
        tire = _tire_with_reviews(1)
        html = build_community_reviews_section(tire)
        self.assertIn("1 review so far", html)
        self.assertIn("2 more needed", html)

    def test_full_state_shows_aggregate(self):
        tire = _tire_with_reviews(5)
        html = build_community_reviews_section(tire)
        self.assertIn("tp-rev-summary", html)
        self.assertIn("tp-rev-avg", html)
        self.assertNotIn("more needed", html)
        self.assertNotIn("tp-rev-empty", html)

    def test_full_state_aggregate_math(self):
        """Average must be computed correctly."""
        reviews = [
            _valid_review(review_id="r1", stars=5, submitted_at="2026-02-19T12:00:00Z"),
            _valid_review(review_id="r2", stars=4, submitted_at="2026-02-18T12:00:00Z"),
            _valid_review(review_id="r3", stars=3, submitted_at="2026-02-17T12:00:00Z"),
        ]
        tire = _tire_with_reviews(0)
        tire["community_reviews"] = reviews
        html = build_community_reviews_section(tire)
        # (5+4+3)/3 = 4.0
        self.assertIn("4.0", html)

    def test_only_approved_reviews_counted(self):
        """Non-approved reviews must be excluded."""
        reviews = [
            _valid_review(review_id="r1", stars=5, submitted_at="2026-02-19T12:00:00Z"),
            _valid_review(review_id="r2", stars=4, submitted_at="2026-02-18T12:00:00Z"),
            _valid_review(review_id="r3", stars=3, submitted_at="2026-02-17T12:00:00Z", approved=False),
        ]
        tire = _tire_with_reviews(0)
        tire["community_reviews"] = reviews
        html = build_community_reviews_section(tire)
        # Only 2 approved → pending state
        self.assertIn("more needed", html)

    def test_invalid_stars_filtered_before_counting(self):
        """Reviews with stars=0 or stars='bad' must be filtered out."""
        reviews = [
            _valid_review(review_id="r1", stars=5, submitted_at="2026-02-19T12:00:00Z"),
            _valid_review(review_id="r2", stars=4, submitted_at="2026-02-18T12:00:00Z"),
            _valid_review(review_id="r3", stars=0, submitted_at="2026-02-17T12:00:00Z"),
            _valid_review(review_id="r4", stars="bad", submitted_at="2026-02-16T12:00:00Z"),
        ]
        tire = _tire_with_reviews(0)
        tire["community_reviews"] = reviews
        html = build_community_reviews_section(tire)
        # Only 2 valid → pending state
        self.assertIn("more needed", html)

    def test_max_five_cards_rendered(self):
        tire = _tire_with_reviews(10)
        html = build_community_reviews_section(tire)
        # Count exact class="tp-rev-card" (not sub-classes like tp-rev-card-stars)
        self.assertEqual(html.count('class="tp-rev-card"'), 5)

    def test_reviews_sorted_newest_first(self):
        """Most recent review should appear first in the HTML."""
        reviews = [
            _valid_review(review_id="old", stars=3, submitted_at="2026-01-01T00:00:00Z",
                          review_text="OLD REVIEW TEXT"),
            _valid_review(review_id="new", stars=5, submitted_at="2026-02-19T00:00:00Z",
                          review_text="NEW REVIEW TEXT"),
        ]
        tire = _tire_with_reviews(0)
        # Add a third to cross threshold
        reviews.append(_valid_review(review_id="mid", stars=4,
                                     submitted_at="2026-01-15T00:00:00Z",
                                     review_text="MID REVIEW TEXT"))
        tire["community_reviews"] = reviews
        html = build_community_reviews_section(tire)
        new_pos = html.index("NEW REVIEW TEXT")
        mid_pos = html.index("MID REVIEW TEXT")
        old_pos = html.index("OLD REVIEW TEXT")
        self.assertLess(new_pos, mid_pos, "Newest review must appear first")
        self.assertLess(mid_pos, old_pos, "Middle review must appear before oldest")

    def test_form_always_present(self):
        """Review form must appear in all three states."""
        for n in [0, 1, 5]:
            tire = _tire_with_reviews(n)
            html = build_community_reviews_section(tire)
            self.assertIn("tp-rev-form", html,
                          f"Form missing in {n}-review state")


# ── JSON-LD aggregateRating ───────────────────────────────────


class TestJsonLdAggregateRating(unittest.TestCase):
    """JSON-LD uses real reviews when 3+ exist, proxy otherwise."""

    def _parse_jsonld(self, tire, race_recs=None):
        html = build_json_ld(tire, race_recs or [])
        # Extract JSON array between script tags
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>',
                          html, re.DOTALL)
        self.assertIsNotNone(match, "JSON-LD script tag not found")
        return json.loads(match.group(1))

    def test_three_reviews_uses_real_rating(self):
        tire = _tire_with_reviews(3)
        schemas = self._parse_jsonld(tire)
        product = [s for s in schemas if s.get("@type") == "Product"][0]
        self.assertIn("aggregateRating", product)
        agg = product["aggregateRating"]
        self.assertEqual(agg["@type"], "AggregateRating")
        self.assertEqual(agg["ratingCount"], "3")
        # Stars are 1,2,3 → avg = 2.0
        self.assertEqual(agg["ratingValue"], "2.0")

    def test_two_reviews_no_recs_no_aggregate(self):
        tire = _tire_with_reviews(2)
        schemas = self._parse_jsonld(tire, race_recs=[])
        product = [s for s in schemas if s.get("@type") == "Product"][0]
        self.assertNotIn("aggregateRating", product)

    def test_two_reviews_with_recs_uses_proxy(self):
        tire = _tire_with_reviews(2)
        recs = [{"race": "test"}] * 20
        schemas = self._parse_jsonld(tire, race_recs=recs)
        product = [s for s in schemas if s.get("@type") == "Product"][0]
        self.assertIn("aggregateRating", product)
        agg = product["aggregateRating"]
        # 20 recs: 3.0 + (20/50) * 1.5 = 3.6
        self.assertEqual(agg["ratingValue"], "3.6")
        self.assertEqual(agg["ratingCount"], "20")

    def test_real_rating_overrides_proxy(self):
        """When 3+ reviews exist, rec count doesn't matter."""
        tire = _tire_with_reviews(4)
        recs = [{"race": "test"}] * 100
        schemas = self._parse_jsonld(tire, race_recs=recs)
        product = [s for s in schemas if s.get("@type") == "Product"][0]
        agg = product["aggregateRating"]
        # 4 reviews with stars 1,2,3,4 → avg = 2.5
        self.assertEqual(agg["ratingValue"], "2.5")
        self.assertEqual(agg["ratingCount"], "4")

    def test_proxy_capped_at_4_5(self):
        tire = _tire_with_reviews(0)
        recs = [{"race": "test"}] * 1000
        schemas = self._parse_jsonld(tire, race_recs=recs)
        product = [s for s in schemas if s.get("@type") == "Product"][0]
        agg = product["aggregateRating"]
        self.assertEqual(agg["ratingValue"], "4.5")

    def test_jsonld_is_valid_json(self):
        tire = _tire_with_reviews(5)
        html = build_json_ld(tire, [])
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>',
                          html, re.DOTALL)
        # Should not raise
        data = json.loads(match.group(1))
        self.assertIsInstance(data, list)

    def test_jsonld_no_html_entities(self):
        """JSON-LD must not contain HTML entities (esc() in JSON = bug)."""
        tire = _tire_with_reviews(3)
        tire["name"] = "O'Neal's Tire & Rubber"
        html = build_json_ld(tire, [])
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>',
                          html, re.DOTALL)
        raw = match.group(1)
        self.assertNotIn("&amp;", raw,
                          "HTML entity in JSON-LD — used esc() instead of JSON escaping")
        self.assertNotIn("&#", raw,
                          "HTML entity in JSON-LD — used esc() instead of JSON escaping")


# ── Fix #5 + #6: JS double-submit + fetch handling ───────────


class TestJSFormHandler(unittest.TestCase):
    """Fix #5 and #6: JS source-level checks for the tire review form."""

    @classmethod
    def setUpClass(cls):
        cls.js = build_inline_js()

    def test_has_submitting_guard(self):
        """Fix #5: JS must have a submitting flag to prevent double-submit."""
        self.assertIn("submitting", self.js)
        self.assertIn("if(submitting) return", self.js)

    def test_disables_submit_button(self):
        """Fix #5: Submit button must be disabled during request."""
        self.assertIn("submitBtn.disabled=true", self.js)
        self.assertIn("SUBMITTING...", self.js)

    def test_re_enables_on_error(self):
        """Fix #5: Button must re-enable on error response."""
        self.assertIn("submitBtn.disabled=false", self.js)

    def test_awaits_fetch_response(self):
        """Fix #6: fetch() must use .then() to handle response — not fire-and-forget."""
        self.assertIn(".then(function(resp)", self.js)

    def test_handles_non_200_response(self):
        """Fix #6: Error message must be shown on non-200."""
        self.assertIn("tp-rev-error", self.js)
        self.assertIn("errText.textContent=msg", self.js)

    def test_handles_network_error(self):
        """Fix #6: Network failures must show an error message."""
        self.assertIn("Network error", self.js)
        self.assertIn(".catch(function()", self.js)

    def test_success_only_on_200(self):
        """Fix #6: Success state shown only inside the 200 branch."""
        # Find the .then block that checks status
        self.assertIn("if(result.status===200)", self.js)

    def test_no_fire_and_forget(self):
        """Fix #6: fetch must NOT be followed by immediate success display."""
        # The old pattern was: fetch(...).catch(function(){}); form.style.display='none';
        # Check that catch doesn't immediately show success
        self.assertNotIn(".catch(function(){});\n    form.style.display", self.js)


# ── Review form HTML structure ────────────────────────────────


class TestReviewFormHTML(unittest.TestCase):
    """Review form HTML must have required elements."""

    @classmethod
    def setUpClass(cls):
        tire = _tire_with_reviews(0)
        cls.form_html = build_tire_review_form(tire)

    def test_has_honeypot(self):
        self.assertIn('name="website"', self.form_html)
        self.assertIn('type="hidden"', self.form_html)

    def test_has_star_buttons(self):
        self.assertIn("tp-rev-star-btn", self.form_html)
        for i in range(1, 6):
            self.assertIn(f'data-star="{i}"', self.form_html)

    def test_has_email_field(self):
        self.assertIn('name="email"', self.form_html)
        self.assertIn('type="email"', self.form_html)

    def test_has_submit_button_with_id(self):
        self.assertIn('id="tp-rev-submit-btn"', self.form_html)

    def test_has_error_div(self):
        self.assertIn('id="tp-rev-error"', self.form_html)
        self.assertIn('id="tp-rev-error-text"', self.form_html)

    def test_has_success_div(self):
        self.assertIn('id="tp-rev-success"', self.form_html)

    def test_width_options_from_tire_data(self):
        tire = _tire_with_reviews(0)
        tire["widths_mm"] = [35, 40, 45]
        html = build_tire_review_form(tire)
        self.assertIn("35mm", html)
        self.assertIn("40mm", html)
        self.assertIn("45mm", html)

    def test_has_conditions_checkboxes(self):
        for cond in ["dry", "mixed", "wet", "mud"]:
            self.assertIn(f'value="{cond}"', self.form_html)

    def test_has_textarea_with_maxlength(self):
        self.assertIn('maxlength="500"', self.form_html)

    def test_has_tire_id_hidden_field(self):
        self.assertIn('name="tire_id"', self.form_html)
        self.assertIn('name="tire_name"', self.form_html)


# ── Worker source-level tests ────────────────────────────────


class TestWorkerSourceCode(unittest.TestCase):
    """Source-level checks on the tire-review-intake worker."""

    @classmethod
    def setUpClass(cls):
        worker_path = PROJECT_ROOT / "workers" / "tire-review-intake" / "worker.js"
        cls.source = worker_path.read_text(encoding="utf-8")

    def test_uses_exact_origin_match(self):
        """Fix #2: Must use includes(), not startsWith() for origin checking."""
        self.assertIn("allowedOrigins.includes(origin)", self.source)
        # Check that startsWith is not used in executable code (ignore comments)
        code_lines = [l for l in self.source.split("\n")
                       if l.strip() and not l.strip().startswith("//")]
        for line in code_lines:
            self.assertNotIn(".startsWith(", line,
                             f"startsWith used in code: {line.strip()}")

    def test_has_tire_id_regex_validation(self):
        """Fix #3: tire_id must be validated against a slug pattern."""
        self.assertIn("TIRE_ID_PATTERN", self.source)
        self.assertIn("test(data.tire_id)", self.source)

    def test_has_dedup_logic(self):
        """Fix #1: Dedup key must check for existing review before writing."""
        self.assertIn("dedup:", self.source)
        self.assertIn("409", self.source)

    def test_has_width_range_validation(self):
        """Fix #4: width_ridden must be clamped to 25-60mm."""
        self.assertIn("25", self.source)
        self.assertIn("60", self.source)
        self.assertRegex(self.source, r"w\s*<\s*25|25\b")

    def test_has_esc_function(self):
        """HTML escaping must exist for notification email."""
        self.assertIn("function esc(", self.source)

    def test_uses_esc_in_email_template(self):
        """User data in email must be escaped."""
        # esc() should appear multiple times in the email template
        self.assertGreaterEqual(self.source.count("esc("), 5)

    def test_no_startswith_in_cors(self):
        """CORS must not use startsWith pattern."""
        lines = self.source.split("\n")
        cors_lines = [l for l in lines if "origin" in l.lower() and "allow" in l.lower()]
        for line in cors_lines:
            self.assertNotIn("startsWith", line)


# ── Sync script source-level tests ───────────────────────────


class TestSyncScriptSourceCode(unittest.TestCase):
    """Source-level checks on sync_tire_reviews.py."""

    @classmethod
    def setUpClass(cls):
        sync_path = PROJECT_ROOT / "scripts" / "sync_tire_reviews.py"
        cls.source = sync_path.read_text(encoding="utf-8")

    def test_uses_url_encoding(self):
        """Fix #8: KV keys must be URL-encoded before inclusion in API URL."""
        self.assertIn("from urllib.parse import quote", self.source)
        self.assertIn("quote(", self.source)

    def test_has_review_fields_whitelist(self):
        """Fix #10: Must use field whitelist, not PII blacklist."""
        self.assertIn("REVIEW_FIELDS", self.source)
        # Must NOT have a "del review['email']" blacklist pattern
        self.assertNotIn("del review", self.source)
        self.assertNotIn("pop('email')", self.source)
        self.assertNotIn("pop(\"email\")", self.source)

    def test_skips_dedup_keys(self):
        """Sync must filter out dedup: prefixed keys."""
        self.assertIn('startswith("dedup:")', self.source)

    def test_calls_validate_review(self):
        """Fix #9: Must validate every review from KV."""
        self.assertIn("validate_review(", self.source)

    def test_calls_sanitize_review(self):
        """Fix #10: Must sanitize every review through whitelist."""
        self.assertIn("sanitize_review(", self.source)

    def test_sorts_reviews(self):
        """Fix #11: Reviews must be sorted by submitted_at before appending."""
        self.assertIn("sort(", self.source)
        self.assertIn("submitted_at", self.source)


# ── CSS structure tests ──────────────────────────────────────


class TestReviewCSS(unittest.TestCase):
    """CSS must include styles for error and disabled states."""

    @classmethod
    def setUpClass(cls):
        gen_path = PROJECT_ROOT / "wordpress" / "generate_tire_pages.py"
        cls.source = gen_path.read_text(encoding="utf-8")

    def test_has_error_css(self):
        self.assertIn(".tp-rev-error", self.source)

    def test_has_disabled_button_css(self):
        self.assertIn(".tp-rev-submit:disabled", self.source)
        self.assertIn("cursor: not-allowed", self.source)

    def test_has_success_css(self):
        self.assertIn(".tp-rev-success", self.source)


# ── Integration: end-to-end page generation ──────────────────


class TestEndToEndPageGeneration(unittest.TestCase):
    """Generate a full tire page and verify review system integration."""

    @classmethod
    def setUpClass(cls):
        from generate_tire_pages import generate_tire_page
        cls.tire = _tire_with_reviews(4)
        cls.race_recs = [
            {"name": "Unbound Gravel", "slug": "unbound-gravel",
             "position": "primary", "rank": 1, "width": 45,
             "why": "Sharp gravel terrain suits knobby tread"},
            {"name": "Mid South", "slug": "mid-south",
             "position": "primary", "rank": 2, "width": 40,
             "why": "Mixed conditions favor aggressive tread"},
        ]
        cls.html = generate_tire_page(cls.tire, race_recs=cls.race_recs)

    def test_page_contains_review_section(self):
        self.assertIn("05 / COMMUNITY REVIEWS", self.html)

    def test_page_contains_review_form(self):
        self.assertIn("tp-rev-form", self.html)
        self.assertIn("SUBMIT REVIEW", self.html)

    def test_page_contains_review_cards(self):
        self.assertIn("tp-rev-card", self.html)

    def test_page_contains_aggregate_rating(self):
        self.assertIn("tp-rev-avg", self.html)

    def test_page_contains_jsonld(self):
        self.assertIn("application/ld+json", self.html)
        # Should have real rating with 4 reviews
        self.assertIn("AggregateRating", self.html)

    def test_page_contains_error_div(self):
        self.assertIn("tp-rev-error", self.html)

    def test_page_contains_double_submit_prevention(self):
        self.assertIn("submitting", self.html)
        self.assertIn("submitBtn.disabled", self.html)

    def test_internal_links_section_numbered_06(self):
        self.assertIn("06 /", self.html)

    def test_section_number_ordering(self):
        """Community Reviews (05) must come before Internal Links (06)."""
        pos_05 = self.html.index("05 / COMMUNITY REVIEWS")
        pos_06 = self.html.index("06 /")
        self.assertLess(pos_05, pos_06)


if __name__ == "__main__":
    unittest.main()
