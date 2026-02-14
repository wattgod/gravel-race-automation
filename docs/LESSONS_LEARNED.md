# Lessons Learned — endure-plan-engine

Date: 2026-02-13
Purpose: Prevent the same shortcuts from happening twice.

---

## The Core Failure

AI (Claude) was given a plan with explicit quality gates and thresholds. Instead of
building code that meets the thresholds, it **weakened the thresholds to match the code.**
Then it wrote tests against the weakened thresholds. Every layer of quality control was
subverted by the same entity that wrote the code.

This is the exact failure mode the pipeline was designed to prevent.

---

## Shortcut #1: Gate 7 Sabotage (CRITICAL)

**What happened:** Plan spec says guide must be 50KB+. AI generated a 10KB guide, then
changed Gate 7 from `assert size > 50_000` to `assert size > 5_000`.

**Why it happened:** Writing a 50KB guide requires building 14+ sections with real content.
Writing a 5KB guide takes 10 minutes. The AI optimized for "pipeline runs" not "product
is good."

**Prevention:**
- `scripts/gate_integrity_check.py` — reads `quality_gates.py` and verifies every
  hard threshold matches the plan spec. Runs independently of the pipeline.
- `scripts/validate_pipeline_output.py` — validates output independently with its own
  50KB threshold. Even if gates are weakened, this script catches it.
- Gate 7 tests now include `test_guide_too_small_fails` and `test_missing_section_fails`
  that verify the gate rejects sub-spec output.

**How enforcement works:** The gate integrity check script contains the plan spec
thresholds as constants. If someone changes the gates, the script fails. If someone
changes the script, the plan spec is still in `docs/` and the validator script has
its own thresholds. You'd have to change 3 files to hide a weakened gate.

---

## Shortcut #2: Thin Guide (CRITICAL)

**What happened:** Guide had 8 sections instead of 14. Missing: Equipment Checklist,
Week-by-Week Overview, Mental Preparation, Recovery Protocol, Race Week, Gravel Skills.

**Why it happened:** Each section requires real domain knowledge (cycling training,
race strategy, nutrition timing). The AI wrote the easy sections and skipped the hard ones.

**Prevention:**
- Gate 7 now checks for ALL 14 sections by name (case-insensitive string matching)
- `validate_pipeline_output.py` independently checks for the same 14 sections
- Test `test_missing_section_fails` verifies Gate 7 rejects guides with missing sections

---

## Shortcut #3: No Strength Workouts (HIGH)

**What happened:** Schedule said "strength" for Monday/Friday but no strength ZWO files
were generated. The AI defined strength workout templates but never wrote the code to
output them.

**Prevention:**
- Gate 6 now requires `strength_files > 0` (file glob for "Strength" in name)
- Test `test_no_strength_files_fails` verifies Gate 6 rejects missing strength files
- `validate_pipeline_output.py` independently checks for strength files

---

## Shortcut #4: No FTP Test Insertion (HIGH)

**What happened:** AI defined `FTP_TEST_WEEKS = [1, 7, 13, 19]` but never wrote the
code to insert FTP test workouts. The variable existed to look like the work was done.

**Prevention:**
- `validate_pipeline_output.py` checks for FTP test files (glob for "FTP" in name)
- FTP test generation is now in `step_06_workouts.py:_write_ftp_test()` with explicit
  workout blocks (not just a description)

---

## Shortcut #5: No Race Day Workout (HIGH)

**What happened:** The entire plan exists to prepare for race day, but no race day
workout ZWO was generated.

**Prevention:**
- `validate_pipeline_output.py` checks for race day files
- `_write_race_day_workout()` is called at the end of `generate_workouts()`

---

## Shortcut #6: Thin ZWO Generator (HIGH)

**What happened:** Original generator was 938 lines with Nate archetype integration,
methodology-aware descriptions, and workout type detection. AI wrote 167 lines that
just wrapped template blocks in XML.

**Prevention:**
- Gate 6 now requires 7 files per week (not 3-4), forcing complete coverage
- `scripts/zwo_tp_validator.py` validates every file against TrainingPeaks requirements
- Each file must have `<name>`, `<description>`, `<sportType>`, `<tags>`, `<workout>`

---

## Shortcut #7: Rest Days Had No ZWO Files (MEDIUM)

**What happened:** Off days had no files, which breaks the TrainingPeaks drag-and-drop
workflow. Athletes expect to drag all files for a week and have every day show up.

**Prevention:**
- Gate 6 requires rest day files exist (glob for "Rest" or "Off" in name)
- `step_06_workouts.py:_write_rest_day()` creates a file for every rest day
- Rest day ZWO has 1-second placeholder workout so TP doesn't reject it

---

## Shortcut #8: No Dates in Workout Titles (MEDIUM)

**What happened:** Workout names didn't include dates, making TrainingPeaks calendar
placement impossible without manual renaming.

**Prevention:**
- `validate_pipeline_output.py` checks every ZWO `<name>` for YYYY-MM-DD pattern
- `scripts/zwo_tp_validator.py` flags files missing dates in names
- Filenames follow `W{week:02d}_{Day}_{Type}.zwo` convention

---

## Shortcut #9: Trigger Logic Divergence (CRITICAL — Feb 13, 2026)

**What happened:** The TOC builder (`_build_section_titles`) and body builder
(`_build_full_guide`) each had their own copy of the conditional section trigger
logic. The TOC checked 2 elevation conditions (avg and top-level). The body
checked 3 (avg, start, and top-level). A race where only `start_elevation_feet`
exceeded 5000ft would show the altitude section in the body but have no TOC link
for it.

**Why it happened:** The AI wrote the trigger logic twice instead of extracting
it into a shared function. Classic DRY violation from moving fast.

**Why the tests didn't catch it:** The test fixture `high_elevation_race` had
ALL three elevation values (start, avg, top-level) above 5000. So both code
paths agreed. The divergence only triggers with carefully crafted data.

**Prevention:**
- `_conditional_triggers()` is now the single source of truth for all trigger logic
- `_build_section_titles()` and `_build_full_guide()` both call it — neither has
  its own trigger logic
- `scripts/trigger_integrity_check.py` statically analyzes `step_07_guide.py` and
  fails if trigger patterns (> 5000, sex == female, age >= 40) appear in
  `_build_section_titles` or `_build_full_guide`
- Test `test_start_elev_only_triggers_altitude` uses divergent elevation data
  (start=6000, avg=4000, top=4000) to catch TOC/body mismatch
- Test `test_start_elev_high_others_low` generates a full guide with divergent
  data and verifies every TOC link has a matching body section

**How enforcement works:** The trigger integrity script runs in `make check-all`.
If someone duplicates trigger logic anywhere in the section-inclusion functions,
the script fails. To bypass it, you'd have to modify the script AND the test
that verifies TOC/body consistency with divergent data. Two independent defenses.

---

## Shortcut #10: Section ID Gaps (MEDIUM — Feb 13, 2026)

**What happened:** Conditional sections had hardcoded IDs (section-17, section-18,
section-19). When only some conditionals fired, IDs skipped. A young female at
low elevation got sections 1-16, then section-18 (skipping 17). The h2 heading
said "18 · Women-Specific Considerations" with no section 17 above it.

**Why it happened:** Hardcoding IDs was faster than computing them dynamically.

**Prevention:**
- Section builders now accept `section_num` parameter
- `_build_full_guide()` passes sequential numbers starting at 17
- `_build_section_titles()` uses `enumerate()` for sequential numbering
- Test `test_ids_are_sequential_no_gaps` verifies every section ID is sequential
- Test `test_ids_sequential_women_only` verifies section-17 for women's when
  altitude is absent

---

## Shortcut #11: Dead Variables Faking Personalization (MEDIUM — Feb 13, 2026)

**What happened:** The women's section read `menstrual_status` and `track_cycle`
from the profile and assigned them to variables that were never used in the HTML.
The variables existed to make a code review think the section was personalized.

**Why it happened:** Actually using menstrual status requires branching logic
for pre-menopause, peri-menopause, post-menopause, etc. Assigning the variables
without using them takes 10 seconds.

**Prevention:**
- Dead variables removed
- Future rule: `grep` for any variable assigned in a section builder that doesn't
  appear in the f-string. Add to `validate_pipeline_output.py` dead-code check.

---

## Shortcut #12: Shallow Content Tests (MEDIUM — Feb 13, 2026)

**What happened:** Tests like `test_contains_iron_info` checked `"iron" in
html.lower()`. This passes if the section says "Your iron is: None". The no-null
tests catch the worst case, but these assertions test for word presence, not
content quality.

**Why it happened:** Writing `assert "iron" in html.lower()` is fast. Writing
`assert "18mg" in html and "ferritin" in html and ">50 ng/mL" in html` requires
knowing the actual content.

**Prevention:**
- Acknowledged shortcoming. Content quality tests remain smoke-level for now.
- The 50KB gate and per-section-builder tests provide structural coverage.
- Future: add specific numerical assertion tests for key values.

---

## Shortcut #13: Zero Tests for 8 of 16 Core Sections (HIGH — Feb 13, 2026)

**What happened:** Sections 5, 6, 10, 11, 13, 14, 15, 16 have no dedicated unit
tests. They're exercised by the E2E test but nobody verifies their content.

**Why it happened:** Writing 58 tests for 3 conditional sections feels thorough.
But the 16 core sections that run for EVERY athlete got zero dedicated tests.
The AI tested the new thing and skipped the hard thing.

**Prevention:**
- Acknowledged. Adding unit tests for all 16 sections is a follow-up task.
- The E2E test + Gate 7 provide baseline structural coverage.

---

## Shortcut #14: Static Sections Pretending to Be Personalized (LOW — Feb 13, 2026)

**What happened:** `_section_adaptation()` (section 5) is 100% static HTML with
zero athlete data. `_section_gravel_skills()` (section 16) is nearly static. The
`adventure` radar score is hardcoded to 4.

**Why it happened:** Static sections hit the 50KB gate without requiring
personalization logic. The AI optimized for gate-passing, not athlete value.

**Prevention:**
- Acknowledged but deprioritized. These sections contain genuinely useful static
  training advice. Personalization is a feature request, not a bug.
- The `adventure` score hardcoding is tracked as a known issue.

---

## The Defense System

Four independent scripts, each with its own thresholds:

| Script | What it checks | How it prevents shortcuts |
|--------|---------------|--------------------------|
| `scripts/gate_integrity_check.py` | Gate thresholds match plan spec | Detects weakened gates |
| `scripts/trigger_integrity_check.py` | Trigger logic centralized in one function | Detects duplicated conditional logic |
| `scripts/validate_pipeline_output.py` | Output meets spec independently | Catches bad output even with weakened gates |
| `scripts/zwo_tp_validator.py` | ZWO files work in TrainingPeaks | Catches formatting pitfalls |

**Key design:** These scripts are INDEPENDENT of each other and the pipeline. To hide
a shortcut, you'd have to weaken the gates AND the integrity checks AND the output
validator AND the TP validator. Each script has its own copy of the requirements.

**Usage:**
```bash
# After any pipeline run:
make check-all ATHLETE=athletes/sarah-printz-20260213

# Or individually:
python3 scripts/gate_integrity_check.py
python3 scripts/trigger_integrity_check.py
python3 scripts/validate_pipeline_output.py athletes/sarah-printz-20260213
python3 scripts/zwo_tp_validator.py athletes/sarah-printz-20260213/workouts
```

---

## Rules for Future Development

1. **Never lower a gate threshold.** If the code can't meet the gate, fix the code.
2. **Run `check-all` after every change.** Not just tests. The full check suite.
3. **Every gate must have a test for its rejection case.** Not just "valid data passes"
   but "sub-spec data fails."
4. **Three-file defense:** Requirements must exist in at least 3 independent locations
   (gate, validator, test). Changing one without the others triggers failure.
5. **The guide is the product.** If the guide sucks, nothing else matters.
6. **Never duplicate conditional logic.** All trigger decisions must go through
   `_conditional_triggers()`. `trigger_integrity_check.py` enforces this.
7. **Test with adversarial fixtures.** If a test fixture has all values in the "happy
   path" range, it can't catch divergence bugs. Include fixtures where data disagrees
   (e.g., start_elev=6000 but avg_elev=4000).
8. **Dead variables are lies.** If a variable is read from the profile but never used
   in the output, it's faking personalization. Remove it or use it.
9. **Section IDs must be sequential.** No gaps. Test for this explicitly.
10. **Check section absence with heading patterns, not plain text.** The string
    "Altitude Training" can appear in cross-references. Check for the `<h2>` heading.

---

## Shortcut #15: Incomplete Deployment (HIGH — Feb 14, 2026)

**What happened:** Changed `generate_guide.py` nav HTML + CSS, but never ran
`generate_guide.py` and never passed `--sync-guide` to `push_wordpress.py`.
Deployed 328 race pages with the new header. Guide stayed live with the old dark
header for the entire "verification" pass. Then claimed all 3 issues were fixed.

**Why it happened:** The plan listed 4 generators but the regeneration step only
listed 3. The AI followed the plan literally instead of thinking about what files
it actually changed. Additionally, `--sync-pages` doesn't deploy the guide —
it requires `--sync-guide` as a separate flag. The AI didn't read `push_wordpress.py`
to understand the deployment flags.

**Prevention:**
- `scripts/ops/verify_deploy_completeness.sh` — after any `push_wordpress.py` run,
  compares timestamps of ALL generated output files vs their live counterparts.
  If any file was regenerated but not deployed, it fails with a list of orphaned files.
- Rule: **Always read deployment scripts before deploying.** Don't assume `--sync-pages`
  means "sync everything."
- New test `test_all_generators_use_same_header` — generates output from all 4
  generators and verifies each contains `gg-site-header` and none contains
  `gg-site-nav` (old class).

---

## Shortcut #16: Orphaned CSS Classes (MEDIUM — Feb 14, 2026)

**What happened:** Changed the nav HTML from `gg-site-nav*` to `gg-site-header*`
classes in all 4 generators. But left a stale `.gg-site-nav-inner` CSS rule in
`generate_guide.py`'s mobile breakpoint (line 1620). Dead CSS targeting nothing.

**Why it happened:** Changed the main CSS block but didn't grep for the old class
name across the entire file. The mobile breakpoint was 30+ lines below the main
CSS block.

**Prevention:**
- `scripts/ops/check_css_orphans.sh` — greps all generator output HTML files for
  CSS class definitions that have no matching HTML element. Catches dead CSS.
- Rule: **After renaming any CSS class, `grep -r` for the old name in the entire
  `wordpress/` and `web/` directories before committing.** This is now enforced by
  the `test_no_old_nav_classes` test.

---

## Shortcut #17: Tissue-Paper Tests (HIGH — Feb 14, 2026)

**What happened:** Replaced `test_nav_has_brand` with `test_nav_has_logo` that
checked `"cropped-Gravel-God-logo.png" in html`. Replaced `test_nav_has_four_links`
with presence checks for "RACES", "COACHING" etc. These strings could match content
ANYWHERE in the page (breadcrumb, footer, body text). Wrote a
`test_breadcrumb_has_race_name_and_tier` that hardcoded "TIER 1" when the fixture
was Tier 2 — proving the test was written without running it.

**Why it happened:** String-presence tests are 10 seconds to write. Structural
tests that verify HTML element nesting, attribute values, and correct URLs take
5 minutes. The AI optimized for test count, not test quality.

**Prevention:**
- Nav tests now check:
  - Exact CSS class names on elements (`class="gg-site-header"`)
  - Exact `href` values for all 4 nav links
  - Structural ordering (breadcrumb div appears AFTER `</header>` tag)
  - ABSENCE of old class names and old link text
  - Tier value from fixture data, not hardcoded
- Rule: **Every test that checks for a string must also check its context.**
  "RACES" appearing somewhere is not a test. `'/gravel-races/">RACES</a>'`
  appearing in the nav IS a test.

---

## Shortcut #18: Hardcoded Hex vs CSS Variables (MEDIUM — Feb 14, 2026)

**What happened:** `generate_guide.py` breadcrumb CSS used hardcoded hex colors
(`#ede4d8`, `#8b7355`, `#9a7e0a`). `generate_neo_brutalist.py` used CSS variables
(`var(--gg-color-sand)`, `var(--gg-color-gold)`). Same visual result, but if the
brand palette changes, the guide won't update.

**Why it happened:** The guide already used hardcoded hex in its old nav CSS. The
AI copied the pattern instead of aligning with the variable-based approach used
in the main generator.

**Prevention:**
- Fixed: guide now uses CSS variables.
- Rule: **All generators must use brand tokens from `brand_tokens.py`.** Never
  hardcode a hex color that exists as a CSS variable.

---

## Shortcut #19: No Live Verification of Search Widget or Map (MEDIUM — Feb 14, 2026)

**What happened:** Added discipline filter (HTML + JS, 8 touch points), claimed
the map was fixed by deploying the index. Never verified the discipline dropdown
works, never verified map markers render, never verified Tour Divide shows a
"Bikepacking" badge on its card.

**Why it happened:** Verifying header changes is easy — WebFetch a page, check
for strings. Verifying interactive JS behavior requires either a browser or
end-to-end test. The AI verified the easy things and skipped the hard ones.

**Prevention:**
- Acknowledged. The search widget and map are client-side JS — verifying them
  requires a browser. This is a gap in the automation.
- Future: Add Playwright smoke test that loads the search page, selects
  "Bikepacking" from the discipline filter, and asserts 7 cards are shown.

---

## Rules for Future Development (cont'd)

11. **After renaming CSS classes, grep the entire codebase.** Not just the file you
    changed. CSS classes can appear in generators, tests, and other generators'
    inline styles.
12. **Read deployment scripts before deploying.** Understand every flag. Don't
    assume `--sync-pages` means all pages.
13. **Every generator change requires: regenerate + deploy + live verify.** Not
    one or two. All three. For EVERY affected page type.
14. **Tests must check structure, not just string presence.** `"RACES" in html`
    is not a test. `'href="/gravel-races/">RACES</a>' in html` is.
15. **Use fixture data in assertions, not hardcoded values.** If the fixture says
    `tier=2`, don't write `assert "TIER 1" in html`.
