# Native coaching onboarding

Implemented, with production signing disabled until the exact native documents receive counsel approval. See the companion backend's `docs/native-coaching-legal-review.html` and `docs/native-coaching.md` for the document comparison, evidence model, and activation configuration.

The existing `/coaching/apply/` form gains native agreement/privacy controls when the backend reports native signing ready. The new `/coaching/setup/` page lets an existing applicant sign without submitting another questionnaire or selecting a different tier. It removes the private capability from the URL before analytics loads. Consent starts unchecked and resets when the disclosed service changes. Signed records can be downloaded. No private athlete or health information is sent to analytics.

## Deployment after document approval

1. Deploy the companion backend with native signing disabled.
2. Deploy `workers/coaching-intake/worker.js` using the existing Worker deployment configuration and shared intake secret.
3. Generate both pages:
   - `python3 wordpress/generate_coaching_apply.py`
   - `python3 wordpress/generate_coaching_setup.py`
4. Run the repository's required deployment checks, including `python3 scripts/preflight_quality.py --quick`, the focused coaching tests, and the complete site test suite.
5. Publish with the existing deploy workflow: `python3 scripts/push_wordpress.py --sync-coaching-apply --sync-coaching-setup`. Do not change the separate `/questionnaire/` Elementor page.
6. Record the new backend approval receipt and secret; enable native signing. Verify native readiness and a synthetic signing record before creating Scott's real completion link.

## Verification

Focused tests cover generated-page wiring, early capability removal, safe DOM construction, brand tokens, deploy flags, Worker origin/brand isolation, route allowlists, and private response headers. A local browser run against the actual Worker/backend used a synthetic athlete and approval; it verified required assent, signing, complete copy download, repeat viewing, application mount, and mobile layout without browser errors. No production URL has been activated or verified.

Interface copy follows the current user's direction, the writing-graph Gravel God voice profile and original coaching article, and the pinned no-ai-slop guidance. No coaching selection challenge was added to Scott's completion page.
