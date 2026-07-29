# SEO CTR pass — 2026-07-29

Source: `data/gsc-snapshots/2026-07-29.json`, covering 2026-07-23 through
2026-07-29.

## Selection baseline

This pass uses a deliberately simple expected organic CTR curve, rounded to
the nearest whole-number average position:

| Position | Expected CTR |
|---|---:|
| 1–3 | 10.0% |
| 4–5 | 7.0% |
| 6 | 5.0% |
| 7 | 4.0% |
| 8 | 3.5% |
| 9 | 3.0% |
| 10 | 2.5% |
| 11–20 | 1.5% |

A page qualifies when it has at least 80 impressions and observed CTR is
strictly below 60% of the baseline. This keeps the selection rule reproducible
without pretending that the small seven-day sample supports a more precise
curve.

The qualifying snapshot URLs were:

| URL | Impressions | CTR | Position | 60% threshold | Disposition |
|---|---:|---:|---:|---:|---|
| `/race/northcape-4000/` | 524 | 1.1% | 8.2 | 2.1% | Changed |
| `/race/rebeccas-private-idaho/` | 235 | 2.1% | 6.0 | 3.0% | Changed |
| `/race/race-across-america/` | 324 | 1.2% | 9.4 | 1.8% | No GG metadata change; migrated to Roadie Labs |
| `/race/assault-on-mt-mitchell/` | 124 | 1.6% | 7.8 | 2.1% | No GG metadata change; migrated to Roadie Labs |
| `/race/ride-across-indiana/` | 108 | 1.9% | 7.8 | 2.1% | No GG metadata change; migrated to Roadie Labs |

The migrated pages were removed from the active Gravel God catalog on
2026-07-24 and are covered by the canonical Roadie Labs migration map. Their
archived JSON is not a live generator input, so editing it here would not alter
the search result.

Notable pages that clear the 80-impression floor but do **not** fall below the
selection threshold include `/articles/sweet-spot-training-cycling/` (266
impressions, 2.6% CTR, position 8.7, 1.8% threshold), `/race/crooked-gravel/`
(183, 2.7%, 8.2, 2.1%), and `/race/little-apple-100/` (84, 2.4%, 6.9, 2.4%;
the rule is strictly below).

## Metadata changes

All values below are emitted from `race-data/{slug}.json` through
`wordpress/generate_neo_brutalist.py`. Titles are capped at 60 characters and
descriptions at 155 characters by the generator.

### `/race/northcape-4000/`

- Evidence: 524 impressions, 6 clicks, 1.1% CTR, average position 8.2.
- Before title (48): `NorthCape 4000 Review 2026 | Norway | Gravel God`
- After title (49): `NorthCape 4000: Route, Difficulty & 27-Day Cutoff`
- Before description (64): `Rated 77/100 (Contender). Course maps, ratings & full breakdown.`
- After description (138): `NorthCape 4000 route analysis: 2,485 miles, 98,000 feet, 8 countries, and a 27-day cutoff. See the difficulty rating and course breakdown.`

### `/race/rebeccas-private-idaho/`

- Evidence: 235 impressions, 5 clicks, 2.1% CTR, average position 6.0.
- Before title (56): `Rebecca's Private Idaho Review 2026 | Idaho | Gravel God`
- After title (51): `Rebecca's Private Idaho: Course, Tires & Difficulty`
- Before description (155): `Idaho's most beautiful gravel race. 100 miles through the Pioneer Mountains. Rated 80/100 (Elite) in Ketchum, Idaho. Course maps, ratings & full breakdown.`
- After description (138): `Rebecca's Private Idaho course analysis: 104 miles, 6,860 feet, Corral Creek Summit, difficulty rating, tire picks, and training guidance.`

The differentiated promises are present on each page: NorthCape has the route,
distance, elevation, country count, cutoff, and rated course breakdown;
Rebecca's Private Idaho has the 104-mile course, elevation, Corral Creek
analysis, rating, tire recommendations, and training section.

## Measurement and release gate

Watch these affected URLs in the existing daily `gsc-snapshots` output:

- `/race/northcape-4000/`
- `/race/rebeccas-private-idaho/`

Compare a seven-day window after roughly 14 days with the 2026-07-23 through
2026-07-29 baseline above. Read CTR together with average position and
impressions; do not attribute a raw CTR move to copy if ranking or query mix
shifted materially.

Deployment remains gated on Matt's review of title voice. This change must not
be deployed before that review.
