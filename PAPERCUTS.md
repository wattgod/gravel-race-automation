# Papercuts

Small frictions hit while working. Not bugs, not accomplishments — where this repo needs sanding down.

- 2026-10-28 [claude-opus-5-5] running the full pytest suite on fresh main -> tests/test_article_conversion.py and tests/test_substack_import.py import bs4, which isn't in the local Python, so collection stops; add beautifulsoup4 to requirements or importorskip
- 2026-11-01 [claude-opus-5-5] homepage cut -> race-index.json takes discipline only from gravel_god_rating, so 49 profiles whose vitals.discipline is road/bikepacking/mtb are indexed as gravel (Nove Colli showed in 'top rated gravel'); fix in scripts/generate_index.py:328 by falling back to vitals.discipline
- 2026-11-01 [claude-opus-5-5] full-page Playwright screenshots of the homepage show lazy-loaded images as blank boxes -> set the viewport to the full scroll height before the screenshot so loading=lazy images actually load
- 2026-11-01 [claude-opus-5-5] running the full suite locally -> pytest -n auto silently does nothing (no xdist) and test_article_conversion/test_substack_import fail collection without bs4; document the local test deps
