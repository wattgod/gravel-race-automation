# Race calculator entry: GGC → Endure Labs

The race page now mounts a calculator entry in the actual `generate_page`
deep-content list, after “Train for This Race”, with a matching table-of-contents link.
The deliberate `08a` TOC subsection preserves the existing 09–11 section numbers.
It remains 08a when training marketing is suppressed; a real-page test covers
source-blocked, paused and ineligible profiles so the utility remains available.
It does not use the retired, unmounted preparation strip and does not require
a race-pack preview. The locked first-pass page spine is unchanged.

## Athlete-first handoff

The entry now describes the intended sequence: selected race → the athlete's
own training history in Endure Labs → conditions and practical race scenarios
→ a ballpark finish estimate. It does not invite the rider to configure power
or physics parameters. This remains the existing native form, with no new
calculator or personal inputs on GGC.

The selected edition and distance are identity, not proof of route coverage.
Endure Labs must retain them through authentication and resolve the athlete's
own history only after authentication. If that exact edition has no usable
course, it must explain the gap before estimating. In particular, the public
2026 Unbound 200 pilot route must never be relabelled as a 2027 course.
Source-blocked GGC profiles continue to omit edition and distance rather than
asserting unavailable current-course metadata. The public note asks the rider
to confirm edition-specific course availability.

This handoff copy describes the flow being implemented, not evidence of a
completed hosted release. Publish it only with the matching authenticated
athlete-first destination. It claims no verified route, group prediction,
forecast availability, or validated finish-time accuracy.

## Browser contract

The native GET form targets:

`https://endurelabs.app/plan/races/calculator`

It submits only allowlisted public metadata:

- `source=gravel`
- `race`: a validated profile slug, when available
- `edition`: an explicit source year, when available
- `distance`: the selected source variant key, when available

For example, `source=gravel&race=barry-roubaix&edition=2027&distance=62-mile`
reflects the current GGC profile. It does not imply that the acquired 2026
pilot GPX is a 2027 course. The Endure Labs calculator must preserve the selected
metadata through sign-in, verify catalog identity, and let the athlete select
the edition and course file. It must never save an event implicitly.

The form requires no JavaScript, third-party iframe, cross-site session or
personal query parameters. No mass, power, email or other health input exists
on this public entry. A selected distance is native form state, not a fixed
primary-course hyperlink. Existing consent/analytics/header infrastructure
remains in the generator.

## Unknown and legacy profiles

The helper reads structured `distances`, `distance_options` and
`distance_variants` lists at race or vitals level. It preserves explicit safe
keys. Without an explicit key, an unambiguous source measurement becomes a
stable metadata key such as `62-mile`, `66-5-mile` or `37-5-km`. Named and
measured labels stay visible. It does not parse prose lists into invented
variants, convert kilometres into approximate miles, or infer variants from a
race name. A primary numeric distance is a fallback only when supported by the
source. Conflicting duplicate keys are omitted rather than silently selected.

An unknown edition stays omitted; the current year is never a fallback.
Source-blocked profiles do not pass an old edition or distance as current.
Unsafe slugs downgrade to the generic Endure Labs calculator. Unknown choices are
made in Endure Labs. All profile-supplied strings are HTML-escaped, and the
destination host is a constant.

This entry does not publish a finish estimate, readiness verdict, nutrition
quantity or confidence interval. The personal calculation and its qualification
state belong to Endure Labs. Raw route assets and private athlete values are not
redistributed by this change.

## GG×Glyph presentation

The scoped control surface uses the existing Sometype Mono / Source Serif 4
fonts and `--gg-*` token chain. It has flat paper/brown surfaces, source data
labels, a dotted course-file note, 48px controls, keyboard focus and a 150ms
transform-only hover response. Reduced motion removes that response. No global
fonts, color tokens, scoring, rankings, header, consent or SEO fields change.
The calculator CSS enters both inline page output and the existing hashed
shared-asset pipeline through one style-tag assembly helper. Its anchor offset includes
the measured sticky-header height and a token-based allowance for the sticky TOC.
A focused test verifies every referenced token against the emitted token CSS or
the actual header runtime setter; upstream canonical parity remains a separate check. Deploy regenerated page HTML together with the generated
shared CSS asset; do not edit hashed files by hand.

## Copy provenance and editorial check

Surface: race-page utility control for riders opening a personal course
scenario. Register: concise product language. The copy states navigation and
input choices, without a forecast or marketing promise.

Read-only source retrieval used these `wattgod/writing-graph` paths:

- `self/voice-and-beliefs-profile.md`
- `inbox/gravel-god/hacking-unbound-200-with-best-bike-split.md`
- `vendor/no-ai-slop/SKILL.md`
- `vendor/no-ai-slop/eval.md`

The raw public article grounds the distinction between rider, course and
weather choices. Authorship was independently verified on the public article byline, Matti Rowe, April 8, 2023. No quotations, numeric claims, anecdotes, profanity or private
material were reused. The profile's product register governs the short labels.
The full pinned no-AI-slop edit workflow and eval were read. The final copy
passes the repository mechanical slop check and each applicable eval criterion:
the action appears early, exact controls carry the details, prose is direct,
and there is no inflated promise, invented evidence, faux narrator, decorative
metaphor, rhetorical setup or summary kicker. With no supplied prose draft,
the minimum-edit principle means keeping only the functional labels and brief
course-file instruction. These provenance notes are technical documentation,
not part of the generated public page.

## Verification and preview

Focused checks originally used a small Python 3.11 + pytest environment.
The same task-local environment now has the complete `requirements.txt` set
and a task-local Chromium headless runtime for the full test suite:

```sh
work/test-venv/bin/python -m pytest tests/test_race_calculator.py tests/test_neo_brutalist.py tests/test_prep_strip.py -q --tb=short
/opt/homebrew/bin/python3.11 -m py_compile wordpress/race_calculator.py wordpress/generate_neo_brutalist.py tests/test_race_calculator.py
```

Preview uses the production path, without deployment:

```sh
python3 wordpress/generate_neo_brutalist.py barry-roubaix --output-dir work/calculator-preview/race
```

The parent owns publication and live verification. Local browser and full
validation receipts are recorded below; neither establishes production acceptance.

Serve `work/calculator-preview` as the local root; open `/race/barry-roubaix.html#race-calculator` so the generated `/race/assets/` font/CSS paths resolve. Local generation copied all six host font files; no global font changes were needed.

## Local result

The 35 new cases and neighboring generator/preparation-strip suites pass together: 299 tests. Python 3.11 compilation and `git diff --check` pass. A metadata-only sweep of all 384 source profiles succeeds: 384 safe slugs, 350 explicit editions, 370 with supported distance choices, and a maximum of five choices. This is not a full 384-page browser check.

`preflight_quality.py --quick --offline` exits 0 with eight warnings: three upstream brand-token parity checks cannot run because the sibling brand repository is absent; generated `wordpress/output` coverage and slop checks lack that directory; PHP is unavailable; existing generic-homepage citations and absent photo-QC metadata remain warnings. This probe is not the complete live pre-deploy gate. Release Endure Labs's target calculator route before publishing GGC links, then regenerate/deploy the matching shared asset and HTML set and verify the live pages and cache through the parent workflow.

## Independent source review

A signed-in CLI source-only review ran with `claude-fable-5-1`, tools disabled,
and JSON output. Its first pass found no privacy, XSS, reachability or forecast
truthfulness blocker. It requested TOC numbering consistency and token-existence
coverage; both are implemented. Advisory fixes also centralize style assembly,
clarify the edition/course-file instruction, add a sticky-anchor offset and
correct the mount location documented above. The review excludes generated
profiles and private athlete inputs. Local review prompts and JSON receipts
remain under untracked `work/`. Earlier screenshot attempts returned blank
canvases; a later local browser measurement and screenshot are recorded below.
No production acceptance is claimed.

The same Fable session independently rereviewed the corrections and returned
**PASS for the GGC calculator entry**, with model usage confirming
`claude-fable-5-1`. The suppression-path advisory then received an explicit
real-page test, and the CSS-extraction docstring was corrected. Remaining
advisories concern minor repeated fallback wording, browser confirmation of
anchor alignment and Endure Labs confirmation of historical editions. None is
a claimed visual or deployment result.

## Narrow-screen integration correction

A parent browser DOM audit found the existing single-column grid's automatic
minimum expanding the main column to 632px inside a 456px mobile container.
The mobile grid now uses `minmax(0, 1fr)` and the main grid item has
`min-width: 0`. This permits the calculator and its ancestor column to shrink
with the viewport; desktop retains its existing two-column track definition.
The preview was regenerated for a new browser measurement. Source/test checks
do not substitute for that measurement or visual acceptance.

A fresh source-only `claude-fable-5-1` review returned PASS for this two-rule
correction. Source inspection confirms the main element is the grid's direct
child and no later main-width rule overrides it. The parent browser audit
remains responsible for detecting independent child-content overflow.

## Full validation receipt — November 4, 2026

The task-local Python 3.11.17 environment was completed with
`work/test-venv/bin/python -m pip install --no-cache-dir -r requirements.txt`.
`pip check` reports no broken requirements. Chromium headless and FFmpeg were
installed under `work/playwright-browsers`, without changing the shared browser
cache or global Python installation. The resolved package versions are retained
in the untracked `work/calculator-venv-freeze.txt` receipt.

```sh
PLAYWRIGHT_BROWSERS_PATH="$PWD/work/playwright-browsers" work/test-venv/bin/python -m pytest tests/ -q --tb=short -x
```

Result: **11,139 passed, 298 skipped, 31 warnings in 370.70 seconds**; all
11,437 tests collected. This includes the synthetic exit-survey browser tests,
whose outbound requests are intercepted. The first complete-environment run
stopped at the missing Chromium executable after 2,140 passes; installing the
local runtime resolved that environment failure. No code changes were needed.
The final full-suite log is
`work/calculator-full-pytest-with-browser.log`.

The complete release checks are not all green:

- `work/test-venv/bin/python scripts/preflight_quality.py` exits 1 for live
  questionnaire parity: 76 fields/markers differ from the repository form.
  The fetched public page has the title “Build Your Plan | Gravel God Cycling”,
  65,308 bytes, five form controls and no challenge-page indicators. Its SHA-256
  is `2881bea70069e0a36d5d719435a945beeab4550c68eddc3f9ea5c289ae856617`.
  Comparing the same response against pre-calculator commit `2cb53ff` produces
  the same 76 findings; both the form source and checker are unchanged. This
  proves an existing parity difference, not that the live form is broken.
- `work/test-venv/bin/python scripts/preflight.py --skip-tests` was run alongside
  the independent full pytest invocation, in validate-only mode. Color and
  citation checks pass; the existing race-data audit warns. Blog validation
  reports 61 passes and six failures because `wordpress/output/blog` and its
  generated recap files are absent in this worktree. No `--generate` or
  `--deploy` invocation was made.
- Standalone `work/test-venv/bin/python scripts/youtube_validate.py` exits 1:
  all 1,130 reported errors across 262 enriched profiles are missing photo/GIF
  files on disk. The validator and `race-data` are unchanged from `2cb53ff`.
- Full quality-check warnings also identify missing sibling brand-token files,
  absent generated-output coverage/slop inputs, unavailable PHP syntax tooling,
  existing generic-homepage citations, absent photo-QC metadata and the
  research-dump backlog. Missing inputs remain unverified checks.

Detailed untracked receipts are `work/calculator-full-validation-summary.json`,
`work/calculator-questionnaire-baseline-receipt.json`,
`work/calculator-existing-artifact-baseline.json`,
`work/calculator-full-preflight-quality.log`,
`work/calculator-validate-only.log` and
`work/calculator-youtube-validation.log`.

## Local narrow-screen browser receipt

The parent measured the regenerated race preview in a **390 CSS-pixel iframe**:
its document width was 390px, the calculator entry was 366px wide, the controls
were 48px high, and there was no horizontal overflow. Keyboard focus showed a
2px outline. The screenshot is `outputs/ggc-calculator-390.jpg` in the parent
Codex task artifacts, outside this repository. This verifies that local browser
configuration; it is not physical-device or production evidence.

The public handoff remains on hold until Endure Labs's target route is live. Publishing
GGC still requires the matching regenerated shared CSS and HTML, the applicable
release-gate disposition, cache purge and verification of the live race pages.
Neither the full pytest result nor this local browser measurement is full
production acceptance.

## Release-preparation checkpoint — November 4, afternoon

The stale questionnaire blocker is repaired against the actual two-step public
intake, retaining the legacy checks. All 133 scoped intake/checker tests pass;
actual Fable source review and corrective review pass. The standalone live
parity check passes. See `questionnaire-parity-check.md`.

A complete fresh race-only package is retained on the external drive at
`/Volumes/Seagate Backup Plus Drive/Codex-work/race-release-20261104/ggc-package`:
384 race pages, 384 matching prep kits and 384 Markdown profiles, with eight
shared assets. All slug sets match, every calculator handoff is present, and
asset content hashes agree. Total package size is 92.1 MB. Its Markdown guide
inventory comes from 354 genuine public training-guide HTML pages verified
against exact URLs and canonicals; it is not an empty stand-in inventory.

Separate validation inputs include 1,130 existing public media files restored
with exact same-origin URL, type, signature, length and SHA256 receipts, plus
real generated blog artifacts. No media or blog is added to the scoped
publication package. The final stable validation tree contains 829 HTML files.
Unmodified quality preflight passes with 12 existing advisories; validate-only
preflight passes (four checks, two warnings), YouTube validation reports zero
errors, and blog validation passes 132 checks with no failures or warnings.
The external package retains manifests and the exact final logs.

The recreated external Python 3.11 full-suite run exposed an existing raw-shell
path bug when its temporary path contained spaces. The verify/promote builders
now quote literal paths while retaining supported `~/` expansion. All 83 atomic
deploy tests pass, including real paths with spaces, quotes and literal shell
syntax; actual Fable review passes. Locking, count/size/truncation checks,
promotion receipts and preservation of sibling content remain intact.

Head `40198d0` subsequently passed GitHub full-suite validation on an identical
merge tree: 11,194 tests passed / 299 skipped, plus 423 Mission Control tests.
Regression and immune checks also passed. The redundant local rerun was stopped
after the exact-tree CI proof; no local full-suite pass is claimed. GitHub
hosting secrets exist, while the local SiteGround key/configuration is absent.
A separately reviewed scoped runner is being prepared; no deployment ran.

## Product audit: finish outcomes before physics controls

The user's November 4 review identified a more fundamental release blocker.
The Endure Labs form currently asks for steady average power and simulates a
solo ride. It does not yet infer sustainable race effort from athlete history,
use forecast weather, or model group retention and getting dropped. Exposing
fewer fields alone cannot close those gaps.

The owning corrective contract is Endure Labs
`specs/race-performance/product-audit-20261104.md`. It requires athlete ability,
an exact course, valid weather and supported race scenarios to drive a ballpark
finish estimate. Numerical settings belong inside the model; bike/setup
assumptions should be understandable, disclosed and inspectable. Scenario
spread must not be called a confidence interval without coverage validation.
BBS functionality research is distinct from a matched-input numerical comparison;
no numerical parity or real-world accuracy qualification is claimed.

The public handoff remains on hold. Keep the existing namespace, edition and
distance continuation contract, but regenerate publication artifacts only after
the final product source is frozen. Passing site tests and preparing a safe
release runner do not make the current manual calculator ready to launch.
