# Quarantined Road Fabrications

Matti ruled on 2026-07-24 that these four records are fabrications and must be
deleted from Gravel God's generated catalog:

- `chase-the-sun-norway.json`
- `fuji-panorama-gran-fondo.json`
- `gran-fondo-sibiu.json`
- `vietnam-cycling-challenge.json`

They remain here only as a version-controlled evidence trail. This directory is
outside `race-data/` and must never be consumed by catalog generators.

Evidence and decision pointers:

- `docs/specs/road-migration-map.json`: the owner-approved `hub_redirect`
  dispositions and per-record `review_reasons`.
- Roadie Labs catalog-pruning commit `7c16483`: the corresponding unverified
  records were removed instead of migrated.
- Gravel God Phase 0 reconciliation commit `68b7b4ef`: records the integrity
  overlay that parked these profiles for owner review.
- Gravel God Phase 1 verification commit `ee498693`: records Matti's approval
  and verifies the live redirect-target dispositions.

Do not restore or port any of these records without new owner approval and a
fresh veracity review from primary event evidence.
