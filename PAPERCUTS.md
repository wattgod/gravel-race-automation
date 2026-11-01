# Papercuts

Small frictions hit while working. Not bugs, not accomplishments — where this repo needs sanding down.

- 2026-10-28 [claude-opus-5-5] running the full pytest suite on fresh main -> tests/test_article_conversion.py and tests/test_substack_import.py import bs4, which isn't in the local Python, so collection stops; add beautifulsoup4 to requirements or importorskip
- 2026-11-01 [claude-opus-5-5] Searching generators with grep --include=*.py -> zsh expands the unquoted glob and errors 'no matches found'; must quote --include='*.py'.
- 2026-11-01 [claude-opus-5-5] Orienting in the repo -> CLAUDE.md still says 757 race profiles while race-data has 384; stale headline count misleads agents about scale.
- 2026-11-01 [claude-opus-5-5] Agent bash calls reset cwd to gg-deploy-main between calls -> every generator/test must be prefixed with cd into the worktree or it writes into another session's tree.
- 2026-11-01 [claude-opus-5-5] Running preflight_quality.py on a data-only branch -> it fails on 'Questionnaire parity' (live Elementor page vs repo, 76 fields) which no branch can fix; a live-site check inside a pre-PR gate makes every PR look red.
- 2026-11-01 [claude-opus-5-5] Regenerating web artifacts -> generate_llms_txt.py exits on 'SSH_HOST/SSH_USER not set (source .env)' just to build a text file, so llms-full.txt can't be refreshed without deploy secrets.
- 2026-11-01 [claude-opus-5-5] Editing race-data JSON -> 29 profiles don't round-trip through json.dumps (mixed \u escapes), so any scripted edit either churns the whole file or needs a hand-rolled text insert; one canonical writer would fix it.
