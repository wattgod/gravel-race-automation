"""Published Gravel God TrainingPeaks link synchronization."""

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sync_tp_race_plan_links import build_links


def test_build_links_filters_and_sorts_published_gravel_plans():
    rows = [
        {
            "planId": 3,
            "race_slug": "race-a",
            "discipline": "gravel",
            "status": "published",
            "marketplace_url": "https://tp.example/3",
            "tier": "Save My Race",
            "length_wk": 6,
            "price": 69,
        },
        {
            "planId": 2,
            "race_slug": "race-a",
            "discipline": "gravel",
            "status": "published",
            "marketplace_url": "https://tp.example/2",
            "tier": "Finisher",
            "length_wk": 8,
            "price": 79,
        },
        {
            "planId": 1,
            "race_slug": "race-a",
            "discipline": "gravel",
            "status": "published",
            "marketplace_url": "https://tp.example/1",
            "tier": "Finisher",
            "length_wk": 12,
            "price": 99,
        },
        {
            "planId": 4,
            "race_slug": "race-a",
            "discipline": "road",
            "status": "published",
            "marketplace_url": "https://tp.example/4",
            "tier": "Finisher",
            "length_wk": 12,
            "price": 99,
        },
        {
            "planId": 5,
            "race_slug": "race-a",
            "discipline": "gravel",
            "status": "private-ready",
            "marketplace_url": "https://tp.example/5",
            "tier": "Finisher",
            "length_wk": 12,
            "price": 99,
        },
    ]

    links = build_links(rows)

    assert list(links) == ["race-a"]
    assert [plan["planId"] for plan in links["race-a"]] == [1, 2, 3]


def test_oregon_trail_publishes_the_complete_full_7_ladder():
    links = json.loads(
        (Path(__file__).resolve().parent.parent / "data" / "tp-race-plan-links.json")
        .read_text(encoding="utf-8")
    )
    ladder = links["oregon-trail-gravel"]

    assert [plan["planId"] for plan in ladder] == [
        669620, 669621, 669622, 669623, 669624, 669625, 669626
    ]
    assert all(plan["url"].endswith(f"tp-{plan['planId']}/p") for plan in ladder)
