# Article Cadence — one contrarian essay per week

**Why:** "Sweet Spot Isn't That Sweet" outperformed everything else 4-to-1
(see substack-performance memory). Contrarian-training angles are the proven
traffic move, and traffic is the funnel's binding constraint. One essay a
week, cross-posted to Substack, is the growth engine.

## The runbook (per article, ~half a session)

1. Pick from the backlog below (or a fresher take — contrarian > planned).
2. Write in Matti's voice (`/voice` skill): gut-punch open, inversion-turn,
   math as weapon, ≤1 profanity, concession section ("who this ISN'T for"),
   end with weight. 1,200–1,600 words.
3. Build on the editorial shell (`wordpress/editorial_shell.py`; the module
   docstring is the contract). Don't hand-copy another article's HTML: that
   is how the training-app page shipped with Sweet Spot's tail and JSON-LD
   (removed 2026-10-08).
   - Body: `wordpress/article_sources/<slug>.body.html`, a run of
     `<section class="gg-blog-section">` blocks (h2 per section; references
     in `gg-blog-section gg-references`). Optional `<!--GG:IN_SHORT-->` and
     `<!--GG:LADDER-->` markers.
   - Meta + extras: `wordpress/article_sources/<slug_with_underscores>.py`
     with `META`, `render()` and `main()` (copy
     `your_training_app_doesnt_know_your_race_exists.py` for a plain essay,
     `sweet_spot_training_cycling.py` for figures + "In short"). The
     plain-essay template is safe to copy as of 2026-10-08: its Sweet Spot
     sections, references and FAQ JSON-LD are gone, and its Article JSON-LD
     describes that article. Still rewrite every META field and the
     `ARTICLE_LD` (headline, description, dates) for the new piece.
   - "N min read" in the hero is on by default (`ArticleMeta.show_read_time`);
     keep it on for essays.
   - Regenerate: `python3 wordpress/article_sources/<module>.py` writes
     `wordpress/articles/<slug>/index.html`. Add the module to
     `ARTICLE_SOURCES` in `tests/test_editorial_shell.py`.
   `wordpress/articles/` is the tracked, generated output; `wordpress/output/`
   is gitignored, so don't author there.
   **Regenerate every committed article** (run each module in
   `wordpress/article_sources/`) after changing any of: the shell,
   `data/pricing.json` (ladder prices), `brand_tokens` snippets (GA4, fonts,
   favicon, preload), the consent banner (`cookie_consent.py`), or the
   shared header/logo (`shared_header.py`). The articles embed all of these,
   and `test_committed_article_html_is_fresh` fails until they're rebuilt.
   The listing (`wordpress/articles/index.html`) embeds them too: rerun
   `python3 wordpress/generate_articles_index.py` as well
   (`tests/test_articles_index.py::test_committed_listing_is_fresh`).
4. Checks: `slop_rules.check_text` = zero issues; then
   `pytest tests/test_editorial_shell.py` (freshness, contents, ladder
   pricing, analytics). `tests/test_article_infrastructure.py` is not on
   main as of 2026-10-08.
5. Entry in `web/blog-index.json` (category "article", `url`
   `/articles/<slug>/`, ISO `date`), then
   `python3 wordpress/generate_articles_index.py`. The listing card reads
   its headline, dek, OG image and "N min read" from the committed essay
   page, so there's nothing else to edit; newest essay leads.
6. Commit `wordpress/articles/<slug>/` and `wordpress/articles/index.html`
   first, then deploy: SCP the essay dir to `public_html/articles/<slug>/` and
   `wordpress/articles/index.html` to `public_html/articles/index.html`;
   flush SG cache.
7. Cross-post to Substack (manual — the essay drives subs, subs drive return
   traffic). Link the article's on-site version from the Substack footer.
8. Road cross-surface: when road's articles system exists, syndicate the
   road-relevant ones.

## Imported WordPress posts (root URLs)

The 77 old Elementor blog posts move onto the same shell **at their existing
root URL**: `gravelgodcycling.com/<slug>/`. The slug never changes (no
`/articles/` prefix, no redirect).

- Convert: `python3 scripts/wp_post_import.py <post_id> [--aside "Sidebar"]`
  reads the audit inventory + snapshot (`~/specs/gg-wp-posts-2026-10-09/`),
  fetches the live page's `<head>` for metadata (never the REST API: aioseo
  canonicals are wrong for some posts), downloads originals to
  `~/.cache/gg-wp-import/`, and writes:
  - `wordpress/post_sources/<slug>.body.html` + `<slug>.json` (generated;
    re-runnable),
  - `wordpress/post_sources/<module>.py` (scaffolded once, then hand-edited:
    ALT for every image, "In short" drafts, infographics),
  - `wordpress/posts/<slug>/img/` (WebP 1x ≤1600w, @2x only when the source
    has 2x pixels, phone 660w/@2x; GIFs → muted MP4 + WebM + WebP poster;
    `<featured>-og.jpg`, the featured image as a 1200×630 JPEG ≤200 KB that
    the page uses as `og:image`; posts without a featured image keep the live
    generic one; `--no-images` backfills a missing crop),
  - `<specs>/pilot/<slug>/images.json` (per-image manifest; hand-written
    fields survive re-runs).
  Unknown Elementor widgets raise; extend the mapping in the converter.
- "In short" (Matt, 2026-10-09: "matter of fact in a claude voice"): plain,
  neutral statements of what the post says or argues, third person or
  impersonal ("The post argues that…"); no first person, no "!", no imitation
  of the author's jokes or slang, no hype. Each claim is supported by the post
  text, ≤25 words, and links to its section; 2–4 claims (≤2 under 800 words).
  `render_post` raises on the lintable half (`wp_post.in_short_problems`); the
  full rule is in the `wordpress/wp_post.py` docstring.
- Meta description: the live one, unless it's wrong; then the module passes
  `description=` (same neutral voice; e.g. Double Day 3).
- Render: `python3 wordpress/post_sources/<module>.py` writes
  `wordpress/posts/<slug>/index.html` (renderer: `wordpress/wp_post.py`).
- Check: `pytest tests/test_wp_post_import.py` (word-for-word text diff
  against the snapshot, freshness, alt text, metadata, widget mapping,
  comments). Add the post to `PILOTS` there with its fixtures in
  `tests/fixtures/wp_posts/`.
- Deploy (not automated): SCP `wordpress/posts/<slug>/` (index.html + img/)
  to `public_html/<slug>/`, then flush the SG cache. Apache serves a real
  directory's `index.html` before WordPress's rewrite runs (WP's `.htaccess`
  skips existing files and directories), so the static page wins at the
  same URL while the WP post stays in the database. Rollback = delete
  `public_html/<slug>/`. Verify with `curl -s https://gravelgodcycling.com/<slug>/ | grep gg-blog-section`.
- Comments: approved comments render as a read-only archive (no form).

## Backlog (ranked by contrarian energy × funnel relevance)

1. ~~Your Training App Doesn't Know Your Race Exists~~ — SHIPPED Jul 2 2026.
2. **You Don't Need More FTP. You Need to Stop Fading.** — durability as the
   most race-relevant, least-trained quality; why apps sacrifice long rides
   to protect "readiness"; the hour-five wattage nobody measures.
3. **The Aid Station Will Save You (It Will Not)** — the 24-gels arithmetic
   as a full essay; the four bonkers taxonomy (Optimist/Minimalist/
   Experimenter/Denier) already proven in the email sequence.
4. **Every Race Is "Epic" Until You Rate 757 of Them** — the honest-ratings
   manifesto; Scratch Ankle's 36 vs Unbound's 97; why a database that can't
   say no is a brochure. (Trust-builder; links the whole database.)
5. **Compliance Is a Vanity Metric** — 91% compliance, walked at mile 82;
   what actually predicts race-day outcomes (durability, gut training,
   pacing discipline) vs what apps celebrate.
6. **Recovery Weeks Are Where Fitness Is Manufactured** — the boring-middle
   argument; riders who skip recovery weeks plateau, every time.
7. **Zone 2 Is Having a Moment. Most of You Are Doing It Wrong Anyway.** —
   the polarized follow-up to Sweet Spot; punchable-title energy.
8. **Waiting Is Cheaper. That's the Problem.** — the per-week pricing
   paradox as public essay; base weeks are non-renewable. (Doubles as
   funnel copy — same argument as the repitch email.)

## Rules that don't bend

- No fabricated people, results, or stats. The mile-82 rider is an archetype
  composite — keep composites obviously archetypal (field-guide framing).
- Concession section is mandatory: name who shouldn't buy/believe.
- Free-first: the article must be fully useful with zero purchase.
- One CTA voice: the shell's ladder + subscribe blocks; no extra pitches.
