# Prep-kit rendered-fact release gate

`scripts/prep_kit_fact_gate.py` is an offline publication check for prep-kit
HTML. It runs before `sync_prep_kits()` reads SSH credentials or stages an
upload. It compares the exact proposed files with a freshly captured live
baseline, then requires independent-review evidence for each changed rendered
race fact.

The check is deliberately not a source-research system. Existing profile
`source_review` work remains the authoring record; this packet binds its
preserved capture and independent release review to the rendered output. A
reviewer decides whether a preserved organizer capture supports a claim. The
validator checks that the decision, capture, and exact bytes are bound together;
it cannot prove that an external source is true or still current.

## Prepare a packet

Immediately before a release, capture the live prep-kit HTML into a dedicated
directory. Record the capture time and canonical live base URL. The timestamp
is freshness evidence, not proof that the public page has not changed since;
the release operator must fresh-read the live pages before publishing.

Create a JSON manifest next to preserved source captures. The proposed directory
and the `pages` array must have exactly the same `{slug}.html` inventory.
Existing pages use `captured_live` and bind their baseline hash. A page absent
from the live capture is never silently approved: use `new_page` explicitly and
review every factual field it renders.

```json
{
  "schemaVersion": "prep-kit-rendered-fact-review/v1",
  "baseline_metadata": {
    "captured_at": "2026-09-09T12:00:00Z",
    "canonical_live_base_url": "https://gravelgodcycling.com/race/"
  },
  "pages": [
    {
      "slug": "example-race",
      "baseline": {
        "kind": "captured_live",
        "sha256": "<sha256 of live-baseline/example-race.html>"
      },
      "proposed_sha256": "<sha256 of proposed/example-race.html>",
      "facts": [
        {
          "field": "distance",
          "proposed_value": "66 mi",
          "edition_or_status": "current",
          "course_variant": "Fuego XL",
          "course_pair": {"distance": "66 mi", "elevation": "7,800 ft"},
          "author": "claim author identity",
          "source": {
            "url": "https://organizer.example/course",
            "capture": "captures/example-race-course.txt",
            "sha256": "<sha256 of captures/example-race-course.txt>",
            "excerpt": "Short preserved organizer excerpt identifying the course and edition."
          },
          "independent_review": {
            "outcome": "accepted",
            "reviewer": "reviewer identity distinct from author",
            "reviewed_at": "2026-09-09T12:15:00Z"
          }
        }
      ]
    }
  ]
}
```

The allowed independent-review outcomes are `accepted` and `historical`.
`historical` also requires `edition_or_status: historical` and a
`historical_label` string that appears in the proposed page. `contradicted`, `unverified`, and
`unavailable` are not publishable outcomes. A changed distance or elevation
must identify the same course variant and paired distance/elevation values.
If a reviewed elevation is intentionally suppressed, its review must give a
`suppression_reason`.

Source captures must stay under the manifest directory. Their hash, URL, and
nonempty excerpt are mandatory; deterministic HTML/text normalization requires
the excerpt to appear in the hashed capture. The reviewer identity check is an
auditable declaration rather than authentication, and `reviewed_at` must be an
ISO-8601 timestamp with a timezone.

## Validate and publish

Run the standalone command before any deploy:

```sh
python3 scripts/prep_kit_fact_gate.py \
  --proposed-dir wordpress/output/prep-kit \
  --live-baseline-dir release/prep-kit-live-baseline \
  --manifest release/prep-kit-fact-review.json
```

The same arguments are mandatory whenever prep kits are synchronized:

```sh
python3 scripts/push_wordpress.py --sync-prep-kits \
  --prep-kit-dir wordpress/output/prep-kit \
  --prep-kit-live-baseline-dir release/prep-kit-live-baseline \
  --prep-kit-fact-manifest release/prep-kit-fact-review.json
```

CSS or layout changes with no change to the extracted factual fields require no
fact-review entries, but still require the page and byte hashes in the packet.
The gate requires the generated hero layout and extracts its name, distance,
elevation, date/status slot, and location in both current and legacy
omitted-vital forms. It also extracts labeled race-context distance, elevation,
location, conditions, signature challenge/course, race-week climate, key
challenges, and the Fueling Math distance heading. Unknown or malformed hero
markup refuses publication rather than producing an empty fact set. New factual
surfaces must extend the extractor and tests before publication; prose is not
inferred as fact by this tool.
