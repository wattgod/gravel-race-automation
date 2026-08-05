"""The quiz page embeds every race as a JS object literal.

One malformed number invalidates the ENTIRE array, so the script block throws a
SyntaxError and the quiz silently does nothing. That shipped: `elevation_ft` of
"4,500-9,116" was interpolated raw as `"ef":4,500-9,116`, live on
gravelgodcycling.com/race/quiz/, with the race-finder sequence showing a single
enrollment for its whole lifetime.

The array is valid JSON when every numeric field is numeric, so parsing it is a
sufficient guard.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))


def _load_index():
    idx = ROOT / "web" / "race-index.json"
    data = json.loads(idx.read_text())
    return data if isinstance(data, list) else data.get("races", data)


class TestNumberCoercion:
    @pytest.mark.parametrize("raw,expected", [
        (4890, 4890),
        ("4,500-9,116", 4500),   # range with separators — the bug
        ("1,200", 1200),
        ("12.5", 12.5),
        ("", 0),
        (None, 0),
        ("TBD", 0),
        (True, 0),              # bool is an int subclass; must not become 1
    ])
    def test_coerces_to_js_safe_number(self, raw, expected):
        from generate_quiz import _num
        assert _num(raw) == expected

    def test_respects_default(self):
        from generate_quiz import _num
        assert _num("nope", 4) == 4


class TestRaceArrayIsParseable:
    def test_every_emitted_race_is_valid_json(self):
        from generate_quiz import build_quiz_page

        html = build_quiz_page(_load_index())
        m = re.search(r"var RACES=(\[.*?\]);", html, re.S)
        assert m, "RACES array not found in generated quiz page"
        races = json.loads(m.group(1))  # raises if any field is malformed
        assert races, "RACES array is empty"

        numeric = ("t", "sc", "dm", "ef", "mn", "df", "tc")
        for r in races:
            for key in numeric:
                assert isinstance(r.get(key), (int, float)), (
                    f"{r.get('s')}: {key}={r.get(key)!r} is not numeric — "
                    "this invalidates the whole array"
                )
