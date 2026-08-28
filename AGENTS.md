# AGENTS.md — entry point for any coding agent

## AI writing as Matti

Before drafting, rewriting, or approving copy presented as Matti Rowe or one of
his brands, read `docs/AI_WRITING_POLICY.md`. Its source-retrieval,
provenance, privacy, and anti-slop requirements are binding.

## Baseline editorial and citation rules

These rules apply to every agent and every public-facing race, rating, article,
email, and product surface:

- Write the finished judgment, never the research process. Do not say a source's
  "assessment rings true," "according to our research," "sources say," or name
  the person/site that supplied an ordinary fact unless the attribution itself
  materially matters.
- Do not use the brand as a synthetic narrator (for example, "Gravel God
  scores..."). State the judgment directly in the brand's established voice.
- Lead every Course and Editorial/Experience rating with one sharp, standalone
  verdict sentence before discussing individual criteria.
- Put a numbered inline marker such as `[3]` on every factual or quoted claim.
  Every marker must resolve to that page's numbered source list; preserve stable
  source order, never invent a source number, and never use attribution prose as
  a substitute for the marker.
- Preserve a real person's exact words inside quotation marks and cite the quote.
  Clean up only the surrounding prose; do not flatten actual human language into
  house style.
- Cut AI filler: importance puffery, vague scene-setting, fake quotations,
  repetitive conclusions, canned transitions, generic superlatives, and words
  such as "delve," "testament," or "game-changing" when a concrete statement
  will do.
- Citation correctness and voice quality are separate gates. A sourced sentence
  can still be bad copy, and clean copy can still be unsupported. Verify both.

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
