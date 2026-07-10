# AGENTS.md — entry point for any coding agent

Binding instructions live in `CLAUDE.md` — read it first; it is written for
all agents, not just Claude. `docs/GRAVEL_GOD_SCORING_SYSTEM.md` is the
scoring bible; `gravel-god-cycling/NORTHSTAR.md` (sibling repo) is the
canonical plan.

## Handover skills

Distilled operating knowledge — incidents, settled decisions, and playbooks
not derivable from the code. Read the one matching your task before starting;
each file says when not to use it.

| Before you… | Read |
|---|---|
| Deploy anything to gravelgodcycling.com / touch WordPress | `.claude/skills/deploy-safely/SKILL.md` |
| Touch scores, rankings, testimonials, trust-bearing claims | `.claude/skills/scoring-and-veracity/SKILL.md` |
| Touch brand tokens, fonts, CI workflows, Python deps | `.claude/skills/brand-tokens-and-ci/SKILL.md` |
| Touch email capture, sequences, Mission Control, replies | `.claude/skills/conversion-and-email/SKILL.md` |
| Add/edit race profiles, run enrichment, regenerate site | `.claude/skills/data-pipeline-ops/SKILL.md` |

## Non-negotiables (full text in CLAUDE.md)

- Never use innerHTML with data-derived values; `_safe_json_for_script()` inside script tags.
- Every generator includes `get_ga4_head_snippet()` and `get_site_header_js()`.
- Every email form POSTs to the worker with a honeypot — no fake success states.
- Never hardcode hex; tokens come from the brand-tokens chain.
- Never fabricate testimonials, quotes, or review counts. Ever.
- `python3 scripts/preflight_quality.py` before any deploy; purge SiteGround cache after.
