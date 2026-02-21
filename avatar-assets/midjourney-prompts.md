# Midjourney Prompts — Gravel God Avatar

## Character Design Decisions

- **Style**: Pure South Park construction paper cutout
- **Build**: Stocky dad-bod
- **Outfit**: Casual gravel — baggy MTB shorts over bibs, flannel over worn cycling jersey
- **Sunglasses**: Pit Viper retro
- **Facial hair**: Thick handlebar mustache
- **Expression default**: Deadpan
- **Voice match**: Dry, droll, data-obsessed (see `gravel-voice-reference.md`)

---

## Step 1: Hero Reference (Run First)

Generate 4 variations. Pick the one with the most personality and clearest South Park geometry. Upscale it. Use that upscaled URL as `--cref` for all Step 2 poses.

```
South Park style flat cartoon character, construction paper cutout aesthetic,
stocky dad-bod build, thick handlebar mustache, Pit Viper retro sunglasses,
baggy mountain bike shorts over cycling bibs, flannel shirt unbuttoned over
a worn cycling jersey, cycling gloves, gravel dust on clothes, standing pose
facing camera, arms crossed, deadpan expression, solid color background,
full body, clean lines, no shading, flat colors --ar 1:1 --s 50 --no 3d
realistic shading gradient shadow photorealistic
```

### Fallback variants (if the above drifts too realistic)

Add `--style raw` to force simpler output:

```
South Park style flat cartoon character, construction paper cutout aesthetic,
stocky dad-bod build, thick handlebar mustache, Pit Viper retro sunglasses,
baggy mountain bike shorts over cycling bibs, flannel shirt unbuttoned over
a worn cycling jersey, cycling gloves, gravel dust on clothes, standing pose
facing camera, arms crossed, deadpan expression, solid color background,
full body, clean lines, no shading, flat colors --ar 1:1 --s 50 --style raw
--no 3d realistic shading gradient shadow photorealistic
```

If flannel reads wrong, swap to hoodie:

```
South Park style flat cartoon character, construction paper cutout aesthetic,
stocky dad-bod build, thick handlebar mustache, Pit Viper retro sunglasses,
baggy mountain bike shorts over cycling bibs, unzipped hoodie over a worn
cycling jersey, cycling gloves, gravel dust on clothes, standing pose facing
camera, arms crossed, deadpan expression, solid color background, full body,
clean lines, no shading, flat colors --ar 1:1 --s 50 --no 3d realistic
shading gradient shadow photorealistic
```

---

## Step 2: Pose Library

Replace `[URL]` with the upscaled hero image URL. `--cw 100` = maximum character consistency.

All 16 poses match the `avatar_assets_needed` field in video briefs.

```
South Park style flat cartoon character, same character, excited reaction pose, arms raised, mouth open, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, facepalm pose, hand covering face in disappointment, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, mind blown pose, hands on sides of head, shocked expression, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, mustache twirl pose, one hand twisting mustache tip, smug expression, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, pointing at camera pose, one arm extended pointing forward, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, presenting pose, one arm extended to the side palm up, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, skeptical pose, arms crossed, one eyebrow raised, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, suffering pose, hunched over bicycle handlebars in pain, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, thinking pose, hand on chin looking upward, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, thumbs up pose, one arm extended with thumb up, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, boxing versus stance, fists up ready to fight, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, dramatic pose, leaning forward intensely, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, counting on fingers pose, holding up fingers, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, shrug pose, palms up shoulders raised, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, leaning in conspiratorial pose, hunched forward like sharing a secret, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow

South Park style flat cartoon character, same character, mic drop pose, one arm extended downward dropping microphone, construction paper cutout, flat colors, no shading, solid color background, full body --cref [URL] --cw 100 --ar 1:1 --s 50 --no 3d realistic shading gradient shadow
```

---

## Step 3: Background Removal

Midjourney cannot produce true transparency. After generating each pose:

1. Use [remove.bg](https://www.remove.bg/) or Photoshop to remove background
2. Export as transparent PNG
3. Save to `avatar-assets/` with naming convention: `{pose}.png`

### File naming convention

```
avatar-assets/
├── excited.png
├── facepalm.png
├── mind_blown.png
├── mustache_twirl.png
├── pointing.png
├── presenting.png
├── skeptical.png
├── suffering.png
├── thinking.png
├── thumbs_up.png
├── versus.png
├── dramatic.png
├── counting.png
├── shrug.png
├── leaning_in.png
├── mic_drop.png
└── hero_reference.png      ← the original locked design
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Too realistic / 3D shading | Add `--style raw` and strengthen `--no` list |
| Character looks different across poses | Increase `--cw` to 100, use the exact same `--cref` URL |
| Flannel looks wrong | Try "unzipped hoodie over cycling jersey" |
| Pit Vipers not reading as retro | Try "oversized retro sport sunglasses, colorful mirrored lenses" |
| Mustache too small | Add "prominent thick handlebar mustache" |
| Too skinny | Emphasize "stocky build, broad shoulders, thick torso" |
| Background not solid | Add "isolated on solid [color] background" |

---

## Notes

- **Cost**: Midjourney Standard ($30/mo) covers hero + all 16 poses in one session
- **Consistency**: `--cref` + `--cw 100` is the key to same-character across poses
- **Brand alignment**: Character uses Gravel God brand colors where possible (brown `#59473c`, teal `#178079`) but South Park style takes priority over exact brand matching
- **Video briefs reference**: Every brief's `avatar_assets_needed` array lists exactly which poses that video requires
