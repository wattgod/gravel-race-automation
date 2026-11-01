# Papercuts

Small frictions hit while working. Not bugs, not accomplishments — where this repo needs sanding down.

- 2026-10-28 [claude-opus-5-5] running the full pytest suite on fresh main -> tests/test_article_conversion.py and tests/test_substack_import.py import bs4, which isn't in the local Python, so collection stops; add beautifulsoup4 to requirements or importorskip
- 2026-11-01 [claude-opus-5-5] Reframing guide art -> the <img height=640> attribute silently overrode the CSS aspect-ratio crop, so phones showed a thin sliver of the handbook art; fixed with height:auto, worth a test.
- 2026-11-01 [claude-opus-5-5] Replacing /guide/media art -> files are served with a 1-year cache and no content hash, so same-name swaps would stay stale; had to rename to gg-art-v67-*.
