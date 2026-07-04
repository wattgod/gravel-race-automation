# Spec: Social Engine — database-driven posts, human-approved takes

**Status:** APPROVED (Matti, Jul 2026) — Phase 1 building now
**Goal:** social as a traffic channel toward the binding constraint (550
sessions/day needed for 1 plan sale/day; ~39 actual). Automate what's safe
(data in brand voice), queue what isn't (opinion), measure only what pays.

## Architecture

```
race-data/ + race-dates.json + gravel_god_rating/fondo_rating
        │
   scripts/social_engine.py  (brand-aware, both repos' data)
        │  post candidates: countdown (16w/8w window-entry, same triggers
        │  as the email system), score reveals, weekly tier rankings,
        │  riders-report quote cards (existing YouTube intel)
        ├── text renderer  → X post / Substack Note (UTM-tagged links)
        ├── card renderer  → 1080×1350 neo-brutalist PNG per brand
        │                    (brand tokens; big score, tier chip, countdown)
        └── data/social-queue/YYYY-MM-DD.json  (+ cards in social-cards/)
        │
   ┌────┴─────────┐
   AUTO-PUBLISH    APPROVAL QUEUE (opinion/takes/replies)
   (data posts)    Matti reviews ~5 drafts/day, one minute, approve/kill
```

## The automation boundary (the trust rule)

- **Fully automated:** anything where facts dominate — countdowns, scores,
  rankings, rider-intel quotes. Same principle that made the emails work:
  templates carry the voice, data carries the content, nothing to fake.
- **Human-approved only:** hot takes, replies, anything conversational.
  Automated opinion under Matti's name is the fastest way to spend the
  honest-critic trust asset. X requires automated accounts to be labeled —
  the hybrid (automated data + human takes) keeps the account authentically
  his while the volume runs itself.

## Platforms

| Platform | Write path | Notes |
|---|---|---|
| X | REST API (write NOT in hosted MCP); ~$0.015/post, ~$0.20 w/ link | Anti-spam pricing favors low-cadence honest accounts |
| X read side | **Official hosted MCP** (api.x.com/mcp, launched Jun 30 2026) | Phase 2: voice-corpus mining + race-intel DB enrichment (mirror of youtube_extract_intel) |
| Instagram | Meta Graph API (Business account + app) | Cards are the product; neo-brutalist data cards stand out in a photo feed |
| Substack Notes | No public API — browser automation via logged-in session | Feeds the platform with proven conversion |

## Cadence (dial-in starting point — council session over ~20 samples before launch)

- Daily: 1 countdown card (races entering the 16w window; 8w as fallback)
- Weekly: 1 honest-score reveal (low scores outperform raves), 1 tier-rankings carousel
- Human: takes/replies from the approval queue, whenever Matti wants

## Measurement — the metrics that matter and WHY (Morning Intel SOCIAL section)

Ranked by what actually pays, explicitly to avoid vanity-metric drift:
1. **Social-driven sessions** (GA4 channel + UTM) — the ONLY metric that
   connects to the constraint. Everything else is a leading indicator at best.
2. **Link clicks per post** — the post-level version of #1; tells which
   content formats earn the click, not just the scroll-past like.
3. **Engagement rate per post** (engagements/impressions) — quality signal
   for the voice dial-in; absolute likes/followers are explicitly IGNORED
   as success measures (they don't buy plans).
4. **Follower growth** — reported but framed as capacity, not success.
Kill criteria: if after 8 weeks social drives <10% of total sessions,
kill the channel and reinvest in articles (the proven lever).

## Phases

1. **Content engine + card renderer** (NOW): social_engine.py, per-brand
   PNG cards from brand tokens, queue JSON. No posting yet.
2. **X read-side via official MCP:** (a) race-intel enrichment pipeline —
   full-archive search per race → extract rider reports → race-data
   enrichment both brands (pattern: youtube_extract_intel.py);
   (b) voice corpus — high-engagement cycling-X posts → pattern study →
   blind-judge our drafts (the Physiqonomics method).
3. **Posting plumbing:** X API write + IG Graph + Notes browser automation;
   the approval queue; UTM discipline (utm_source=x|instagram|substack_notes).
4. **Dial-in council:** ~20 sample posts, adversarial critique + blind
   judging on voice fidelity / click-worthiness / trust preservation.

## Fonts note

Brand fonts ship as woff2 (web-only). Card renderer v1 uses system
Georgia/Courier New as stand-ins; swap in licensed TTF/OTF of Source
Serif 4 + Sometype Mono before launch (both are open fonts — download
task, not a licensing problem).
