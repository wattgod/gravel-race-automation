---
name: brand-tokens-and-ci
description: Load when touching brand colors/fonts/tokens, CI workflows, or Python version/dependency issues.
---

# Brand Tokens and CI

Written for zero-context engineers and agents picking this repo up cold.

## 1. The token chain — read this before touching any color or CSS var

Three files, three roles, verified by reading them directly:

1. `../gravel-god-brand/tokens/tokens.json` — the actual source of truth. Hand-edit
   this one.
2. `../gravel-god-brand/tokens/generate_css.py` — reads `tokens.json`, writes
   `tokens.css` with the header `/* Auto-generated from tokens.json — do not edit
   by hand */`. Run `python3 tokens/generate_css.py` after any `tokens.json` change.
3. `../gravel-god-brand/tokens/tokens.css` — generated output. This repo's
   CLAUDE.md calls this the "brand tokens source of truth," which is correct
   from THIS repo's vantage point (it's the only brand file this repo reads at
   preflight time) but wrong upstream: `tokens.css` is a build artifact of
   `tokens.json`. Edit `tokens.json`, regenerate, never hand-edit `tokens.css`
   — a hand-edit survives only until the next regeneration, which silently
   reverts it (this has happened once already, per session memory: a WCAG
   pass hand-edited `tokens.css` without touching `tokens.json`, and a later
   regen wiped the fix).

**The trap that already fired once**: `wordpress/brand_tokens.py`'s
`get_tokens_css()` does NOT read `tokens.css` at runtime. It contains its own
hardcoded triple-quoted copy of the `:root` block, consumed by 22 generator
files (`generate_homepage.py`, `generate_calendar.py`, `generate_tire_guide.py`,
etc.). War story (Jul 2026): that copy silently drifted from `tokens.json`
on border gold/secondary, and carried two typography tokens
(`--gg-font-weight-black`, `--gg-letter-spacing-display`) upstream never
knew about — for months, because the old preflight parity check only
compared `--gg-color-*` names. Root cause: the Jul 4 WCAG restore updated
tokens.json's colors block but missed its border block.

Fixed and guarded Jul 2026: upstream border/typography tokens corrected
(brand repo commit "tokens: finish WCAG restore"), and
`scripts/preflight_quality.py::check_brand_tokens_py_parity()` now compares
EVERY `--gg-*` declaration in `get_tokens_css()` against `tokens.css` — a
future drift fails preflight instead of shipping. If that check fires:
decide which side is right (usually tokens.json), fix there, regenerate,
and only then touch brand_tokens.py. Never hardcode hex anywhere else in
the codebase — the brand_tokens.py block is the one sanctioned, now-guarded
exception, not a pattern to copy.

## 2. CI red-since-April incident — the wallpaper trap

`.github/workflows/test.yml` failed on every "Run Tests" run from roughly
April 2026 through early July 2026: the workflow hand-installed 5 packages
while the test suite imports Pillow/dotenv/fastmcp/ddgs/beautifulsoup4/etc.,
so pytest died at collection — 0 tests ever ran. Nobody noticed for months
because the failure emails became noise.

Fixed Jul 2026: `test.yml` now runs `pip install -r requirements.txt` (step
"Install dependencies", line ~25) — verified current. `requirements.txt` at
repo root carries the full dependency set including `fastmcp`,
`python-frontmatter`, `beautifulsoup4`.

Rule: a red CI you've learned to ignore is worse than no CI. If a workflow is
red, either fix it now or delete it — never let it become wallpaper.

Note: the push trigger on `test.yml` is scoped to `paths: scripts/**,
tests/**` — changes under `wordpress/`, `mission_control/`, etc. do not
trigger it on push (though `pull_request` has no path filter, so PRs always
run the full suite).

## 3. Python version trap

Three different Python versions are in play, verified directly:
- **CI** (`test.yml`, `actions/setup-python@v5`): pins `python-version: '3.11'`
- **Runtime** (`Dockerfile`, `railway.toml` → `dockerfilePath: Dockerfile`):
  `FROM python:3.12-slim`
- **Local dev** (this machine): `python3 --version` → 3.14.3

War story: nested-quote f-strings and backslashes inside f-string
expressions (e.g. `f'{d['key']}'`) are valid on 3.12+ but a `SyntaxError` on
3.11. They pass locally (3.14) and even pass `ast.parse(feature_version=...)`
checks (tokenizer-level, not caught) — then crash CI. Fixed instances:
`youtube_screenshots` (x2), `draft_race_reply`, `daily_intel` (the last would
have crashed the daily-intel cron in production). Fix swept with:
`uv run --python 3.11 --no-project python -c "compile(...)"` over all `.py`
files.

Rule: write syntax that's valid on 3.11 (the strictest pinned version, and
the one CI gates on), not whatever your local interpreter accepts. Before
trusting a change that touches f-strings or new syntax, compile it under
3.11.

## 4. Fonts

Sometype Mono (data/labels/stats) + Source Serif 4 (editorial prose) — see
CLAUDE.md "Brand & Copy" for the full rule. Font-face pitfalls: CLAUDE.md
Known Pitfalls #8 (missing `@font-face` silently falls back to system fonts)
and #14 (removing a font file requires updating `brand_tokens.py`
`@font-face` blocks, CSS custom property tokens, `<link rel="preload">`
hints, and `FONT_FILES` — `test_ux_overhaul.py::TestFontCleanup` enforces
this).

## When NOT to use this

- Pure content/copy edits with no CSS, color, font, or `.github/workflows/`
  touch — irrelevant.
- Race-data or scoring changes (`race-data/*.json`, tier/prestige logic) —
  see the scoring-focused skill instead.
- Deploy/SSH/SiteGround mechanics with no CI or token involvement — see
  CLAUDE.md "Deploy" section directly.
- One-line hex tweaks inside `tokens.json` itself, when you already know to
  regenerate — you don't need the full trap list, just run
  `python3 tokens/generate_css.py` and move on.
