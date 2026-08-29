"""Regression tests for the pinned petergyang/no-ai-slop copy guard."""

import copy
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))

from generate_courses import (  # noqa: E402
    NO_AI_SLOP_GUARD,
    build_landing_page,
    load_course,
    validate_course_copy,
    validate_rendered_course_copy,
)
from slop_rules import (  # noqa: E402
    RULESET_COMMIT,
    RULESET_NAME,
    RULESET_URL,
    check_text,
)


class TestPinnedAuthority:
    def test_upstream_identity_is_pinned(self):
        assert RULESET_NAME == "petergyang/no-ai-slop"
        assert RULESET_URL == "https://github.com/petergyang/no-ai-slop"
        assert RULESET_COMMIT == "d30eddb9e04562234f2070b5ee63ca4649d9a05e"
        assert NO_AI_SLOP_GUARD == f"{RULESET_NAME}@{RULESET_COMMIT}"

    def test_vendored_rules_and_license_exist(self):
        root = PROJECT_ROOT / ".claude" / "skills" / "no-ai-slop"
        assert (root / "SKILL.md").exists()
        assert (root / "eval.md").exists()
        assert "Copyright (c) 2026 Peter Yang" in (root / "LICENSE").read_text()


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("Let us delve into the details.", "delve"),
        ("Here is the thing. The calendar changed.", "throat-clearing opener"),
        ("What most people get wrong is recovery.", "faux-insight setup"),
        ("The best part: it learns.", "colon reveal"),
        ("The launch shipped Tuesday, highlighting our commitment.", "superficial analysis"),
        ("Experts agree this works.", "weasel attribution"),
        ("This is not a calendar. It is a coaching system.", "binary contrast"),
        ("Not an AI, not a dashboard, not a coach who reads you like a spreadsheet.", "negative listing"),
    ],
)
def test_named_upstream_patterns_are_detected(text, rule):
    assert rule in {finding["phrase"] for finding in check_text(text)}


def test_word_boundaries_do_not_flag_elevation():
    assert check_text("The route has 2,000 meters of elevation gain.") == []


def test_short_copy_rejects_em_dash_rhythm_crutch():
    findings = check_text("The plan changed — because life changed.")
    assert "em-dash overuse" in {finding["phrase"] for finding in findings}


class TestCoachingStartCopy:
    @pytest.fixture
    def course(self):
        return load_course(PROJECT_ROOT / "data" / "courses" / "coaching-start")

    def test_course_opts_into_exact_guard(self, course):
        assert course["copy_guard"] == NO_AI_SLOP_GUARD

    def test_course_passes_deterministic_guard(self, course):
        validate_course_copy(course)

    def test_generation_fails_closed_on_slop(self, course):
        broken = copy.deepcopy(course)
        broken["description"] = "Here is the thing. Let us delve into onboarding."
        with pytest.raises(ValueError, match="failed petergyang/no-ai-slop"):
            validate_course_copy(broken)

    def test_rendered_page_passes_guard(self, course):
        html = build_landing_page(course, [course])
        validate_rendered_course_copy(course, "landing page", html)

    def test_rendered_page_fails_closed_on_template_slop(self, course):
        with pytest.raises(ValueError, match="failed rendered petergyang/no-ai-slop"):
            validate_rendered_course_copy(
                course,
                "broken page",
                "<main>Here is the thing. Let us delve into onboarding.</main>",
            )

    def test_unknown_guard_version_fails_closed(self, course):
        broken = copy.deepcopy(course)
        broken["copy_guard"] = "petergyang/no-ai-slop@unreviewed"
        with pytest.raises(ValueError, match="Unsupported copy_guard"):
            validate_course_copy(broken)
