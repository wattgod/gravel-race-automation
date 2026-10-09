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
   is how the training-app page shipped with Sweet Spot's tail and JSON-LD.
   - Body: `wordpress/article_sources/<slug>.body.html`, a run of
     `<section class="gg-blog-section">` blocks (h2 per section; references
     in `gg-blog-section gg-references`). Optional `<!--GG:IN_SHORT-->` and
     `<!--GG:LADDER-->` markers.
   - Meta + extras: `wordpress/article_sources/<slug_with_underscores>.py`
     with `META`, `render()` and `main()` (copy
     `your_training_app_doesnt_know_your_race_exists.py` for a plain essay,
     `sweet_spot_training_cycling.py` for figures + "In short").
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
4. Checks: `slop_rules.check_text` = zero issues; then
   `pytest tests/test_editorial_shell.py` (freshness, contents, ladder
   pricing, analytics). `tests/test_article_infrastructure.py` is not on
   main as of 2026-10-08.
5. Entry in `web/blog-index.json` (category "article"), regen
   `generate_articles_index.py`.
6. Commit `wordpress/articles/<slug>/` first, then deploy: SCP it to
   `public_html/articles/<slug>/` + `/articles/index.html` to gravel; flush SG cache.
7. Cross-post to Substack (manual — the essay drives subs, subs drive return
   traffic). Link the article's on-site version from the Substack footer.
8. Road cross-surface: when road's articles system exists, syndicate the
   road-relevant ones.

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
