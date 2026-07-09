---
name: deploy-safely
description: Load before any deploy to gravelgodcycling.com or any SiteGround/WordPress operation (push_wordpress.py, mu-plugin edits, cache purge, Elementor pages).
---

# Deploy Safely (gravelgodcycling.com)

Layer CLAUDE.md's "Deploy"/"Articles" sections don't cover: exact command
order, what each script does, SiteGround/WordPress traps specific to this
repo. Read CLAUDE.md Deploy/Articles and
`gravel-god-cycling/docs/deploy-runbook.md` first — not repeated here.

## 1. Pre-deploy gate sequence (verified from repo root)

`scripts/preflight.py` chains most of this. Plain invocations, in order:

```
python3 -m pytest tests/ -q --tb=short -x
python3 scripts/audit_colors.py
python3 scripts/validate_citations.py
python3 scripts/validate_blog_content.py
python3 scripts/youtube_validate.py
```

Changed `wordpress/ab_experiments.py` or its config? Regenerate before
pytest, or `test_experiments_json_matches_source` fails: `python3
wordpress/ab_experiments.py`. Quality gate is separate — `preflight.py` does
NOT call it: `python3 scripts/preflight_quality.py` (`--quick` skips slow
checks, `--js` for JS-only).

Six test files import PIL, commonly excluded when Pillow isn't installed:
`test_guide_templates.py`, `test_photo_qc.py`, `test_video_assembly.py`,
`test_youtube_screenshots.py`, `test_youtube_integration.py`,
`test_youtube_thumbnail.py`. Use `--ignore tests/test_x.py` per file, not a
blanket skip.

One-shot validate+generate+deploy+post-checks: `python3 scripts/preflight.py
--deploy`. Exact phase order (read from source): pytest → audit_colors →
validate_citations → audit_race_data (warn-only) → validate_blog_content →
youtube_validate → generate_index.py --with-jsonld → generate_season_roundup
--all → generate_blog_index → generate_blog_index_page → generate_sitemap
--blog → generate_neo_brutalist --all → generate_prep_kit --all →
generate_homepage → generate_methodology → generate_tier_hubs →
push_wordpress --deploy-content → push_wordpress --sync-homepage →
validate_deploy → validate_redirects (warn-only).

`preflight.py --deploy` does NOT run `preflight_quality.py`, does NOT
regenerate `ab_experiments.py`, and `--deploy-content` does NOT include
mu-plugin syncs (section 3) or article SCP sync. Run those separately —
"--deploy passed" is not "everything shipped".

## 2. SSH / SiteGround mechanics

- Key `~/.ssh/siteground_key`. Credentials via env vars `SSH_HOST`, `SSH_USER`,
  optional `SSH_PORT` (default `18765`) — `get_ssh_credentials()` in
  `push_wordpress.py`. Nothing hardcoded in the repo.
- Race pages: tar+ssh pipe (`sync_pages()`), flat `{slug}.html` →
  `{slug}/index.html`. Never rsync.
- Articles: SCP to `/articles/{slug}/index.html`, separate from `--sync-blog`
  (targets `/blog/`) — see CLAUDE.md Deploy section.
- Cache purge is scripted: `purge_cache()` SSHes `wp --path=$HOME/www/
  gravelgodcycling.com/public_html sg purge` (SiteGround wp-cli command) —
  clears static, dynamic, memcached, opcache in one call. Pass
  `--purge-cache` on any `push_wordpress.py` invocation, or it's already
  folded into `--deploy-content`/`--deploy-all`. Never assume cache is clear
  from a successful upload alone — SG serves stale pages aggressively.
- War story: SSL renewal on SiteGround is a manual Site Tools action, not
  scripted anywhere here. Roadie Labs (same stack) went down for an extended
  stretch on an unrenewed cert — check cert expiry before blaming code.

## 3. WordPress mu-plugin layer

Source: `wordpress/mu-plugins/` (8 files): `gg-ab.php`, `gg-cookie-consent.php`,
`gg-ga4.php`, `gg-header.php`, `gg-meta-descriptions.php`, `gg-noindex.php`,
`gg-race-ctas.php`, `gg-training-form.php`. Seven have a dedicated
`push_wordpress.py` SCP flag (`--sync-ab`, `--sync-consent`, `--sync-ga4`,
`--sync-header`, `--sync-meta-descriptions`, `--sync-noindex`, `--sync-ctas`);
`--deploy-all` includes all seven. `gg-training-form.php` has **no sync flag
anywhere in `push_wordpress.py`** and is not in `--deploy-all` — verify its
deploy path before assuming a local edit is live.

`gg-header.php` must be kept in manual sync with `shared_header.py`'s
`get_site_header_html/css/js()` — no shared source of truth between Python
and PHP. `tests/test_header_mu_plugin.py` and
`tests/test_cookie_consent_mu_plugin.py` enforce byte-level parity (covered by
plain `pytest tests/`) — run after touching either mu-plugin or its Python
counterpart.

SiteGround mu-plugin traps specific to this stack:
- `mu-plugins/` absent on fresh installs — sync functions `mkdir -p` it.
- Never `echo '<script>'` raw in a mu-plugin — SG Speed Optimizer strips raw
  `<script>` from `wp_footer`. Use `wp_enqueue_script()`.
- `is_page('slug')` can silently fail on Elementor pages — use numeric page ID
  (from body class `page-id-XXXX`).
- File Manager can drop uploads in the wrong directory — verify breadcrumb
  path after any manual upload.
- `wp-login.php` may be hidden by a security plugin — use Site Tools >
  WordPress > "Log in to Admin Panel".

## 4. Hashed-asset discipline

CLAUDE.md Known Pitfall 9: never hand-edit `gg-search.{hash}.css` /
`gg-styles.{hash}.css`. Regeneration (verified via `extract_widget_css.py
--help`): `python3 scripts/extract_widget_css.py` (`--dry-run` to preview) —
md5-hashes the CSS content for the filename, deletes stale
`gg-search.*.css` files in the same run.

## 5. Elementor questionnaire trap

Full detail in CLAUDE.md Deploy section: `/questionnaire/` is Elementor (ID
5017, widget `3f59420`) — editing repo HTML or `post_content` does nothing live.

## 6. What rollback looks like here

No backup/snapshot step exists in `push_wordpress.py`. `wordpress/output/`
(generator output) is gitignored, so it's not a rollback target itself.
Rollback = `git checkout` the prior commit of the *source* (race-data JSON,
`wordpress/*.py` generators, templates), rerun the relevant `generate_*.py`
steps to rebuild `wordpress/output/`, redeploy, purge cache. No one-command
rollback script — treat it as forward-fix from last-known-good source, not a
remote-side revert.

## When NOT to use this

- Editing race-data JSON, generators, or tests with no deploy planned — run
  the relevant `pytest` subset only.
- `athlete-custom-training-plan-pipeline` or sibling repos — this repo's
  Makefile (`draft`/`deliver`/`check-all`) is a different pipeline in the
  same checkout, not the WordPress deploy flow above.
- Local preview/dev work (`preview-*.html`, generating without pushing) — no
  SSH or cache purge needed until you're about to touch the live site.
- Roadie Labs / XC Ski Labs deploys — same stack, different host and
  mu-plugin set; use their own repos, not this file's gravelgodcycling.com
  paths (hardcoded `wp_path` in `purge_cache()`).
