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
   - `id` is **public**: it is printed in the page HTML as `data-receipt-id` and in marketing exports. It must be `r-` plus three or more digits (`r-001`, `r-0042`); production builds refuse anything else. Page anchors and screenshot filenames are hashed from it.
   - `display_name` must fit the identity tier: `Firstname Lastname` (full_name), `Firstname L.` (first_last_initial), or one word (first_age_group).
   - `tags` must come from the allow-list in `wordpress/receipts_data.py` (`TAGS`); they are exported to social/email tools.
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
   - Look at the final cropped image yourself and record the date as `redaction_checked_at`. It is required, because the build can't read pixels.
   - Optional per-screenshot `withdrawn_at` / `consent_expires` remove just that screenshot.
   - The build re-encodes every screenshot from its pixels, dropping EXIF/GPS/text metadata. Production builds need Pillow for this.
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

An exchange is left out when it:

- has no `alt`, `render_approved_at` or `redaction_checked_at`;
- has its own `withdrawn_at` set, or its own `consent_expires` has passed;
- has an unknown key;
- has a missing image file;
- has no matching channel.

Entries that can't render on the channel being built (withdrawn, expired, another channel, `count_only`) are filtered out first and never content-checked, so a withdrawal always builds.

For the rest, the whole build fails when:

- an entry has a health-shaped key anywhere (`hr`, `avg_hr`, `hrv_rmssd`, `pulse`, `weight`, `wkg`, `med*`, `health`, `injury`, `diagnosis`…);
- a quote, story, transcript or tag contains a numeric health reading or body metric (weight, W/kg, HR or pulse readings, HRV, body fat).

Medical wording (meds, cardiologist, asthma, injury, surgery…) leaves just that entry, or just that screenshot, out of the build, and the build prints why. If a person has checked the wording and it isn't health data, set `health_wording_reviewed_at` on the entry; that never overrides numeric readings.

Results need an `https` `official_url`. Production builds also refuse fixture and template leftovers: ids starting `synthetic-` or `example-`, names like "Test Rider" or "Example", example.com/org links, and the template's placeholder text.

## Building with the private ledger

From `gravel-race-automation`, one line:

```
GG_BUILD=production GG_RECEIPTS_PATH=../gravel-god-training-plans/db/receipts.json python3 wordpress/generate_athletes.py
```

This writes `wordpress/output/athletes.html` and copies the approved screenshots to `wordpress/output/athletes/media/`. With `GG_BUILD=production` the build refuses to run if:

- `GG_RECEIPTS_PATH` is unset, or points at a synthetic ledger;
- any `COPY` value at the top of `generate_athletes.py` still starts with `[MATTI WRITES`. Matti writes those lines himself.

When `GG_RECEIPTS_PATH` is unset (and `GG_BUILD` isn't `production`), the build falls back to the synthetic fixture and marks the page synthetic and noindex. If `GG_RECEIPTS_PATH` is set, that ledger is used whether or not this is a production build.

`push_wordpress.py --sync-athletes` refuses to upload when any of these is true:

- the page is synthetic, still has unwritten copy, or contains fixture/template leftovers;
- a screenshot the page references is missing from `wordpress/output/athletes/media/`;
- that folder holds a file the page doesn't reference.

It purges the SiteGround cache after every upload attempt.

## Deploying and withdrawing

Deploy (manual, after the production build):

```
python3 scripts/push_wordpress.py --sync-athletes
```

`--sync-athletes` is not part of `--deploy-all`. It swaps the whole remote `athletes/media/` folder, so a screenshot dropped from the ledger is gone from the server after the next push.

To withdraw an athlete (spec §8): set `withdrawn_at`, rebuild, and run `--sync-athletes` (it purges the cache). Then do the rest of the §8 runbook (social posts, OG images, the private removal log).
