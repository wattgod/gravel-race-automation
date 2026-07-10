"""Guard against defensive trust copy and retired guide hero photos."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

import generate_coaching
import generate_guide_cluster
import generate_homepage


BANNED_COPY_RE = re.compile(
    r"honestly rated|honest review|unbiased|no sponsors|zero sponsors|pay-to-play",
    re.IGNORECASE,
)
CHAPTER_HERO_RE = re.compile(r"ch\d+-hero-.*webp", re.IGNORECASE)


def _race_index() -> list[dict]:
    return json.loads((ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))


def test_generated_homepage_guide_pillar_and_coaching_avoid_defensive_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(generate_homepage, "fetch_substack_posts", lambda: [])
    homepage_html = generate_homepage.generate_homepage(_race_index())

    guide_dir = tmp_path / "guide"
    generate_guide_cluster.generate_cluster(output_dir=guide_dir)
    guide_pillar_html = (guide_dir / "index.html").read_text(encoding="utf-8")

    coaching_html = generate_coaching.generate_coaching_page()

    for label, html in {
        "homepage": homepage_html,
        "guide pillar": guide_pillar_html,
        "coaching": coaching_html,
    }.items():
        assert not BANNED_COPY_RE.search(html), f"{label} contains banned copy"


def test_generated_guide_chapters_do_not_reference_retired_hero_photos(tmp_path):
    guide_dir = tmp_path / "guide"
    generate_guide_cluster.generate_cluster(output_dir=guide_dir)

    for chapter_dir in guide_dir.iterdir():
        chapter_file = chapter_dir / "index.html"
        if chapter_dir.name == "race-prep-configurator" or not chapter_file.exists():
            continue
        html = chapter_file.read_text(encoding="utf-8")
        assert not CHAPTER_HERO_RE.search(html), f"{chapter_dir.name} references retired hero photo"
