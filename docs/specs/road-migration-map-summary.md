# Road catalog migration — Phase 0 reconciliation summary

Checkpoint artifact for Matti’s review. Migration approval was recorded on 2026-07-24. This phase made no race-data or sibling-repository changes and performed no deploys.

The machine-readable source of truth is [`road-migration-map.json`](road-migration-map.json). It contains one row and one Gravel God `.md` source mapping for each of the 364 index-selected road pages. The required Sol review is incorporated as an integrity overlay; the raw three-stage matcher remains recorded under `mechanical_counts` and on every row.

## Counts

| Class | Count | Interpretation |
|---|---:|---|
| `exact` | 349 | Same slug exists in Roadie Labs and is present in its current road index. |
| `renamed` | 10 | Explicit Roadie Labs alias/successor provenance; owner confirmation required. |
| `gg_only` | 0 | Genuine verified port candidates. None remain after integrity review. |
| `ambiguous` | 5 | Four quarantined records plus one MTB discipline conflict, all parked for Matti. |
| **Total** | **364** | `discipline == "road"` in `web/race-index.json`. |

For auditability, the literal slug → normalized name → heuristic pass produced `exact=350`, `renamed=6`, `gg_only=7`, `ambiguous=1`. The adversarial review then applied explicit same-day Roadie Labs catalog rulings: four additional canonical successors, four integrity quarantines, and one same-slug MTB exclusion.

Current checkout inventory differs from the draft spec: Gravel God has 733 total profiles/index rows (364 road); Roadie Labs has 397 profiles but only 396 indexed. A concurrent sibling session produced six race-data modifications during Phase 0. To avoid mixing mid-edit states, this map is pinned to committed Roadie Labs HEAD `e3612bb`; the excluded worktree paths are recorded in the JSON and were not changed here.

## Ambiguous — parked for Matti

| GG slug | Disposition | Evidence | Redirect / `.md` target |
|---|---|---|---|
| `chase-the-sun-norway` — Chase the Sun Norway | `quarantine` | Fabricated composite assembled from unrelated UK/Italy event details and a Norwegian touring corridor. | None selected |
| `fuji-panorama-gran-fondo` — Fuji Panorama Gran Fondo | `quarantine` | Apparently assembled/unverified; any real Fujiichi replacement requires fresh research rather than migration. | None selected |
| `gran-fondo-sibiu` — Gran Fondo Sibiu | `quarantine` | Likely fabricated or conflated with a permanent randonneuring route, not a verified gran fondo. | None selected |
| `rift-valley-odyssey` — Rift Valley Odyssey (RVO) | `keep_on_gg` | Same slug exists in Roadie Labs race-data but is excluded from its index by catalog_flags.discipline_mismatch = mtb. | Keep/reclassify on GG pending owner decision |
| `vietnam-cycling-challenge` — Vietnam Cycling Challenge | `quarantine` | No verifiable Da Lat event exists under this name; explicitly not a duplicate of another Roadie Labs profile. | None selected |

All four `quarantine` rows were deleted from Roadie Labs by catalog-pruning commit `7c16483`; their stale generated HTML/Markdown artifacts are not evidence that a target exists. `rift-valley-odyssey` still has a Roadie Labs profile and stale artifacts, but the current index excludes it as MTB.

## Gravel God only — full list

**None.** No verified Phase 1 port candidate survives the integrity overlay. The four raw no-match rows are quarantined above and must not be ported without fresh, owner-approved research.

## Renamed pairs — review required

| GG slug | Roadie Labs canonical slug | Provenance | Target artifacts | `.md` mapping |
|---|---|---|---|---|
| `gfny-florida-sebring` — GFNY Florida Sebring | `gfny-florida-hardee` — GFNY Florida Hardee | `current Roadie Labs canonical profile catalog_flags` (`730a22d`) | HTML NO; `.md` NO | `/race/gfny-florida-sebring.md` → `https://roadielabs.com/race/gfny-florida-hardee.md` |
| `gfny-la-vaujany-alpe-dhuez` — GFNY La Vaujany Alpe d'Huez | `la-vaujany` — La Vaujany Cyclosportive | `Roadie Labs pre-prune profile race-data/gfny-la-vaujany-alpe-dhuez.json` (`7c16483^`) | HTML yes; `.md` yes | `/race/gfny-la-vaujany-alpe-dhuez.md` → `https://roadielabs.com/race/la-vaujany.md` |
| `gran-fondo-nirvana-antalya` — UCI Gran Fondo World Series Antalya | `granfondo-antalya` — Granfondo Antalya | `Roadie Labs pre-prune profile race-data/gran-fondo-nirvana-antalya.json` (`7c16483^`) | HTML yes; `.md` yes | `/race/gran-fondo-nirvana-antalya.md` → `https://roadielabs.com/race/granfondo-antalya.md` |
| `granfondo-sestriere` — Granfondo Sestriere Colle delle Finestre | `marmotte-granfondo-sestriere` — Marmotte Granfondo Sestriere | `Roadie Labs pre-prune profile race-data/granfondo-sestriere.json` (`7c16483^`) | HTML yes; `.md` yes | `/race/granfondo-sestriere.md` → `https://roadielabs.com/race/marmotte-granfondo-sestriere.md` |
| `granfondo-vosges` — Granfondo Vosges | `gran-fondo-vosges` — Gran Fondo Vosges | `Roadie Labs pre-prune profile race-data/granfondo-vosges.json` (`7c16483^`) | HTML yes; `.md` yes | `/race/granfondo-vosges.md` → `https://roadielabs.com/race/gran-fondo-vosges.md` |
| `letape-piemonte` — L'Etape Piemonte | `letape-italy-piemonte` — L'Etape Italy Piemonte by Tour de France | `Roadie Labs pre-prune profile race-data/letape-piemonte.json` (`7c16483^`) | HTML yes; `.md` yes | `/race/letape-piemonte.md` → `https://roadielabs.com/race/letape-italy-piemonte.md` |
| `race-across-belgium` — Race Across Belgium | `race-across-benelux` — Race Across Benelux | `Roadie Labs pre-prune profile race-data/race-across-belgium.json` (`7c16483^`) | HTML yes; `.md` yes | `/race/race-across-belgium.md` → `https://roadielabs.com/race/race-across-benelux.md` |
| `the-majestics` — The Majestics | `gran-fondo-suisse` — Gran Fondo Suisse | `Roadie Labs pre-prune profile race-data/the-majestics.json` (`7c16483^`) | HTML yes; `.md` yes | `/race/the-majestics.md` → `https://roadielabs.com/race/gran-fondo-suisse.md` |
| `tour-down-under-community-ride` — Tour Down Under Community Ride | `adelaide-epic-ride` — Adelaide Epic Ride | `Roadie Labs pre-prune profile race-data/tour-down-under-community-ride.json` (`7c16483^`) | HTML yes; `.md` yes | `/race/tour-down-under-community-ride.md` → `https://roadielabs.com/race/adelaide-epic-ride.md` |
| `whistler-granfondo` — RBC GranFondo Whistler | `rbc-granfondo-whistler` — RBC GranFondo Whistler | `Roadie Labs pre-prune profile race-data/whistler-granfondo.json` (`7c16483^`) | HTML yes; `.md` yes | `/race/whistler-granfondo.md` → `https://roadielabs.com/race/rbc-granfondo-whistler.md` |

Nine of the ten renamed canonical targets already have local Roadie Labs HTML and Markdown artifacts. `gfny-florida-hardee` has neither and must be generated/verified in Phase 1 before any redirect can exist. Multiple GG source slugs may legitimately consolidate onto one canonical target; those claim groups are explicit in the JSON.

## Source and artifact consistency flags

- `rift-valley-odyssey`: GG index says road, GG profile says `mountain_bike`, and Roadie Labs flags `discipline_mismatch: mtb`; it is excluded from the Roadie Labs index.
- `the-majestics`: GG index says road while its GG profile says gravel; Roadie Labs explicitly identifies the road-event lineage’s canonical profile as `gran-fondo-suisse`.
- `gfny-belitung`: its GG road source `.md` and Roadie Labs target HTML are missing locally; the target Roadie Labs `.md` does exist. Both missing artifacts are recorded in the map.
- Roadie Labs has 397 race-data profiles but 396 index rows; stale generated artifacts exist for deleted profiles, so artifact presence never overrides catalog disposition.

No profiles classified `road` only inside GG `race-data/` but non-road in the generated GG index were added; the spec’s 364-page boundary is the index selection.

## Checkpoint decisions

Matti should confirm the 10 successor redirects, affirm quarantine/no-port treatment for the four rejected records, and decide whether `rift-valley-odyssey` stays on GG as MTB or is otherwise reclassified. Phase 1 should then operate only on approved `action` values; it must not assume 364 redirect pairs.
