# Gravel God to Endure onboarding

Prepared from current main 2cb53ff77ed398f03c10f141ea786ab25f9a3dfe. Related Endure draft: https://github.com/wattgod/endurelabs/pull/4800.

The existing shared Endure offer keeps its signup destination and analytics fields and adds `source=ggc&intent=training`. These are editable suggestions, never paid access, a confirmed race, consent or an installed plan. Existing purchased-plan and coaching links stay separate.

The standard trial is fourteen days, from Endure `src/lib/billing/trial-policy.ts` at eb14c01b77. Roadie/XC seven-day text is corrected to match that rule. No billing policy, referral bonus, purchase terms or access is changed. No new marketing prose, outcomes or voice claims are introduced. The existing wording and card/conversion/cancellation/eligibility disclosures remain. Numerical correction and URL fields only. Writing-policy sources reviewed: `docs/AI_WRITING_POLICY.md`, writing-graph `self/voice-and-beliefs-profile.md` and pinned `vendor/no-ai-slop/{SKILL.md,eval.md}`. No private correspondence is published.

Checks: `python3 -m pytest tests/test_endure_trial_offer.py tests/test_shared_footer.py -q`. They exercise actual footer generation, source/intent and analytics fields, correct trial length, disclosures and the separate purchase ladder. Cross-repository generated-link/auth contract evidence is recorded in the Endure PR.

This is a draft source change. No live site, catalog, profile, provider account or billing state was changed. Regenerate the affected site output through the existing generator before deployment; do not publish before Endure's entry handling is released and the owner approves the release.

GGC's secondary race-page offer remains the separate, open draft [#535](https://github.com/wattgod/gravel-race-automation/pull/535), not part of main or this footer patch. Its observed `utm_source=gravel-god` remains supported by Endure. This change neither merges nor deploys that race-offer draft.
