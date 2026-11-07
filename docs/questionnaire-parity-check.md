# Questionnaire deployment parity

The authoritative two-step flow is `wordpress/generate_plan_intake_pages.py`:
`/training-plans/start/` collects race/date/name/email and a honeypot before
checkout. `/training-plans/details/` holds the remaining questions after payment.
`tests/test_plan_intake_pages.py` retains the legacy question/option parity,
pricing and payload checks. The inline scripts in `web/training-plans-start.js`
and `web/training-plans-details.js` also create conditional/dynamic controls.

`scripts/check_questionnaire_parity.py` preserves the original legacy field and
content-marker checks when `/questionnaire/` actually returns an unredirected
200. Only the repository's exact single same-origin 302 to the canonical start
page selects the new flow. Any other redirect is refused before following it.

For that flow, both public pages must return 200 at their exact canonical URL.
Their parsed complete main DOM must match the corresponding repository builder,
including every control, required attribute, option, label, terms, conditional
container and hidden view. The entire ordered script list must match a
repository-generated inline or external-bundle build, including every inline
body, tag attribute, shared-script fingerprint and placement. Unknown or
changed scripts fail. This covers JS-created controls, API/payload selection,
pricing, validation and state transitions. Ordering also requires the details
token scrub before analytics. External shared script bytes are not fetched by
this page-artifact checker; the shared script's content-addressed URL is checked.
Stylesheet URLs and all external asset bytes remain deployment checks. Canonical and noindex metadata
are required.
Any `<base>` element is rejected, including outside the form, so relative
shared-script URLs cannot resolve against a different origin. A title,
redirect, field count or scattered marker match cannot pass this check.

No checkout, private token, saved response or payment request is made. This is
public deployed-artifact parity, not runtime checkout/payment acceptance. Local
behavior tests and hosted purchase-flow acceptance remain separate checks. The
preflight wrapper still warns on genuine transport unavailability; validator
implementation/import errors explicitly fail rather than becoming warnings;
HTTP error responses, unexpected redirects and malformed contracts fail parity.

Run under Python 3.11:

```sh
work/brand-test-venv/bin/python -m pytest tests/test_check_questionnaire_parity.py tests/test_preflight_questionnaire.py tests/test_plan_intake_pages.py -q --tb=short
work/brand-test-venv/bin/python scripts/check_questionnaire_parity.py
```

A failure should be repaired on the matching surface: the actual legacy
Elementor widget or generated two-step intake. Do not alter a working live
questionnaire to satisfy a checker for a retired flow, skip the parity gate,
or submit real checkout data to investigate this artifact check.

The legacy checker was introduced after the June 2026 Elementor page missed
two shipped commits. That protection remains in place for an actual legacy
200; redirect recognition does not bypass it or accept an unrelated builder.

## Scoped verification receipt

The checker, wrapper and existing intake suites pass together: **133 tests**.
The standalone read-only live checker passes against both public intake pages.
Python 3.11 compilation and `git diff --check` pass. Actual source-only
`claude-fable-5-1` review and corrective re-review returned **PASS**, session
`fe991e99-ec66-4a6f-af93-80a3d72ee347`; local prompts and JSON receipts are
under untracked `work/fable-questionnaire-parity-*`. The explicit no-base
addition also received a separate PASS in `work/fable-questionnaire-base-review.json`. Full release preflight,
asset verification and runtime purchase acceptance remain separate gates.

Malformed HTTP protocol responses fail closed rather than becoming transport
warnings. Future shared-script changes intentionally surface live artifact
drift; a reviewed repair/deployment sequence must resolve it. Do not suppress
the parity gate to ship its repair.
