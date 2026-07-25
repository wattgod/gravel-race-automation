# Road catalog migration — Phase 1 report

Completed 2026-07-24 (America/Chicago). Phase 0's 349 exact and 10 renamed
mappings, plus Matti's approved dispositions for the five parked records, were
the input. Phase 1 made no Gravel God catalog changes, no Roadie Labs site
changes, no deploys, and no pushes.

The machine-readable audit record is
[`road-migration-map.json`](road-migration-map.json). Every entry now has a
`target_verified` value and supporting `target_verification` evidence.

## Result

| Check | Mapped entries | Unique RL targets | Passed | Failed |
|---|---:|---:|---:|---:|
| Complete target pair: HTML 200 + spine marker and Markdown 200 | 359 | 353 | 358 entries / 352 targets | 1 entry / 1 target |
| HTML: HTTP 200 with `spine-v2-approved` | 359 | 353 | 359 entries / 353 targets | 0 |
| Markdown mirror: HTTP 200 | 359 | 353 | 358 entries / 352 targets | 1 entry / 1 target |

Six RL targets are intentionally shared by two GG source entries: an exact
canonical slug and one approved renamed predecessor. Each unique RL URL pair
was fetched once and the evidence was recorded on every claiming map entry.

The batch ran from `2026-07-25T02:00:40.193Z` through
`2026-07-25T02:02:38.569Z` (the evening of July 24 in America/Chicago). It used
three workers, a 400 ms delay between requests per worker, a 20-second timeout,
and up to three attempts only for network, 429, or 5xx failures.

## Verification failure

| GG source | Intended RL target | HTML | Markdown | Phase 1 disposition |
|---|---|---|---|---|
| `gfny-florida-sebring` | `gfny-florida-hardee` | HTTP 200; spine marker present | HTTP 404 | Both GG source URLs map to `https://roadielabs.com/road-races/` |

The specific GFNY redirect was removed from the actionable set. A future 301
generator must consume the map's `url_mapping` fields and therefore cannot
point either GG source URL at the incomplete target pair.

## `gfny-florida-hardee` artifact inspection

The RL profile exists at
`../road-race-automation/race-data/gfny-florida-hardee.json`. It was introduced
by RL commit `730a22d`, is present in RL `main` and its current race index, and
has seven citations. Production HTML is already live with the approved spine.
The missing artifact is the Markdown mirror.

The reproducibility gap is that the inspected canonical page-source branch,
`race-page-canonical-rollout` at `1ffc311`, contains neither the profile nor its
index row. Before generating and deploying this target as a complete pair, RL
would need to:

1. Carry the committed profile and current index state into a worktree of
   `race-page-canonical-rollout`.
2. Run the RL profile validator, citation validation, fabricated-claims audit,
   and index generation.
3. Generate the target HTML from the approved spine source into a dedicated
   staging directory, and generate
   `web/markdown/gfny-florida-hardee.md`.
4. Pass the spine/catalog audits, deploy the staged HTML (and matching
   content-hashed assets if they change) plus the Markdown mirror under the RL
   deploy gate, flush SiteGround's dynamic cache as required, and re-check both
   public URLs.

Phase 1 did not run those generators or deploy steps. Until both public URLs
pass, the map keeps the GG source on the RL hub fallback.

## Hub fallbacks and retained record

Final actionable dispositions are:

| GG slug | Reason | Destination / action |
|---|---|---|
| `chase-the-sun-norway` | Owner-confirmed fabrication quarantine | RL hub |
| `fuji-panorama-gran-fondo` | Owner-confirmed fabrication quarantine | RL hub |
| `gfny-florida-sebring` | Intended target's Markdown mirror returned 404 | RL hub |
| `gran-fondo-sibiu` | Owner-confirmed fabrication quarantine | RL hub |
| `vietnam-cycling-challenge` | Owner-confirmed fabrication quarantine | RL hub |
| `rift-valley-odyssey` | Owner-approved MTB disposition | Keep on GG; reclassify in Phase 2 |

This leaves 358 GG entries mapped to verified race-specific RL targets, five
entries mapped to the RL hub, and one entry retained on GG. There are no
`gg_only` profiles to port.

## Scope confirmation

- No RL or GG generation ran.
- No IndexNow pings were sent.
- No GG race data, pages, Markdown mirrors, or redirects changed.
- No site was deployed or cache-purged.
- Nothing was pushed.
