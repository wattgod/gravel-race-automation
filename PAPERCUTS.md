# Papercuts

Small frictions hit while working. Not bugs, not accomplishments — where this repo needs sanding down.

- 2026-10-28 [claude-opus-5-5] running the full pytest suite on fresh main -> tests/test_article_conversion.py and tests/test_substack_import.py import bs4, which isn't in the local Python, so collection stops; add beautifulsoup4 to requirements or importorskip
