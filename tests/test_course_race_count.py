"""Course copy names the live race count, never a stale literal (sweep GG-03)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))

import generate_courses as gc  # noqa: E402
from race_facts import catalog_race_count  # noqa: E402

COURSES = ROOT / "data" / "courses"


def test_no_hard_coded_race_count_in_course_data():
    hits = []
    for f in COURSES.rglob("*.json"):
        for m in re.finditer(r"\b\d{3}(?:[- ]race| races| gravel races| race profiles| profiles| in the database)", f.read_text()):
            hits.append(f"{f.relative_to(ROOT)}: {m.group(0)}")
    assert not hits, hits


def test_loader_fills_the_live_count():
    course = gc.load_course(COURSES / "dirt-craft")
    outcome = [o for o in course["what_youll_learn"] if "Race Setup Card" in o][0]
    assert f"any of {catalog_race_count()} gravel races" in outcome
    blob = repr(course)
    assert gc.RACE_COUNT_TOKEN not in blob


def test_course_pages_speak_as_matti():
    src = (ROOT / "wordpress" / "generate_courses.py").read_text()
    assert "your coach" not in src
    assert "we\\\\u2019ll sort it out" not in src
