# Gravel God memes

Meme illustrations for the essays: Gravel God, the site's cartoon rider, recreates a well-known meme
format's composition and plays every role in it. Matt, 2026-10-09: "I absolutely love the gravel god meme
formats."

- `PLAN.md`: why each meme went where it did, the candidates that were cut or skipped and why, and the
  design-review fixes.
- `catalog/catalog.json` and `catalog/index.html`: the format catalog (45 formats, ranked, with fit, risk
  and a hook per essay). Open `catalog/index.html` in a browser.

## What is live in the essays

| Essay | Meme | After the paragraph ending |
|---|---|---|
| sweet-spot-training-cycling | spiderman-threshold | "…functionally doing is a threshold workout." |
| | panik-kalm-panik | "…the real victim in all this is the athletes stoke." |
| | stonks-tss | "…it ceases to be a good metric." (Goodhart's Law) |
| | midwit-sweet-spot | "…more intense workouts above that intensity." (end of *It's Conceptually Broken*) |
| | virgin-sweetspot-chad-polarized | "…systematically prevents both adaptations." (end of *The Black Hole Metaphor is Perfect*) |
| | gru-noob-gains | "…training some is called noob gains." |
| | drake-polarized | "…just noise in the middle." (end of *Polarized Training is Just Better*) |
| your-training-app-doesnt-know-your-race-exists | pigeon-compliance | "…adapted to what?" |
| | drake-fit | "…It grades on fit." (end of *Fitness Has a Shape*) |

None has a caption: each meme's words are already in the image, and the alt text spells them out.

## Where the rendering code lives

Not in this repo. The memes are drawn in code on the locked v6.2 character rig in
**wattgod/dirt-craft-course** (`~/dirt-craft-course`):

- `scripts/drill_video/essay_memes.py` on branch `feat/essay-memes`: every meme above, plus the Anton
  font and its OFL licence in `scripts/drill_video/fonts/`.
- `scripts/drill_video/essay_scenes.py` on branch `feat/essay-scenes`: the three Sweet Spot scenes
  (tombstone, tablet, black-hole loop). `essay_memes.py` imports its backgrounds.
- Both sit on `feat/gravel-god-drill-videos` (dirt-craft-course PR #8), which holds the rig itself.

Re-render:

```bash
cd ~/dirt-craft-course && git switch feat/essay-memes
cd scripts/drill_video
python3 essay_memes.py --out /tmp/memes                    # all of them
python3 essay_memes.py --only drake-fit --out /tmp/memes   # one
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
   `MEMES` in `tests/test_editorial_shell.py` and run
   `pytest -q tests/test_editorial_shell.py`.
4. Deploy is separate: SCP the new `img/memes/` files and `index.html` (see `docs/article-cadence.md`).
