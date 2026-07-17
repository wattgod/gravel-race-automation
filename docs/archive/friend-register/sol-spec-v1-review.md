codex
# Verdict: NO-GO before executor dispatch

The spec’s central evidence set is incomplete, its proposed gate does not actually gate, and its promise/device changes conflict with live enrollment behavior and binding instructions.

## Blockers

1. **The “25 GG emails” scope is false and the findings miss three live emails.**

   Live GG contains:

   - Welcome: 12 steps across A/B ([welcome.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/welcome.py:17))
   - Nurture: 4 distinct steps ([nurture.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/nurture.py:9))
   - Race-specific: 3 ([race_specific.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/race_specific.py:13))
   - Post-purchase: 5 ([post_purchase.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/post_purchase.py:13))
   - Win-back: 2 distinct steps ([win_back.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/win_back.py:7))
   - Countdown: 2 ([race_countdown.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/race_countdown.py:15))

   That is **28 distinct scheduled email slots**, or **34 literal variant-step references** if the zero-weight duplicate nurture/win-back B variants are counted.

   `friend_test.py` reports 25 because its regex refuses dictionaries containing braces ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:99)). It silently drops:

   - Race-specific day 4, whose subject contains `{race_name}` ([race_specific.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/race_specific.py:15))
   - GG countdown 16w and 8w, whose subjects contain merge fields ([race_countdown.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/race_countdown.py:23))

   Consequently, the findings’ “25 emails judged” claim ([friend-test-findings.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/friend-test-findings.md:3)) does **not** cover the full live scope. Neither countdown email is judged.

2. **`friend_test.py` is a report generator, not a CI gate.**

   It never evaluates `friend_score >= 4`, never fails on detector failures, and always reaches normal exit after writing the report ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:402)). Judge errors are merely embedded in output ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:305)). The Codex subprocess has no timeout, return-code check, or stderr handling ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:296)). No CI workflow invokes it.

   Brand discovery is also filename-based, not registry/`brand`-key based ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:123)); the mixed-brand `race_countdown.py` file breaks that assumption. A Roadie run skips that file entirely.

3. **The proposed welcome-only promise is not true under actual enrollment behavior.**

   The promise currently appears in six places, not just welcome:

   - GG welcome ([welcome_value.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/welcome_value.html:28))
   - GG anti-pitch and repitch ([anti_pitch.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/anti_pitch.html:22), [repitch.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/repitch.html:17))
   - Sober welcome, pitch, and repitch ([sober_welcome.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/sober_welcome.html:16), [sober_pitch.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/sober_pitch.html:16), [sober_repitch.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/sober_repitch.html:16))

   More importantly, prep-kit and quiz leads enroll in their source sequence **and welcome** ([webhooks.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/routers/webhooks.py:160), [webhooks.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/routers/webhooks.py:187)). A prep-kit lead can therefore receive two welcome sales emails plus two nurture sales emails. A quiz lead can receive two welcome sales emails plus the race-specific anti-pitch.

   Thus the proposed welcome promise—“I’ll pitch you once … then drop it” ([friend-first-sequences.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/specs/friend-first-sequences.md:60))—is false unless overlapping enrollment or suppression changes. It also conflicts with welcome’s explicit pitch and repitch steps ([welcome.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/welcome.py:21)).

   The existing shared template is already non-self-contained: `anti_pitch` promises a follow-up, but race-specific and win-back do not include `repitch` afterward ([race_specific.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/race_specific.py:13), [win_back.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/win_back.py:7)).

4. **The spec requires trigger changes while declaring engine changes out of scope.**

   It says day-17 emails become reply/race-week-triggered and scheduled emails without a valid premise “move … or die” ([friend-first-sequences.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/specs/friend-first-sequences.md:87)), but engine/trigger infrastructure is out of scope ([friend-first-sequences.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/specs/friend-first-sequences.md:138)). Copy alone cannot make a day-17 drip behavior-triggered.

5. **XC cannot safely enroll or send with the listed prerequisites alone.**

   There is no `xcskilabs` sender config ([config.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/config.py:45)) and no XC sequence registry entry ([sequences/__init__.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/__init__.py:10)). Beyond the spec’s list, XC also needs:

   - Sequence files, templates, registry imports, and routing tests
   - Subscriber webhook allowlist update; unknown brands currently become Gravel God ([webhooks.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/routers/webhooks.py:140))
   - XC domain added to UTM matching; only GG/RL domains are recognized ([sequence_engine.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/services/sequence_engine.py:404))
   - Worker CORS origins ([wrangler.toml](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/workers/fueling-lead-intake/wrangler.toml:5))
   - Worker brand label/sender maps ([worker.js](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/workers/fueling-lead-intake/worker.js:121))
   - `friend_test.py` brand choice and discovery support ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:359))
   - The actual purchase integration must emit `brand: xcskilabs`
   - SendGrid brand-field configuration, currently documented but not configured ([wrangler.toml](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/workers/fueling-lead-intake/wrangler.toml:23))

   Unsubscribe needs no brand-specific implementation; it is centrally injected.

## Errors and omissions

- **The two best-score claim is correct.** They are post-purchase day 10 and race-specific day 1, both 4/5 ([friend-test-findings.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/friend-test-findings.md:209), [friend-test-findings.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/friend-test-findings.md:216)).

- **The device override conflicts with the binding skill.** The skill calls the P.S. loops, early exit ramp, final verb CTA, offer block, sample week, and competitive frame mandatory ([email-sequences/SKILL.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/.claude/skills/email-sequences/SKILL.md:61)). The spec says the skill/doc update occurs only after copy approval, so executors receive mutually exclusive instructions during drafting.

- **Almost none of those devices are mechanically enforced.** Existing tests enforce template existence and merge rendering. The only relevant content assertion requires `"two emails"` in `welcome_value` ([test_brand_routing.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/tests/test_brand_routing.py:167)). No test or hook enforces CTA position, P.S. chain, offer block, sample week, or competitive frame. `wordpress/slop_rules.py` is only a generic phrase/structure library, and preflight scans WordPress output—not Mission Control email templates.

  If the new dispositions are approved, update:

   - `.claude/skills/email-sequences/SKILL.md`
   - `docs/email-voice-model.md`
   - `docs/email-conversion-principles.md`
   - `test_pitch_count_promise_in_both_branches`
   - Conditional-personalization template lists/tests if branches change
   - Add sequence-level promise tests across overlapping enrollments

- **The judge is internally conflicted.** It loads the current voice model into every prompt ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:87)), while the spec plans to update that model only after approval. It may judge new copy against devices the spec told executors to kill.

- **The LLM gate is noisy and expensive.** It performs one independent model call per email, resending up to 14,000 characters of reference material each time, with no seed, repeated judging, cache, or variance policy. A hosted CI runner also cannot assume an authenticated local Codex CLI; the Anthropic path requires a key and SDK.

- **The threshold is achievable in principle.** The two 4/5 emails already have zero detector FAILs; WARNs are allowed. The concern is repeatability, not logical impossibility.

## Overreaches and conversion risk

The spec reverses conversion findings that were previously treated as 3/3 council constraints: honest urgency, artifact proof, scannable deliverables, and final verb CTA ([email-conversion-principles.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/email-conversion-principles.md:44)). It provides no sales data showing those devices reduce trust or conversion.

The strongest downside case is straightforward:

- Turning a deliverables block into prose makes price/value harder to scan on mobile.
- Replacing one clear action with “reply yes or hit this link” introduces competing actions and weakens attribution.
- Removing legitimate race-window urgency removes the reason to buy now.
- Requiring a personalized friend-premise for every pitch sidelines anonymous subscribers—the people least likely to reply—before they ever see a direct offer.
- The judge explicitly treats “salesiness” as a potential FAIL ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:206)); optimizing solely for that judge can produce copy that passes by barely selling.

Mitigation should be a GG-only controlled test against the current control, not replacement of both welcome variants and both brands at once. Preserve a direct CTA and compact deliverables treatment in at least one arm, measure completed purchases plus unsubscribe/reply/spam guardrails, then roll to RL only after a real result. Purchase attribution must be repaired first: the existing sequence report derives purchases from `gg_athletes`, while the repo itself says real purchases do not populate that table ([sequence_report.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/sequence_report.py:81), [daily_intel.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/daily_intel.py:279)).

## Final verdict

**No-go.** Do not dispatch executors until the scope is corrected to 28 distinct GG emails, all missing emails are judged, `friend_test.py` becomes a registry-based and genuinely failing gate with a variance policy, promise language is reconciled with parallel enrollment, trigger-dependent rewrites are either brought into scope or removed, the binding skill/doc conflict is resolved before drafting, and XC’s complete routing/UTM/CORS/registry prerequisites are specified. After that, the rewrite should ship as a measured GG control-vs-treatment experiment, not a simultaneous replacement across live brands.
tokens used
171,883
# Verdict: NO-GO before executor dispatch

The spec’s central evidence set is incomplete, its proposed gate does not actually gate, and its promise/device changes conflict with live enrollment behavior and binding instructions.

## Blockers

1. **The “25 GG emails” scope is false and the findings miss three live emails.**

   Live GG contains:

   - Welcome: 12 steps across A/B ([welcome.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/welcome.py:17))
   - Nurture: 4 distinct steps ([nurture.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/nurture.py:9))
   - Race-specific: 3 ([race_specific.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/race_specific.py:13))
   - Post-purchase: 5 ([post_purchase.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/post_purchase.py:13))
   - Win-back: 2 distinct steps ([win_back.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/win_back.py:7))
   - Countdown: 2 ([race_countdown.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/race_countdown.py:15))

   That is **28 distinct scheduled email slots**, or **34 literal variant-step references** if the zero-weight duplicate nurture/win-back B variants are counted.

   `friend_test.py` reports 25 because its regex refuses dictionaries containing braces ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:99)). It silently drops:

   - Race-specific day 4, whose subject contains `{race_name}` ([race_specific.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/race_specific.py:15))
   - GG countdown 16w and 8w, whose subjects contain merge fields ([race_countdown.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/race_countdown.py:23))

   Consequently, the findings’ “25 emails judged” claim ([friend-test-findings.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/friend-test-findings.md:3)) does **not** cover the full live scope. Neither countdown email is judged.

2. **`friend_test.py` is a report generator, not a CI gate.**

   It never evaluates `friend_score >= 4`, never fails on detector failures, and always reaches normal exit after writing the report ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:402)). Judge errors are merely embedded in output ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:305)). The Codex subprocess has no timeout, return-code check, or stderr handling ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:296)). No CI workflow invokes it.

   Brand discovery is also filename-based, not registry/`brand`-key based ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:123)); the mixed-brand `race_countdown.py` file breaks that assumption. A Roadie run skips that file entirely.

3. **The proposed welcome-only promise is not true under actual enrollment behavior.**

   The promise currently appears in six places, not just welcome:

   - GG welcome ([welcome_value.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/welcome_value.html:28))
   - GG anti-pitch and repitch ([anti_pitch.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/anti_pitch.html:22), [repitch.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/repitch.html:17))
   - Sober welcome, pitch, and repitch ([sober_welcome.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/sober_welcome.html:16), [sober_pitch.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/sober_pitch.html:16), [sober_repitch.html](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/templates/emails/sequences/sober_repitch.html:16))

   More importantly, prep-kit and quiz leads enroll in their source sequence **and welcome** ([webhooks.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/routers/webhooks.py:160), [webhooks.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/routers/webhooks.py:187)). A prep-kit lead can therefore receive two welcome sales emails plus two nurture sales emails. A quiz lead can receive two welcome sales emails plus the race-specific anti-pitch.

   Thus the proposed welcome promise—“I’ll pitch you once … then drop it” ([friend-first-sequences.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/specs/friend-first-sequences.md:60))—is false unless overlapping enrollment or suppression changes. It also conflicts with welcome’s explicit pitch and repitch steps ([welcome.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/welcome.py:21)).

   The existing shared template is already non-self-contained: `anti_pitch` promises a follow-up, but race-specific and win-back do not include `repitch` afterward ([race_specific.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/race_specific.py:13), [win_back.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/win_back.py:7)).

4. **The spec requires trigger changes while declaring engine changes out of scope.**

   It says day-17 emails become reply/race-week-triggered and scheduled emails without a valid premise “move … or die” ([friend-first-sequences.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/specs/friend-first-sequences.md:87)), but engine/trigger infrastructure is out of scope ([friend-first-sequences.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/specs/friend-first-sequences.md:138)). Copy alone cannot make a day-17 drip behavior-triggered.

5. **XC cannot safely enroll or send with the listed prerequisites alone.**

   There is no `xcskilabs` sender config ([config.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/config.py:45)) and no XC sequence registry entry ([sequences/__init__.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/sequences/__init__.py:10)). Beyond the spec’s list, XC also needs:

   - Sequence files, templates, registry imports, and routing tests
   - Subscriber webhook allowlist update; unknown brands currently become Gravel God ([webhooks.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/routers/webhooks.py:140))
   - XC domain added to UTM matching; only GG/RL domains are recognized ([sequence_engine.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/services/sequence_engine.py:404))
   - Worker CORS origins ([wrangler.toml](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/workers/fueling-lead-intake/wrangler.toml:5))
   - Worker brand label/sender maps ([worker.js](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/workers/fueling-lead-intake/worker.js:121))
   - `friend_test.py` brand choice and discovery support ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:359))
   - The actual purchase integration must emit `brand: xcskilabs`
   - SendGrid brand-field configuration, currently documented but not configured ([wrangler.toml](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/workers/fueling-lead-intake/wrangler.toml:23))

   Unsubscribe needs no brand-specific implementation; it is centrally injected.

## Errors and omissions

- **The two best-score claim is correct.** They are post-purchase day 10 and race-specific day 1, both 4/5 ([friend-test-findings.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/friend-test-findings.md:209), [friend-test-findings.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/friend-test-findings.md:216)).

- **The device override conflicts with the binding skill.** The skill calls the P.S. loops, early exit ramp, final verb CTA, offer block, sample week, and competitive frame mandatory ([email-sequences/SKILL.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/.claude/skills/email-sequences/SKILL.md:61)). The spec says the skill/doc update occurs only after copy approval, so executors receive mutually exclusive instructions during drafting.

- **Almost none of those devices are mechanically enforced.** Existing tests enforce template existence and merge rendering. The only relevant content assertion requires `"two emails"` in `welcome_value` ([test_brand_routing.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/mission_control/tests/test_brand_routing.py:167)). No test or hook enforces CTA position, P.S. chain, offer block, sample week, or competitive frame. `wordpress/slop_rules.py` is only a generic phrase/structure library, and preflight scans WordPress output—not Mission Control email templates.

  If the new dispositions are approved, update:

   - `.claude/skills/email-sequences/SKILL.md`
   - `docs/email-voice-model.md`
   - `docs/email-conversion-principles.md`
   - `test_pitch_count_promise_in_both_branches`
   - Conditional-personalization template lists/tests if branches change
   - Add sequence-level promise tests across overlapping enrollments

- **The judge is internally conflicted.** It loads the current voice model into every prompt ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:87)), while the spec plans to update that model only after approval. It may judge new copy against devices the spec told executors to kill.

- **The LLM gate is noisy and expensive.** It performs one independent model call per email, resending up to 14,000 characters of reference material each time, with no seed, repeated judging, cache, or variance policy. A hosted CI runner also cannot assume an authenticated local Codex CLI; the Anthropic path requires a key and SDK.

- **The threshold is achievable in principle.** The two 4/5 emails already have zero detector FAILs; WARNs are allowed. The concern is repeatability, not logical impossibility.

## Overreaches and conversion risk

The spec reverses conversion findings that were previously treated as 3/3 council constraints: honest urgency, artifact proof, scannable deliverables, and final verb CTA ([email-conversion-principles.md](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/docs/email-conversion-principles.md:44)). It provides no sales data showing those devices reduce trust or conversion.

The strongest downside case is straightforward:

- Turning a deliverables block into prose makes price/value harder to scan on mobile.
- Replacing one clear action with “reply yes or hit this link” introduces competing actions and weakens attribution.
- Removing legitimate race-window urgency removes the reason to buy now.
- Requiring a personalized friend-premise for every pitch sidelines anonymous subscribers—the people least likely to reply—before they ever see a direct offer.
- The judge explicitly treats “salesiness” as a potential FAIL ([friend_test.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/friend_test.py:206)); optimizing solely for that judge can produce copy that passes by barely selling.

Mitigation should be a GG-only controlled test against the current control, not replacement of both welcome variants and both brands at once. Preserve a direct CTA and compact deliverables treatment in at least one arm, measure completed purchases plus unsubscribe/reply/spam guardrails, then roll to RL only after a real result. Purchase attribution must be repaired first: the existing sequence report derives purchases from `gg_athletes`, while the repo itself says real purchases do not populate that table ([sequence_report.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/sequence_report.py:81), [daily_intel.py](/Users/mattirowe/Documents/GravelGod/gravel-race-automation/scripts/daily_intel.py:279)).

## Final verdict

**No-go.** Do not dispatch executors until the scope is corrected to 28 distinct GG emails, all missing emails are judged, `friend_test.py` becomes a registry-based and genuinely failing gate with a variance policy, promise language is reconciled with parallel enrollment, trigger-dependent rewrites are either brought into scope or removed, the binding skill/doc conflict is resolved before drafting, and XC’s complete routing/UTM/CORS/registry prerequisites are specified. After that, the rewrite should ship as a measured GG control-vs-treatment experiment, not a simultaneous replacement across live brands.
