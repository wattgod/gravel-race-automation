# Receipts ledger: how to add an athlete

Spec: [`docs/specs/receipts-social-proof-2026.md`](specs/receipts-social-proof-2026.md) (§6.2). Field reference: [`docs/receipts-ledger-template.json`](receipts-ledger-template.json). Code: `wordpress/receipts_data.py` (loader and validator), `wordpress/receipts_components.py`, `wordpress/generate_athletes.py`.

## Where the ledger lives

Real athletes live only in the private repo:

- `gravel-god-training-plans/db/receipts.json`: the ledger (schema `gg-receipts-v2`)
- `gravel-god-training-plans/db/media/`: TrainingPeaks comment screenshots, referenced from the ledger by relative path

Never copy names, quotes, screenshots or consent records into `gravel-race-automation`; that repo is public. It holds only the code and a synthetic fixture (`tests/fixtures/receipts_synthetic.json`, "Test Rider A").

The old `db/testimonials.json` (`gg-testimonials-v1`) is a different schema. Move anything you keep into `receipts.json` entry by entry, collecting the consent fields below for each.

## Adding an athlete

1. The athlete fills in the consent form. Note the response id, identity tier, channels, assets ticked (quote, result links, screenshots) and any material connection.
2. Copy the example entry from the template into `receipts.json` and fill it in. Drop the `//` note keys if you like; the loader ignores them.
3. Send the athlete the exact quote, story text and rendered card or screenshot. Record the date they approve each:
   - `quote_approved_at`: required when there is a quote
   - `story.text_approved_at`: required when there is a story
   - `render_approved_at`: required for the athlete to render at all
   - each exchange's own `render_approved_at`
4. For each TrainingPeaks exchange:
   - Save the screenshot under `db/media/`.
   - Crop it to the comment panel. Cut metrics (heart rate, weight, power), other people, and any name the athlete's identity tier doesn't allow.
   - Type the comments word for word into `alt`, as `Speaker: words`.
   - Set `rank`; lower numbers show first.
5. Raise `coached_count` (it counts everyone coached, including people who say no) and update `coached_count_as_of`.

## Fields the build checks

An athlete is left out of the page (and the build prints why) when any of these is true:

- `consent_id` is missing
- `render_approved_at` is missing
- there is a quote or story without its approval date
- `consent_expires` has passed (consent runs 3 years)
- `withdrawn_at` is set
- the channel being built (`gravelgod` for this site) isn't in `channels`
- `identity_tier` is `count_only`, so the athlete is only counted

An exchange is left out when it has no `alt`, no `render_approved_at`, a missing image file, or no matching channel.

The whole build fails when an entry has a health field (`hr`, `hrv`, `weight`, `wkg`, `med*`…) or a quote, story or transcript that mentions weight, W/kg or heart data. Results need an `https` `official_url`.

## Building with the private ledger

From `gravel-race-automation`, one line:

```
GG_BUILD=production GG_RECEIPTS_PATH=../gravel-god-training-plans/db/receipts.json python3 wordpress/generate_athletes.py
```

This writes `wordpress/output/athletes.html` and copies the approved screenshots to `wordpress/output/athletes/media/`. With `GG_BUILD=production` the build refuses to run if:

- `GG_RECEIPTS_PATH` is unset, or points at a synthetic ledger;
- any `COPY` value at the top of `generate_athletes.py` still starts with `[MATTI WRITES`. Matti writes those lines himself.

Without `GG_BUILD=production` the build falls back to the synthetic fixture and marks the page synthetic and noindex. `push_wordpress.py --sync-athletes` refuses to upload a synthetic page or one with unwritten copy.

## Deploying and withdrawing

Deploy (manual, after the production build):

```
python3 scripts/push_wordpress.py --sync-athletes --purge-cache
```

`--sync-athletes` is not part of `--deploy-all`. It swaps the whole remote `athletes/media/` folder, so a screenshot dropped from the ledger is gone from the server after the next push.

To withdraw an athlete (spec §8): set `withdrawn_at`, rebuild, run `--sync-athletes`, and purge the cache. Then do the rest of the §8 runbook (social posts, OG images, the private removal log).
