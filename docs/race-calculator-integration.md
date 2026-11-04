# Race calculator entry: GGC → Endure

The race page now mounts a calculator entry in the actual `generate_page`
deep-content list, after “Train for This Race”, with a matching table-of-contents link.
The deliberate `08a` TOC subsection preserves the existing 09–11 section numbers.
It remains 08a when training marketing is suppressed; a real-page test covers
source-blocked, paused and ineligible profiles so the utility remains available.
It does not use the retired, unmounted preparation strip and does not require
a race-pack preview. The locked first-pass page spine is unchanged.

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
pilot GPX is a 2027 course. The Endure calculator must preserve the selected
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
Unsafe slugs downgrade to the generic Endure calculator. Unknown choices are
made in Endure. All profile-supplied strings are HTML-escaped, and the
destination host is a constant.

This entry does not publish a finish estimate, readiness verdict, nutrition
quantity or confidence interval. The personal calculation and its qualification
state belong to Endure. Raw route assets and private athlete values are not
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

Run with the existing Python test environment or the small local test-only
environment used here (Python 3.11 + pytest):

```sh
work/test-venv/bin/python -m pytest tests/test_race_calculator.py tests/test_neo_brutalist.py tests/test_prep_strip.py -q --tb=short
/opt/homebrew/bin/python3.11 -m py_compile wordpress/race_calculator.py wordpress/generate_neo_brutalist.py tests/test_race_calculator.py
```

Preview uses the production path, without deployment:

```sh
python3 wordpress/generate_neo_brutalist.py barry-roubaix --output-dir work/calculator-preview/race
```

The parent owns browser rendering, full preflight, publication and live
verification. No deployment or live acceptance is claimed by these tests.

Serve `work/calculator-preview` as the local root; open `/race/barry-roubaix.html#race-calculator` so the generated `/race/assets/` font/CSS paths resolve. Local generation copied all six host font files; no global font changes were needed.

## Local result

The 35 new cases and neighboring generator/preparation-strip suites pass together: 299 tests. Python 3.11 compilation and `git diff --check` pass. A metadata-only sweep of all 384 source profiles succeeds: 384 safe slugs, 350 explicit editions, 370 with supported distance choices, and a maximum of five choices. This is not a full 384-page browser check.

`preflight_quality.py --quick --offline` exits 0 with eight warnings: three upstream brand-token parity checks cannot run because the sibling brand repository is absent; generated `wordpress/output` coverage and slop checks lack that directory; PHP is unavailable; existing generic-homepage citations and absent photo-QC metadata remain warnings. This probe is not the complete live pre-deploy gate. Release Endure's target calculator route before publishing GGC links, then regenerate/deploy the matching shared asset and HTML set and verify the live pages and cache through the parent workflow.

## Independent source review

A signed-in CLI source-only review ran with `claude-fable-5-1`, tools disabled,
and JSON output. Its first pass found no privacy, XSS, reachability or forecast
truthfulness blocker. It requested TOC numbering consistency and token-existence
coverage; both are implemented. Advisory fixes also centralize style assembly,
clarify the edition/course-file instruction, add a sticky-anchor offset and
correct the mount location documented above. The review excludes generated
profiles and private athlete inputs. Local review prompts and JSON receipts
remain under untracked `work/`. Browser screenshots returned blank canvases in
the parent environment; no visual acceptance is claimed.

The same Fable session independently rereviewed the corrections and returned
**PASS for the GGC calculator entry**, with model usage confirming
`claude-fable-5-1`. The suppression-path advisory then received an explicit
real-page test, and the CSS-extraction docstring was corrected. Remaining
advisories concern minor repeated fallback wording, browser confirmation of
anchor alignment and Endure confirmation of historical editions. None is
a claimed visual or deployment result.
