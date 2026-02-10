# Data Visualization Guidelines

Brand-aligned rules for how Gravel God presents data, charts, and infographics across all properties (training guide, race profiles, methodology page, social media).

## Documents

| File | Purpose |
|------|---------|
| [best-practices.md](best-practices.md) | General rules and reference for chart selection, design, accessibility, and programmatic generation |
| [visualization-inventory.md](visualization-inventory.md) | Chapter-by-chapter audit of the training guide with 28 identified visualization opportunities, prioritized |
| [brand-chart-style.md](brand-chart-style.md) | Gravel God-specific chart styling: colors, fonts, borders, layout templates |

## Quick Reference

### Chart Selection (decision tree)

```
Comparing items?          -> Horizontal bar chart
Parts of a whole?         -> Donut chart (2-5 slices max)
Trend over time?          -> Line chart
Before/after only?        -> Slopegraph
Multi-variable profile?   -> Radar chart (5-8 axes, 1-4 polygons)
Process or sequence?      -> Flowchart or timeline
Hierarchy or ranking?     -> Pyramid or funnel
Density or patterns?      -> Heatmap
Distribution?             -> Stacked bar
```

### Non-Negotiable Rules

1. **3-5 colors max** per infographic
2. **Never use color as sole encoding** — always pair with text, patterns, or position
3. **Direct labeling** over legends (label data points, not a separate key)
4. **No 3D effects, no gradient fills, no decorative gridlines**
5. **4.5:1 contrast ratio** for text, **3:1** for chart elements (WCAG)
6. **Generate at 2x**, serve at 1x + 2x via srcset
7. **WebP format** for all infographics (never JPEG — compression artifacts on text)
8. **3px solid black border** on all images (neo-brutalist brand)
9. **Sometype Mono** for all text in generated infographics

### Generation Pipeline

```
Pillow template -> 2x raw PNG -> brand border -> 1x + 2x WebP -> guide/media/
```

All templates live in `scripts/media_templates/`. Run via `python scripts/generate_guide_media.py`.
