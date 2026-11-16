"""/plan/manage on gravelgodcycling.com sends riders to the plan manage page.

The page itself is served by the training-plan pipeline on Railway. It reads
its #t= token from the URL fragment (kept across a redirect) and posts to
relative /api/race-plan/* paths, so only a redirect works here.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import push_wordpress as pw  # noqa: E402

TARGET = "https://athlete-custom-training-plan-pipeline-production.up.railway.app/plan/manage"
RULE = re.compile(r"^RewriteRule (\S+) (\S+) \[([^\]]+)\]$", re.M)


def _rule_for(path):
    for pattern, target, flags in RULE.findall(pw.REDIRECT_BLOCK):
        if re.search(pattern, path):
            return target, flags
    return None


def test_both_spellings_redirect_to_the_manage_page():
    for path in ("plan/manage", "plan/manage/"):
        assert _rule_for(path) == (TARGET, "R=302,L"), path


def test_nothing_else_under_plan_is_caught():
    for path in ("plan/manage/extra", "plan/", "plan/managed", "xplan/manage"):
        hit = _rule_for(path)
        assert hit is None or hit[0] != TARGET, path


def test_rule_runs_before_the_fallbacks():
    block = pw.REDIRECT_BLOCK
    assert block.index("^plan/manage/?$") < block.index("# Self-healing for stale blog URLs")
