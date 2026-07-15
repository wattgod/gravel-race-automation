"""Coverage audit tests for race-page video still relevance."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_photo_relevance_coverage import parse_score, scan_photo_coverage


def _write_race(root: Path, slug: str, photos: list[dict]) -> None:
    (root / f"{slug}.json").write_text(json.dumps({"photos": photos}))


def test_parse_score_is_null_and_string_safe():
    assert parse_score(None) is None
    assert parse_score("") is None
    assert parse_score("not-scored") is None
    assert parse_score("4") == 4


def test_coverage_reports_unscored_and_all_filtered_races(tmp_path):
    _write_race(tmp_path, "passes", [
        {"type": "video-1", "ai_relevance": "4"},
        {"type": "video-2", "ai_relevance": 5},
        {"type": "street-1"},
    ])
    _write_race(tmp_path, "mixed", [
        {"type": "video-1", "ai_relevance": None},
        {"type": "video-2", "ai_relevance": 2},
    ])
    _write_race(tmp_path, "trusted-only", [{"type": "landscape"}])

    report = scan_photo_coverage(tmp_path)

    assert report["race_files"] == 3
    assert report["races_with_video_stills"] == 2
    assert report["races_fully_scored"] == 1
    assert report["races_partially_scored"] == 1
    assert report["video_stills"] == 4
    assert report["video_stills_scored"] == 3
    assert report["video_stills_passing"] == 2
    assert report["races_losing_all_video_stills"] == ["mixed"]
