"""Hardcoded QC tests for workout showcase eligibility on race pages.

Tests the eligibility filtering system that selects 5 showcase workouts
per race page, verifying:
    - Bad picks never appear (e.g., Double Day Simulation for short races)
    - Every race gets exactly 5 eligible workouts
    - No recovery/assessment/taper workouts are showcased
    - Ultra-distance races get appropriate workouts
    - Climbing workouts only appear for climbing-heavy races
    - Uniqueness across races (no mass duplication)

These tests run against the generated preview JSONs in web/race-packs/
and mirror the eligibility logic from generate_neo_brutalist.py.
"""

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import pytest

# ── Constants mirrored from generate_neo_brutalist.py ──────────────

# Eligibility rules (source of truth: generate_neo_brutalist.py SHOWCASE_ELIGIBILITY)
SHOWCASE_ELIGIBILITY = {
    # Durability
    'Tired VO2max':          {'min_dist': 60},
    'Double Day Simulation': {'min_dist': 200},
    'Progressive Fatigue':   {},
    # VO2max
    '5x3 VO2 Classic':        {'max_dist': 400},
    'Descending VO2 Pyramid': {'max_dist': 400},
    'Norwegian 4x8':          {'max_dist': 400},
    # HVLI_Extended
    'HVLI Extended Z2':  {'min_dist': 80},
    'Multi-Hour Z2':     {'min_dist': 100},
    'Back-to-Back Long': {'min_dist': 120},
    # Race_Simulation
    'Breakaway Simulation': {'max_dist': 300},
    'Variable Pace Chaos':  {'max_dist': 300},
    'Sector Simulation':    {'max_dist': 300},
    # Threshold
    'Single Sustained Threshold': {},
    'Threshold Ramps':            {},
    'Descending Threshold':       {},
    # G_Spot
    'G-Spot Standard':  {},
    'G-Spot Extended':  {'min_dist': 60},
    'Criss-Cross':      {},
    # Climbing
    'Seated/Standing Climbs':    {'min_climbing': 5},
    'Variable Grade Simulation': {'min_climbing': 5},
    # Over_Under
    'Classic Over-Unders': {},
    'Ladder Over-Unders':  {},
    # Gravel_Specific
    'Surge and Settle':    {'max_dist': 300},
    'Terrain Microbursts': {'max_dist': 300},
    # Endurance
    'Pre-Race Openers':    {'_never_showcase': True},
    'Terrain Simulation Z2': {},
    # Critical_Power
    'Above CP Repeats':  {'max_dist': 300},
    'W-Prime Depletion': {'max_dist': 300},
    # Anaerobic
    '2min Killers':  {'max_dist': 200},
    '90sec Repeats': {'max_dist': 200},
    # Sprint
    'Attack Repeats':  {'max_dist': 200},
    'Sprint Buildups': {'max_dist': 200},
    # Norwegian_Double
    'Norwegian 4x8 Classic': {'max_dist': 400},
    'Double Threshold':      {'max_dist': 400},
    # SFR/Force
    'SFR Low Cadence': {},
    'Force Repeats':   {},
    # Cadence
    'High Cadence Drills': {},
    'Cadence Pyramids':    {},
    # Blended
    'Z2 + VO2 Combo':      {'max_dist': 300},
    'Endurance with Spikes': {},
    # Tempo
    'Tempo Blocks':    {},
    'Extended Tempo':  {'min_dist': 60},
    # Assessments — never showcase
    'MAF Capped Ride':  {'_never_showcase': True},
    'LT1 Assessment':   {'_never_showcase': True},
    # Recovery — never showcase
    'Easy Spin':        {'_never_showcase': True},
    'Active Recovery':  {'_never_showcase': True},
}

# Workouts that must NEVER appear on any race page
NEVER_SHOWCASE = {'Pre-Race Openers', 'Easy Spin', 'Active Recovery',
                  'MAF Capped Ride', 'LT1 Assessment'}

# Showcasable workout names (those with eligibility entries, not never_showcase)
SHOWCASABLE = {k for k, v in SHOWCASE_ELIGIBILITY.items()
               if not v.get('_never_showcase')}


# ── Helpers ────────────────────────────────────────────────────────

PACK_DIR = Path(__file__).resolve().parent.parent / 'web' / 'race-packs'


def _workout_eligible(name: str, distance_mi: float, demands: dict) -> bool:
    """Mirror of _workout_eligible from generate_neo_brutalist.py."""
    rules = SHOWCASE_ELIGIBILITY.get(name, {})
    if rules.get('_never_showcase'):
        return False
    if 'min_dist' in rules and distance_mi < rules['min_dist']:
        return False
    if 'max_dist' in rules and distance_mi > rules['max_dist']:
        return False
    if 'min_climbing' in rules and demands.get('climbing', 0) < rules['min_climbing']:
        return False
    return True


def _select_showcase_workouts(preview: dict) -> list:
    """Simulate the workout selection logic from build_train_for_race."""
    slug = preview['slug']
    dist = preview.get('distance_mi', 0)
    demands = preview.get('demands', {})
    top_categories = preview.get('top_categories', [])

    selected = []
    for tc in top_categories:
        if len(selected) >= 5:
            break
        workouts_list = tc.get('workouts', [])
        eligible = [w for w in workouts_list
                    if w in SHOWCASABLE
                    and _workout_eligible(w, dist, demands)]
        if not eligible:
            continue
        h = int(hashlib.md5(f"{slug}-{tc['category']}".encode()).hexdigest(), 16)
        pick = eligible[h % len(eligible)]
        selected.append(pick)

    return selected


def _load_all_previews() -> list:
    """Load all race pack preview JSONs."""
    if not PACK_DIR.exists():
        pytest.skip("web/race-packs/ directory not found")
    previews = []
    for f in sorted(PACK_DIR.glob('*.json')):
        with open(f) as fh:
            previews.append(json.load(fh))
    if not previews:
        pytest.skip("No preview JSONs found")
    return previews


# Cache all previews for test session performance
@pytest.fixture(scope="module")
def all_previews():
    return _load_all_previews()


@pytest.fixture(scope="module")
def all_selections(all_previews):
    """Pre-compute showcase selections for all races."""
    return {p['slug']: _select_showcase_workouts(p) for p in all_previews}


# ── TestCoverage: Every race gets 5 workouts ──────────────────────


class TestCoverage:
    """Every race must get exactly 5 showcase workouts."""

    def test_all_races_get_5_workouts(self, all_previews, all_selections):
        """No race should have fewer than 5 eligible showcase workouts."""
        failures = []
        for p in all_previews:
            slug = p['slug']
            count = len(all_selections[slug])
            if count < 5:
                failures.append(f"{slug} ({p.get('distance_mi', 0)}mi): only {count}")
        assert not failures, (
            f"{len(failures)} races have < 5 showcase workouts:\n"
            + "\n".join(failures)
        )

    def test_ultra_distance_races_get_5(self, all_previews, all_selections):
        """Ultra-distance races (>400mi) must get 5 workouts despite heavy filtering."""
        ultra = [p for p in all_previews if p.get('distance_mi', 0) > 400]
        failures = []
        for p in ultra:
            slug = p['slug']
            count = len(all_selections[slug])
            if count < 5:
                failures.append(f"{slug} ({p['distance_mi']}mi): only {count}")
        assert not failures, (
            f"Ultra races with < 5 workouts:\n" + "\n".join(failures)
        )

    def test_short_races_get_5(self, all_previews, all_selections):
        """Short races (<50mi) must get 5 workouts."""
        short = [p for p in all_previews if 0 < p.get('distance_mi', 0) < 50]
        failures = []
        for p in short:
            slug = p['slug']
            count = len(all_selections[slug])
            if count < 5:
                failures.append(f"{slug} ({p['distance_mi']}mi): only {count}")
        assert not failures, (
            f"Short races with < 5 workouts:\n" + "\n".join(failures)
        )


# ── TestBadPicks: Specific known-bad patterns never appear ────────


class TestBadPicks:
    """Hardcoded tests for specific coaching-quality failures."""

    def test_double_day_never_for_single_day_races(self, all_previews, all_selections):
        """Double Day Simulation must never appear for races under 200 miles.

        Root cause: 'Double Day Simulation' implies multi-day training volume.
        Most gravel races are single-day events. Showing this workout for a
        50-mile race is absurd and insults the intelligence of any coach.
        """
        failures = []
        for p in all_previews:
            if p.get('distance_mi', 0) < 200:
                if 'Double Day Simulation' in all_selections[p['slug']]:
                    failures.append(f"{p['slug']} ({p['distance_mi']}mi)")
        assert not failures, (
            f"Double Day Simulation shown for single-day races:\n"
            + "\n".join(failures)
        )

    def test_breakaway_never_for_ultra(self, all_previews, all_selections):
        """Breakaway Simulation must never appear for races over 300 miles.

        Root cause: Ultra-bikepacking races (Tour Divide, Trans Am) are
        self-supported multi-day events. There are no 'breakaways' — it's
        individual time trial over thousands of miles.
        """
        failures = []
        for p in all_previews:
            if p.get('distance_mi', 0) > 300:
                picks = all_selections[p['slug']]
                if 'Breakaway Simulation' in picks:
                    failures.append(f"{p['slug']} ({p['distance_mi']}mi)")
        assert not failures, (
            f"Breakaway Simulation shown for ultra races:\n"
            + "\n".join(failures)
        )

    def test_variable_pace_chaos_never_for_ultra(self, all_previews, all_selections):
        """Variable Pace Chaos must never appear for races over 300 miles."""
        failures = []
        for p in all_previews:
            if p.get('distance_mi', 0) > 300:
                if 'Variable Pace Chaos' in all_selections[p['slug']]:
                    failures.append(f"{p['slug']} ({p['distance_mi']}mi)")
        assert not failures, (
            f"Variable Pace Chaos shown for ultra races:\n"
            + "\n".join(failures)
        )

    def test_tired_vo2max_never_for_short_races(self, all_previews, all_selections):
        """Tired VO2max must never appear for races under 60 miles.

        Root cause: Tired VO2max has a 2-hour Zone 2 base ride before the
        intervals. For a 40-mile race lasting ~2.5 hours, the warmup alone
        is nearly the race duration.
        """
        failures = []
        for p in all_previews:
            if 0 < p.get('distance_mi', 0) < 60:
                if 'Tired VO2max' in all_selections[p['slug']]:
                    failures.append(f"{p['slug']} ({p['distance_mi']}mi)")
        assert not failures, (
            f"Tired VO2max shown for short races:\n"
            + "\n".join(failures)
        )

    def test_never_showcase_workouts(self, all_previews, all_selections):
        """Recovery, assessment, and taper workouts must never be showcased.

        Pre-Race Openers = taper workout, not training.
        Easy Spin / Active Recovery = recovery, not training.
        MAF Capped Ride / LT1 Assessment = assessment, not training.
        """
        failures = []
        for p in all_previews:
            for pick in all_selections[p['slug']]:
                if pick in NEVER_SHOWCASE:
                    failures.append(f"{p['slug']}: {pick}")
        assert not failures, (
            f"Never-showcase workouts appeared:\n" + "\n".join(failures)
        )

    def test_vo2_never_for_ultra_bikepacking(self, all_previews, all_selections):
        """VO2max workouts should not appear for races over 400 miles.

        Root cause: Norwegian 4x8 and Descending VO2 Pyramid are
        race-specific intensity workouts that make no sense for
        2000+ mile self-supported events.
        """
        vo2_workouts = {'5x3 VO2 Classic', 'Descending VO2 Pyramid', 'Norwegian 4x8'}
        failures = []
        for p in all_previews:
            if p.get('distance_mi', 0) > 400:
                picks = all_selections[p['slug']]
                bad = vo2_workouts & set(picks)
                if bad:
                    failures.append(f"{p['slug']} ({p['distance_mi']}mi): {bad}")
        assert not failures, (
            f"VO2max workouts shown for ultra-bikepacking:\n"
            + "\n".join(failures)
        )

    def test_climbing_workouts_need_climbing_demand(self, all_previews, all_selections):
        """Climbing workouts must only appear for races with climbing demand >= 5."""
        climbing_workouts = {'Seated/Standing Climbs', 'Variable Grade Simulation'}
        failures = []
        for p in all_previews:
            climbing = p.get('demands', {}).get('climbing', 0)
            if climbing < 5:
                picks = all_selections[p['slug']]
                bad = climbing_workouts & set(picks)
                if bad:
                    failures.append(f"{p['slug']} (climbing={climbing}): {bad}")
        assert not failures, (
            f"Climbing workouts shown for flat races:\n"
            + "\n".join(failures)
        )

    def test_anaerobic_never_for_long_races(self, all_previews, all_selections):
        """Anaerobic/sprint workouts should not appear for races over 200 miles."""
        anaerobic_workouts = {'2min Killers', '90sec Repeats',
                              'Attack Repeats', 'Sprint Buildups'}
        failures = []
        for p in all_previews:
            if p.get('distance_mi', 0) > 200:
                picks = all_selections[p['slug']]
                bad = anaerobic_workouts & set(picks)
                if bad:
                    failures.append(f"{p['slug']} ({p['distance_mi']}mi): {bad}")
        assert not failures, (
            f"Anaerobic/sprint workouts shown for long races:\n"
            + "\n".join(failures)
        )


# ── TestSpecificRaces: Named race spot-checks ─────────────────────


class TestSpecificRaces:
    """Spot-check specific races an expert coach would scrutinize."""

    def _get_picks(self, all_previews, all_selections, slug):
        matches = [p for p in all_previews if p['slug'] == slug]
        if not matches:
            pytest.skip(f"{slug} not found in previews")
        return all_selections[slug], matches[0]

    def test_tour_divide_no_race_sim(self, all_previews, all_selections):
        """Tour Divide (2745mi): no race simulation or VO2max workouts."""
        picks, p = self._get_picks(all_previews, all_selections, 'tour-divide')
        bad = {'Breakaway Simulation', 'Variable Pace Chaos', 'Sector Simulation',
               '5x3 VO2 Classic', 'Descending VO2 Pyramid', 'Norwegian 4x8'}
        assert not (bad & set(picks)), f"Tour Divide bad picks: {bad & set(picks)}"

    def test_tour_divide_has_durability(self, all_previews, all_selections):
        """Tour Divide should include a durability workout."""
        picks, _ = self._get_picks(all_previews, all_selections, 'tour-divide')
        durability_workouts = {'Progressive Fatigue', 'Tired VO2max', 'Double Day Simulation'}
        assert durability_workouts & set(picks), (
            f"Tour Divide missing durability workout. Got: {picks}"
        )

    def test_trans_am_no_race_sim(self, all_previews, all_selections):
        """Trans Am (4233mi): no race simulation workouts."""
        picks, _ = self._get_picks(all_previews, all_selections, 'trans-am-bike-race')
        bad = {'Breakaway Simulation', 'Variable Pace Chaos', 'Sector Simulation'}
        assert not (bad & set(picks)), f"Trans Am bad picks: {bad & set(picks)}"

    def test_mid_south_no_double_day(self, all_previews, all_selections):
        """Mid South (100mi): no Double Day Simulation."""
        picks, _ = self._get_picks(all_previews, all_selections, 'mid-south')
        assert 'Double Day Simulation' not in picks

    def test_rasputitsa_no_tired_vo2(self, all_previews, all_selections):
        """Rasputitsa (46mi): no Tired VO2max (2hr base > race duration)."""
        picks, _ = self._get_picks(all_previews, all_selections, 'rasputitsa')
        assert 'Tired VO2max' not in picks

    def test_unbound_200_has_durability(self, all_previews, all_selections):
        """Unbound 200 (200mi): should include a durability workout."""
        picks, _ = self._get_picks(all_previews, all_selections, 'unbound-200')
        durability = {'Progressive Fatigue', 'Tired VO2max', 'Double Day Simulation'}
        assert durability & set(picks), f"Unbound 200 missing durability. Got: {picks}"

    def test_leadville_has_climbing(self, all_previews, all_selections):
        """Leadville 100: should include climbing or threshold workout."""
        picks, _ = self._get_picks(all_previews, all_selections, 'leadville-100')
        climbing_related = {
            'Seated/Standing Climbs', 'Variable Grade Simulation',
            'Single Sustained Threshold', 'Threshold Ramps', 'Descending Threshold',
            'Classic Over-Unders', 'Ladder Over-Unders',
        }
        assert climbing_related & set(picks), (
            f"Leadville 100 missing climbing workout. Got: {picks}"
        )


# ── TestUniqueness: Cross-race deduplication ──────────────────────


class TestUniqueness:
    """Verify workout selections are sufficiently varied across races."""

    def test_unique_combo_ratio(self, all_previews, all_selections):
        """At least 75% of races should have unique workout combos."""
        combos = [tuple(sorted(picks)) for picks in all_selections.values()]
        unique = len(set(combos))
        total = len(combos)
        ratio = unique / total
        assert ratio >= 0.75, (
            f"Only {unique}/{total} ({ratio:.0%}) unique combos. "
            f"Need >= 75%."
        )

    def test_max_duplication_capped(self, all_previews, all_selections):
        """No single workout combo should appear for more than 5 races."""
        combos = Counter(
            tuple(sorted(picks)) for picks in all_selections.values()
        )
        max_dupe = combos.most_common(1)[0][1]
        assert max_dupe <= 5, (
            f"Max duplication is {max_dupe} races. "
            f"Combo: {combos.most_common(1)[0][0]}"
        )

    def test_all_context_text_unique(self, all_previews):
        """Every race should have unique workout context text."""
        all_context = []
        for p in all_previews:
            context_texts = [
                tc.get('workout_context', '')
                for tc in p.get('top_categories', [])
            ]
            full_context = '|'.join(context_texts)
            all_context.append((p['slug'], full_context))

        seen = {}
        dupes = []
        for slug, ctx in all_context:
            if ctx in seen:
                dupes.append(f"{slug} == {seen[ctx]}")
            else:
                seen[ctx] = slug
        assert not dupes, (
            f"{len(dupes)} races with duplicate context:\n"
            + "\n".join(dupes[:10])
        )


# ── TestEligibilityRules: Rule consistency ────────────────────────


class TestEligibilityRules:
    """Verify the eligibility rules themselves are consistent."""

    def test_never_showcase_list_complete(self):
        """All recovery/assessment workouts must be in the never-showcase set."""
        for name in NEVER_SHOWCASE:
            rules = SHOWCASE_ELIGIBILITY.get(name, {})
            assert rules.get('_never_showcase'), (
                f"{name} should have _never_showcase=True"
            )

    def test_min_dist_less_than_max_dist(self):
        """No workout should have min_dist > max_dist (contradictory)."""
        for name, rules in SHOWCASE_ELIGIBILITY.items():
            if 'min_dist' in rules and 'max_dist' in rules:
                assert rules['min_dist'] < rules['max_dist'], (
                    f"{name}: min_dist={rules['min_dist']} > max_dist={rules['max_dist']}"
                )

    def test_all_workouts_have_eligibility_entry(self, all_previews):
        """Every workout name in preview JSONs should have an eligibility rule."""
        all_workouts = set()
        for p in all_previews:
            for tc in p.get('top_categories', []):
                for w in tc.get('workouts', []):
                    all_workouts.add(w)
        missing = all_workouts - set(SHOWCASE_ELIGIBILITY.keys())
        assert not missing, (
            f"Workouts missing eligibility rules: {missing}"
        )

    def test_eligibility_rules_not_too_restrictive(self):
        """At least 20 workouts should be showcasable (not never_showcase)."""
        showcasable = [k for k, v in SHOWCASE_ELIGIBILITY.items()
                       if not v.get('_never_showcase')]
        assert len(showcasable) >= 20, (
            f"Only {len(showcasable)} showcasable workouts (need >= 20)"
        )


# ── TestPreviewJSON: Structural requirements ──────────────────────


class TestPreviewJSON:
    """Verify preview JSON structure supports the page generator."""

    def test_all_previews_have_distance(self, all_previews):
        """Every preview must have distance_mi for eligibility filtering."""
        missing = [p['slug'] for p in all_previews
                   if 'distance_mi' not in p]
        assert not missing, (
            f"Previews missing distance_mi: {missing[:10]}"
        )

    def test_all_previews_have_demands(self, all_previews):
        """Every preview must have demands dict with 8 dimensions."""
        expected_dims = {'durability', 'climbing', 'vo2_power', 'threshold',
                         'technical', 'heat_resilience', 'altitude', 'race_specificity'}
        failures = []
        for p in all_previews:
            dims = set(p.get('demands', {}).keys())
            if dims != expected_dims:
                failures.append(f"{p['slug']}: {expected_dims - dims}")
        assert not failures, (
            f"Previews with wrong demand dimensions:\n"
            + "\n".join(failures[:10])
        )

    def test_all_previews_have_enough_categories(self, all_previews):
        """Every preview must have >= 5 top_categories for the page generator
        to find 5 eligible workouts after filtering."""
        failures = []
        for p in all_previews:
            count = len(p.get('top_categories', []))
            if count < 5:
                failures.append(f"{p['slug']}: only {count} categories")
        assert not failures, (
            f"Previews with < 5 categories:\n"
            + "\n".join(failures[:10])
        )

    def test_all_categories_have_workout_context(self, all_previews):
        """Every top_category must have a workout_context string."""
        failures = []
        for p in all_previews:
            for tc in p.get('top_categories', []):
                if not tc.get('workout_context'):
                    failures.append(f"{p['slug']}/{tc['category']}")
        assert not failures, (
            f"Categories missing workout_context:\n"
            + "\n".join(failures[:10])
        )

    def test_all_previews_have_race_overlay(self, all_previews):
        """Every preview should have a race_overlay dict (may be empty for mild races)."""
        failures = [p['slug'] for p in all_previews
                    if 'race_overlay' not in p]
        assert not failures, (
            f"Previews missing race_overlay:\n" + "\n".join(failures[:10])
        )
