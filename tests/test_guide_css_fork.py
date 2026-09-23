r"""Divergence guard for the forked training-guide stylesheet.

pipeline/step_07_guide.py::_css is a FORK of the canonical stylesheet in a
different repository:

    repo:   athlete-custom-training-plan-pipeline
    path:   athletes/scripts/training_guide_builder.py
    symbol: _css(brand="gravel")
    commit: c4d6a595c2ea9b2243c08c8ee22a98682dac7178 (origin/main)
    blob:   87b93fb323c3be59397c7b46d56dfcb0c7001d34

At that commit the two copies share 400 identical lines. The `.gg-module`
block and its four variants are byte-identical, and each copy contains
exactly 7 lines carrying border-left declarations (8 declarations, because
.gg-blackpill puts two on one line).

These tests are SELF-CONTAINED: they never import from, or shell out to, the
upstream repository. The upstream text is pinned here as a snapshot taken at
the commit above. That is the point — CI must be able to catch a one-sided
edit to this repo's copy without the other repo being checked out.

WHY THIS MATTERS
    The upstream copy is the canonical brand definition. Editing this fork
    alone silently diverges the two guide stylesheets, and the drift is
    invisible until two customers get visually different deliverables.
    Shared changes go upstream FIRST, then get ported here.

HOW TO REFRESH THE SNAPSHOT (deliberately, never to make a red test green)
    1. Land the change upstream first, in training_guide_builder.py::_css.
    2. Port the identical change into pipeline/step_07_guide.py::_css.
    3. Re-read upstream READ-ONLY (that repo is often mid-merge; never edit
       it, and never trust its working copy) and confirm the block matches:

           git -C ../athlete-custom-training-plan-pipeline show origin/main:athletes/scripts/training_guide_builder.py

    4. Regenerate the constants by running, from the repo root:

           python3 tests/test_guide_css_fork.py

       That prints a ready-to-paste SHARED_MODULE_BLOCK and
       SHARED_MODULE_BLOCK_SHA256 built from the CURRENT _css() output.
       It only prints; it never edits this file for you.
    5. Update SHARED_MODULE_BLOCK, SHARED_MODULE_BLOCK_SHA256, and the
       UPSTREAM_* provenance constants in the SAME commit, and say in the
       commit message which upstream commit you verified against.

    If you are updating the hash without having touched upstream, stop. That
    is the divergence this file exists to prevent.
"""

import hashlib
import re
import sys
from pathlib import Path

import pytest

# Repo root on sys.path so this file also runs standalone as the refresh
# helper (python3 tests/test_guide_css_fork.py), not just under pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.step_07_guide import _css


# ── Upstream provenance (see module docstring) ────────────────

UPSTREAM_REPO = "athlete-custom-training-plan-pipeline"
UPSTREAM_PATH = "athletes/scripts/training_guide_builder.py"
UPSTREAM_COMMIT = "c4d6a595c2ea9b2243c08c8ee22a98682dac7178"
UPSTREAM_BLOB = "87b93fb323c3be59397c7b46d56dfcb0c7001d34"

# Verified byte-identical against upstream at UPSTREAM_COMMIT.
SHARED_MODULE_BLOCK = """/* === Modules / Callouts === */
.gg-module {
  border: 3px solid var(--gg-color-dark-brown);
  border-left-width: 6px;
  padding: 16px 20px;
  margin: 1.5rem 0;
  background: var(--gg-color-warm-paper);
}

.gg-alert { border-left-color: var(--gg-color-gold); }
.gg-tactical { border-left-color: var(--gg-color-teal); }
.gg-info { border-left-color: var(--gg-color-secondary-brown); }
.gg-blackpill { background: var(--gg-color-sand); border-left-width: 8px; border-left-color: var(--gg-color-dark-brown); }
"""

SHARED_MODULE_BLOCK_SHA256 = (
    "91222b2284f908e0049ae7d27d7c66faba2c068fb104b1af62f5bc73cb2086f7"
)

# Both copies carry exactly this many border-left-bearing lines in _css.
SHARED_BORDER_LEFT_LINES = 7
# .gg-blackpill declares two on one line, hence 8 declarations across 7 lines.
SHARED_BORDER_LEFT_DECLARATIONS = 8

_BORDER_LEFT_DECL = re.compile(r"border-left(?:-[a-z]+)?\s*:")

_REFRESH_HINT = (
    "This copy has diverged from upstream "
    f"{UPSTREAM_REPO}:{UPSTREAM_PATH}::_css. Make shared changes UPSTREAM "
    "FIRST, then port them here. See the docstring at the top of "
    "tests/test_guide_css_fork.py for how to refresh the snapshot."
)


@pytest.fixture(scope="module")
def css():
    return _css()


class TestSnapshotIntegrity:
    def test_snapshot_constant_matches_its_recorded_hash(self):
        """The checked-in snapshot must match its checked-in hash.

        Guards against someone silently editing SHARED_MODULE_BLOCK to make a
        failing test pass. Refreshing the snapshot means updating both.
        """
        actual = hashlib.sha256(SHARED_MODULE_BLOCK.encode()).hexdigest()
        assert actual == SHARED_MODULE_BLOCK_SHA256, (
            "SHARED_MODULE_BLOCK was edited without updating "
            f"SHARED_MODULE_BLOCK_SHA256 (now {actual}). " + _REFRESH_HINT
        )


class TestForkHasNotDiverged:
    def test_shared_module_block_is_present_verbatim(self, css):
        """The .gg-module block must appear byte-for-byte in this fork's CSS."""
        if SHARED_MODULE_BLOCK in css:
            return

        # Produce a readable diff instead of a bare "not in" failure.
        import difflib

        start = css.find("/* === Modules / Callouts === */")
        if start == -1:
            pytest.fail(
                "The '/* === Modules / Callouts === */' section is gone from "
                "_css() entirely. " + _REFRESH_HINT
            )
        actual = css[start:start + len(SHARED_MODULE_BLOCK) + 200]
        diff = "\n".join(
            difflib.unified_diff(
                SHARED_MODULE_BLOCK.splitlines(),
                actual.splitlines(),
                fromfile="snapshot (upstream)",
                tofile="pipeline/step_07_guide.py::_css",
                lineterm="",
            )
        )
        pytest.fail(f"{_REFRESH_HINT}\n\n{diff}")

    def test_shared_module_block_hashes_to_upstream_value(self, css):
        """Hash the block as it actually appears in _css() output."""
        start = css.find("/* === Modules / Callouts === */")
        assert start != -1, "Modules/Callouts section missing. " + _REFRESH_HINT
        end = css.index("\n", css.index(".gg-blackpill {", start)) + 1
        actual = hashlib.sha256(css[start:end].encode()).hexdigest()
        assert actual == SHARED_MODULE_BLOCK_SHA256, (
            f"Shared block hashes to {actual}, expected "
            f"{SHARED_MODULE_BLOCK_SHA256}. " + _REFRESH_HINT
        )

    def test_border_left_count_matches_upstream(self, css):
        """Neither copy may grow a border-left the other does not have."""
        lines = [ln for ln in css.splitlines() if "border-left" in ln]
        decls = len(_BORDER_LEFT_DECL.findall(css))
        assert len(lines) == SHARED_BORDER_LEFT_LINES, (
            f"border-left lines went {SHARED_BORDER_LEFT_LINES} -> "
            f"{len(lines)}: {lines}. " + _REFRESH_HINT
        )
        assert decls == SHARED_BORDER_LEFT_DECLARATIONS, (
            f"border-left declarations went {SHARED_BORDER_LEFT_DECLARATIONS} "
            f"-> {decls}. " + _REFRESH_HINT
        )


class TestKnownIntentionalDivergences:
    """Divergences verified at UPSTREAM_COMMIT that are deliberate.

    Documented as tests so that if the fork is ever reconciled, these fail
    and force the docstring to be corrected rather than left lying.
    """

    def test_this_copy_is_gravel_only(self):
        """Upstream takes brand='gravel'|'road'; this copy takes no argument."""
        import inspect

        assert list(inspect.signature(_css).parameters) == []

    def test_print_styles_are_delegated_not_inlined(self, css):
        """Upstream inlines @media print; this copy defers to pipeline/print.css."""
        assert "pipeline/print.css" in css
        assert "@page" not in css

    def test_gravel_palette_matches_upstream(self, css):
        """No colour drift: these three were verified identical upstream.

        Listed explicitly because they have been mistakenly reported as
        divergent. They are not. Do not "unify" them.
        """
        for var, value in (
            ("--gg-color-gold", "#B7950B"),
            ("--gg-color-teal", "#1A8A82"),
            ("--gg-color-secondary-brown", "#8c7568"),
        ):
            assert f"{var}: {value};" in css, f"{var} drifted from {value}"


if __name__ == "__main__":
    # Refresh helper — see "HOW TO REFRESH THE SNAPSHOT" above.
    # Prints the constants for the CURRENT _css() output. Paste them in only
    # after the same change has landed upstream.
    _out = _css()
    _s = _out.index("/* === Modules / Callouts === */")
    _e = _out.index("\n", _out.index(".gg-blackpill {", _s)) + 1
    _block = _out[_s:_e]
    print("SHARED_MODULE_BLOCK = \"\"\"" + _block + "\"\"\"")
    print()
    print("SHARED_MODULE_BLOCK_SHA256 = (")
    print('    "' + hashlib.sha256(_block.encode()).hexdigest() + '"')
    print(")")
    print()
    print("# border-left lines:",
          len([l for l in _out.splitlines() if "border-left" in l]),
          "| declarations:", len(_BORDER_LEFT_DECL.findall(_out)))
