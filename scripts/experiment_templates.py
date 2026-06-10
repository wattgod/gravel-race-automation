#!/usr/bin/env python3
"""
Hypothesis templates for A/B testing — organized by page type.

Each template defines a testable hypothesis with 3 variants (control + 2).
Templates are gravel-cycling-specific and written in plain language.

IMPORTANT: Every template selector MUST reference an actual data-ab attribute
that exists in the rendered HTML. The valid attributes are:

  Homepage (generate_homepage.py):
    - data-ab="hero_tagline"        Hero tagline text
    - data-ab="training_price"      Training plan price/description line
    - data-ab="training_cta_btn"    Training plan CTA button text
    - data-ab="coaching_scarcity"   Coaching card scarcity/description line

  About page (generate_about.py):
    - data-ab="training_price"      Training plan price/description line
    - data-ab="training_cta_btn"    Training plan CTA button text
    - data-ab="coaching_scarcity"   Coaching card scarcity/description line

  Race pages (generate_neo_brutalist.py):
    - data-ab="race_sticky_cta"     Sticky CTA bar button text
    - data-ab="race_coaching_cta"   Coaching teaser CTA button text

Do NOT invent new data-ab selectors without first adding the corresponding
attribute to the relevant generator.

Usage:
    from experiment_templates import TEMPLATES, get_next_template, validate_selectors

    template = get_next_template("homepage_about", used_ids=["price_daily_vs_weekly"])
    errors = validate_selectors()  # should return []
"""

from __future__ import annotations

# ── Valid data-ab selectors (keep in sync with generators) ───

VALID_SELECTORS: dict[str, list[str]] = {
    "hero_tagline": ["/", "/index.html"],
    "training_price": ["/", "/index.html", "/about/"],
    "training_cta_btn": ["/", "/index.html", "/about/"],
    "coaching_scarcity": ["/", "/index.html", "/about/"],
    "race_sticky_cta": ["/race/*"],
    "race_coaching_cta": ["/race/*"],
}


def _selector(attr: str) -> str:
    """Build a CSS selector from a data-ab attribute name."""
    return f"[data-ab='{attr}']"


# ── Templates by page type ───────────────────────────────────

TEMPLATES: dict[str, list[dict]] = {
    "homepage_about": [
        # ── Hero tagline (homepage only) ──
        {
            "id": "hero_tagline_voice",
            "description": "Test first-person vs third-person hero tagline",
            "selector": _selector("hero_tagline"),
            "pages": ["/", "/index.html"],
            "conversion_selector": "[data-ga='hero_cta_click'], [data-ga='hero_search'] button",
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "328 races. 15 criteria. 4,920 scores — all assigned by hand. Zero sponsors. Zero pay-to-play.",
                },
                {
                    "id": "variant_a",
                    "name": "short_direct",
                    "content": "Every gravel race in America. Scored by hand. No sponsors.",
                },
                {
                    "id": "variant_b",
                    "name": "first_person",
                    "content": "I read every Reddit thread, registration page, and Strava segment so you don't have to.",
                },
            ],
        },
        {
            "id": "hero_tagline_proof",
            "description": "Test proof-oriented tagline variants",
            "selector": _selector("hero_tagline"),
            "pages": ["/", "/index.html"],
            "conversion_selector": "[data-ga='hero_cta_click'], [data-ga='hero_search'] button",
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "328 races. 15 criteria. 4,920 scores — all assigned by hand. Zero sponsors. Zero pay-to-play.",
                },
                {
                    "id": "variant_a",
                    "name": "hours_research",
                    "content": "2,000+ hours of race research. Zero sponsors.",
                },
                {
                    "id": "variant_b",
                    "name": "rider_trust",
                    "content": "Riders in 43 states trust these scores. No sponsors. No pay-to-play.",
                },
            ],
        },
        # ── Training price framing ──
        {
            "id": "price_daily_vs_weekly",
            "description": "Test daily vs weekly price anchor on training plans",
            "selector": _selector("training_price"),
            "pages": ["/", "/index.html", "/about/"],
            "conversion_selector": _selector("training_cta_btn"),
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "Race-specific. Built for your target event. $2/day.",
                },
                {
                    "id": "variant_a",
                    "name": "weekly",
                    "content": "Race-specific. Built for your target event. $15/week.",
                },
                {
                    "id": "variant_b",
                    "name": "per_ride",
                    "content": "Race-specific. Built for your target event. ~$2 per ride.",
                },
            ],
        },
        {
            "id": "price_comparison_object",
            "description": "Test what riders compare plan cost to",
            "selector": _selector("training_price"),
            "pages": ["/", "/index.html", "/about/"],
            "conversion_selector": _selector("training_cta_btn"),
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "Less than your race hotel — $2/day.",
                },
                {
                    "id": "variant_a",
                    "name": "gel_anchor",
                    "content": "Less than one gel per ride — $15/week.",
                },
                {
                    "id": "variant_b",
                    "name": "entry_fee",
                    "content": "Your entry fee was $175. Your plan is $2/day.",
                },
            ],
        },
        # ── Training CTA button text ──
        {
            "id": "cta_button_verb",
            "description": "Test action verb on training CTA button",
            "selector": _selector("training_cta_btn"),
            "pages": ["/", "/index.html", "/about/"],
            "conversion_selector": _selector("training_cta_btn"),
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "BUILD MY PLAN",
                },
                {
                    "id": "variant_a",
                    "name": "get_plan",
                    "content": "GET MY PLAN",
                },
                {
                    "id": "variant_b",
                    "name": "start_training",
                    "content": "START TRAINING",
                },
            ],
        },
        # ── Coaching scarcity ──
        {
            "id": "scarcity_coaching_slots",
            "description": "Test scarcity framing specificity for coaching",
            "selector": _selector("coaching_scarcity"),
            "pages": ["/", "/index.html", "/about/"],
            "conversion_selector": "[data-cta='coaching_apply']",
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "A human in your corner. Adapts week to week. Limited spots.",
                },
                {
                    "id": "variant_a",
                    "name": "number",
                    "content": "A human in your corner. Adapts week to week. 20 athletes/month.",
                },
                {
                    "id": "variant_b",
                    "name": "window",
                    "content": "A human in your corner. Adapts week to week. Next window: April.",
                },
            ],
        },
        {
            "id": "scarcity_coaching_framing",
            "description": "Test coaching value framing in scarcity line",
            "selector": _selector("coaching_scarcity"),
            "pages": ["/", "/index.html", "/about/"],
            "conversion_selector": "[data-cta='coaching_apply']",
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "A human in your corner. Adapts week to week. Limited spots.",
                },
                {
                    "id": "variant_a",
                    "name": "price_anchor",
                    "content": "1:1 coaching. $50/week. Cancel anytime.",
                },
                {
                    "id": "variant_b",
                    "name": "vs_generic",
                    "content": "Not a template. Not a group plan. 1:1 coaching. $200 every 4 weeks.",
                },
            ],
        },
    ],

    "race_pages": [
        # ── Sticky CTA bar ──
        {
            "id": "race_cta_verb",
            "description": "Test race-specific action verbs on sticky CTA",
            "selector": _selector("race_sticky_cta"),
            "pages": ["/race/*"],
            "conversion_selector": "[data-cta='build_plan'], #gg-sticky-cta-link",
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "BUILD MY PLAN — $15/WK",
                },
                {
                    "id": "variant_a",
                    "name": "race_specific",
                    "content": "TRAIN FOR THIS RACE — $15/WK",
                },
                {
                    "id": "variant_b",
                    "name": "get_plan",
                    "content": "GET YOUR RACE PLAN — $15/WK",
                },
            ],
        },
        {
            "id": "race_cta_urgency",
            "description": "Test time-anchored CTA vs generic on race pages",
            "selector": _selector("race_sticky_cta"),
            "pages": ["/race/*"],
            "conversion_selector": "[data-cta='build_plan'], #gg-sticky-cta-link",
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "BUILD MY PLAN — $15/WK",
                },
                {
                    "id": "variant_a",
                    "name": "build_phase",
                    "content": "START YOUR BUILD PHASE — $15/WK",
                },
                {
                    "id": "variant_b",
                    "name": "see_plan",
                    "content": "SEE YOUR TRAINING PLAN — $15/WK",
                },
            ],
        },
        {
            "id": "race_cta_price_frame",
            "description": "Test price framing in sticky CTA",
            "selector": _selector("race_sticky_cta"),
            "pages": ["/race/*"],
            "conversion_selector": "[data-cta='build_plan'], #gg-sticky-cta-link",
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "BUILD MY PLAN — $15/WK",
                },
                {
                    "id": "variant_a",
                    "name": "daily_price",
                    "content": "BUILD MY PLAN — $2/DAY",
                },
                {
                    "id": "variant_b",
                    "name": "no_price",
                    "content": "BUILD MY RACE PLAN",
                },
            ],
        },
        # ── Coaching teaser CTA ──
        {
            "id": "race_coaching_verb",
            "description": "Test coaching CTA verb on race pages",
            "selector": _selector("race_coaching_cta"),
            "pages": ["/race/*"],
            "conversion_selector": "[data-cta='coaching']",
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "TALK TO A COACH",
                },
                {
                    "id": "variant_a",
                    "name": "apply",
                    "content": "APPLY FOR COACHING",
                },
                {
                    "id": "variant_b",
                    "name": "race_specific",
                    "content": "GET A COACH FOR THIS RACE",
                },
            ],
        },
        {
            "id": "race_coaching_framing",
            "description": "Test coaching value prop in race page CTA",
            "selector": _selector("race_coaching_cta"),
            "pages": ["/race/*"],
            "conversion_selector": "[data-cta='coaching']",
            "variants": [
                {
                    "id": "control",
                    "name": "control",
                    "content": "TALK TO A COACH",
                },
                {
                    "id": "variant_a",
                    "name": "one_on_one",
                    "content": "1:1 COACHING — LIMITED SPOTS",
                },
                {
                    "id": "variant_b",
                    "name": "direct",
                    "content": "GET A COACH",
                },
            ],
        },
    ],
}


def get_next_template(category: str, used_ids: list[str] | None = None) -> dict | None:
    """Return the next untested template in a category.

    Args:
        category: One of the TEMPLATES keys (e.g. "homepage_about", "race_pages").
        used_ids: List of template IDs already tested.

    Returns:
        The next template dict, or None if all templates in the category
        have been used.
    """
    if category not in TEMPLATES:
        raise ValueError(f"Unknown category: {category!r}. "
                         f"Valid: {', '.join(sorted(TEMPLATES.keys()))}")

    used = set(used_ids or [])
    for template in TEMPLATES[category]:
        if template["id"] not in used:
            return template
    return None


def list_categories() -> list[str]:
    """Return sorted list of template categories."""
    return sorted(TEMPLATES.keys())


def count_templates() -> dict[str, int]:
    """Return count of templates per category."""
    return {cat: len(templates) for cat, templates in sorted(TEMPLATES.items())}


def validate_selectors() -> list[str]:
    """Validate that all template selectors reference known data-ab attributes.

    Returns:
        List of error strings. Empty list means all selectors are valid.
    """
    errors: list[str] = []
    valid_attrs = set(VALID_SELECTORS.keys())

    for category, templates in TEMPLATES.items():
        for template in templates:
            tid = template.get("id", "<missing>")
            sel = template.get("selector", "")

            # Extract data-ab value from selector like "[data-ab='foo']"
            if "data-ab='" in sel:
                start = sel.index("data-ab='") + len("data-ab='")
                end = sel.index("'", start)
                attr = sel[start:end]
                if attr not in valid_attrs:
                    errors.append(
                        f"{category}/{tid}: selector references unknown "
                        f"data-ab='{attr}'. Valid: {sorted(valid_attrs)}"
                    )
            else:
                errors.append(
                    f"{category}/{tid}: selector '{sel}' does not use "
                    f"data-ab attribute format"
                )

    return errors


if __name__ == "__main__":
    # Validate first
    errors = validate_selectors()
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        print()

    counts = count_templates()
    total = sum(counts.values())
    print(f"Experiment templates: {total} across {len(counts)} categories\n")
    for cat, n in counts.items():
        print(f"  {cat}: {n} templates")
        for t in TEMPLATES[cat]:
            print(f"    - {t['id']}: {t['description']}")
    print()

    print("Valid data-ab selectors:")
    for attr, pages in sorted(VALID_SELECTORS.items()):
        print(f"  {attr}: {pages}")
