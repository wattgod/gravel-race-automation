"""Tire reviews must come from real riders (scoring-and-veracity SKILL §3).

In Feb 2026 a seeding script wrote 50 "realistic" reviews straight into
data/tires/*.json with approved=true. They rendered as community reviews on
the /tire/ pages and fed the Product aggregateRating that Google reads. They
were removed in Nov 2026. These tests keep them from coming back.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIRE_DIR = ROOT / "data" / "tires"


def _reviews():
    for path in sorted(TIRE_DIR.glob("*.json")):
        tire = json.loads(path.read_text(encoding="utf-8"))
        for review in tire.get("community_reviews", []):
            yield tire["id"], review


def test_seed_script_is_gone():
    assert not (ROOT / "scripts" / "seed_tire_reviews.py").exists(), (
        "seed_tire_reviews.py writes invented reviews; never restore it"
    )


def test_no_seeded_reviews_in_tire_data():
    seeded = [(tid, r["review_id"]) for tid, r in _reviews()
              if str(r.get("review_id", "")).startswith("seed-")]
    assert not seeded, f"seeded reviews found: {seeded}"


def test_published_reviews_come_from_the_intake_worker():
    """The tire-review-intake worker mints ids as tr-{tire_id}-...; anything
    else was written by hand or by a script and has no rider behind it."""
    bad = [(tid, r.get("review_id")) for tid, r in _reviews()
           if r.get("approved") and not str(r.get("review_id", "")).startswith(f"tr-{tid}-")]
    assert not bad, f"approved reviews without a worker id: {bad}"


def test_unpublished_reviews_say_why():
    """An unpublished review stays in the file (so the KV sync doesn't re-add
    it) and records the reason."""
    silent = [(tid, r["review_id"]) for tid, r in _reviews()
              if r.get("approved") is False and not r.get("rejected_reason")]
    assert not silent, f"unpublished reviews with no rejected_reason: {silent}"
