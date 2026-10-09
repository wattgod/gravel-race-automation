# Gravel God memes

Meme illustrations for the essays: Gravel God, the site's cartoon rider, recreates a well-known meme
format's composition and plays every role in it. Matt, 2026-10-09: "I absolutely love the gravel god meme
formats."

- `PLAN.md`: why each meme went where it did, the candidates that were cut or skipped and why, and the
  design-review fixes.
- `catalog/catalog.json` and `catalog/index.html`: the format catalog (45 formats, ranked, with fit, risk
  and a hook per essay). Open `catalog/index.html` in a browser.
- `library/`: the 17 finished memes that aren't in an essay, as a 1x PNG (for social uploads) and a
  2x WebP, with a table of format, the section each was written for, caption and supporting quote.

## What is live in the essays

The final set, 2026-10-09 (Matt on the gallery of all 35: "this is fucking amazing"): 12 in Sweet
Spot, 6 in the training-app essay, in reading order. The other 17 are in `library/`.

| Essay | Meme | After the paragraph ending |
|---|---|---|
| sweet-spot-training-cycling | scooby-unmask | "…supposed to be a hack to getting faster." (*The Real Issue*) |
| | clown-ftp | "…all of their training zones are off." (*Sweet Spot is Really Threshold*, p4) |
| | spiderman-threshold | "…functionally doing is a threshold workout." (same section, p6) |
| | panik-kalm-panik | "…the real victim in all this is the athletes stoke." (*Practical Implications*, p1) |
| | four-horsemen | "…soured their relationship to the sport." (same section, p3) |
| | midwit-sweet-spot | "…more intense workouts above that intensity." (end of *It's Conceptually Broken*) |
| | same-picture | "…an on/off switch for autonomic stress." (*Your Nervous System…*, p1; the recovery chart follows p2) |
| | so-over-so-back | "…the adaptive stimulus of not-that-hard training." (*Mitochondria…*, p2) |
| | virgin-sweetspot-chad-polarized | "…systematically prevents both adaptations." (end of *The Black Hole Metaphor is Perfect*) |
| | gru-noob-gains | "…training some is called noob gains." |
| | drake-polarized | "…just noise in the middle." (end of *Polarized Training is Just Better*) |
| | gigachad-yes | "…most gravel racers race for most gravel events." (*G-Spot*, p4) |
| your-training-app-doesnt-know-your-race-exists | pov-mile-82 | "…trained him for a race that doesn't exist." (end of the opening) |
| | look-inside | "None of them models the race." (end of *First, the Part Where I Agree*) |
| | drake-fit | "…It grades on fit." (end of *Fitness Has a Shape*) |
| | starter-pack-fueling | "…doing sad math." (*A Field Guide*, the Fueling Optimist) |
| | uno-draw-25 | "…That's what it's for." (*Not to Buy Anything*, p3) |
| | pigeon-compliance | "…adapted to what?" |

Placement rules: where two memes share a section they sit at least two paragraphs apart, and no meme
sits directly next to a scene or a chart. Square and portrait memes run at the default inline width;
landscape memes run the full column (`width="column"`).

None has a caption: each meme's words are already in the image, and the alt text spells them out.

## Where the rendering code lives

Not in this repo. The memes are drawn in code on the locked v6.2 character rig in
**wattgod/dirt-craft-course** (`~/dirt-craft-course`):

- On branch `feat/essay-memes` (dirt-craft-course PR #9), four scripts in `scripts/drill_video/`:
  - `essay_memes.py`: the first nine (spiderman-threshold, panik-kalm-panik, stonks-tss,
    gru-noob-gains, drake-polarized, pigeon-compliance, drake-fit, midwit-sweet-spot,
    virgin-sweetspot-chad-polarized), plus the Anton font and its OFL licence in `fonts/`.
  - `essay_memes_batch_a.py`: bike-fall, surprised-face, two-guys-bus, uno-draw-25, waiting-skeleton,
    scooby-unmask, epic-handshake, same-picture, left-exit-12.
  - `essay_memes_batch_b.py`: clown-ftp, expectation-reality, how-it-started, pov-mile-82, nobody-me,
    tell-me-hour-six, starter-pack-fueling, they-dont-know.
  - `essay_memes_batch_c.py`: gigachad-yes, mask-cry, so-over-so-back, tier-list, clueless, x-doubt,
    four-horsemen, stop-doing, look-inside.
- `scripts/drill_video/essay_scenes.py` on branch `feat/essay-scenes`: the three Sweet Spot scenes
  (tombstone, tablet, black-hole loop). `essay_memes.py` imports its backgrounds.
- Both sit on `feat/gravel-god-drill-videos` (dirt-craft-course PR #8), which holds the rig itself.

Re-render:

```bash
cd ~/dirt-craft-course && git switch feat/essay-memes
cd scripts/drill_video
python3 essay_memes.py --out /tmp/memes                    # all nine in that script
python3 essay_memes.py --only drake-fit --out /tmp/memes   # one
python3 essay_memes_batch_b.py --only clown-ftp --out /tmp/memes   # batch scripts take the same flags
```

Each meme comes out as `<slug>.png`, `@2x.png`, `.webp`, `@2x.webp` (desktop, native aspect) and
`<slug>-m.webp`, `-m@2x.webp` (the phone layout, recomposed rather than cropped so the words stay
legible at 390 px). It needs `rsvg-convert`; the script sets `PANGOCAIRO_BACKEND=fc` so the bundled
fonts are used on macOS.

## Legal guardrails

- **Formats only.** Copy a format's composition (who stands where, how many panels) and nothing else.
  No photo, film still or original artwork is traced or used as a reference overlay.
- **No real-person likeness.** Gravel God plays every role. Never draw Drake, Spider-Man, Gru, Meme
  Man, the "Is this a pigeon?" character or any other source character, costume or logo. Don't name the
  format in on-page text or alt text.
- **Skip these formats:** This Is Fine (KC Green has objected to commercial use), Pepe (Matt Furie),
  Change My Mind (tied to one political commentator). PLAN.md and the catalog flag a few more as risky
  (Two Buttons is an artist's own comic page).
- **Words.** Captions use only claims and numbers the essay itself makes. No coach, company or product
  is named in an image; the training-app memes say "YOUR TRAINING APP".
- **Fonts.** Impact-style captions use Anton (SIL OFL), not Monotype's Impact.

## Adding a meme to an essay

1. Render it in dirt-craft-course and copy the four WebPs into
   `wordpress/articles/<essay-slug>/img/memes/`: `<slug>.webp`, `<slug>@2x.webp`, `<slug>-m.webp`,
   `<slug>-m@2x.webp`. No PNG: the `<img>` fallback is the 1x WebP.
2. Add one line to `FIGURES` in `wordpress/article_sources/<essay_module>.py`. `after` is an exact
   snippet of the body file that occurs once; the meme goes after the paragraph holding it:

   ```python
   EssayFigure(_meme("drake-fit", ALT, 1200, 1200, phone=(660, 660)), after="It grades on fit.</p>"),
   ```

   `_meme()` is `Picture.from_stem(f"img/memes/{name}", alt, w, h, ext="webp", webp=False, phone=phone)`.
   Pass `width="column"` for landscape memes so their small labels stay legible on desktop (the default
   is 440 px). Alternatively, put `<!--GG:FIGURE name-->` in the body and use `marker="name"`.
3. Regenerate: `python3 wordpress/article_sources/<essay_module>.py`, then update the meme list in
   `MEMES` (and, for Sweet Spot, the picture counts in `TestSweetSpotArticle`) in
   `tests/test_editorial_shell.py` and run
   `pytest -q tests/test_editorial_shell.py`.
4. Deploy is separate: SCP the new `img/memes/` files and `index.html` (see `docs/article-cadence.md`).
