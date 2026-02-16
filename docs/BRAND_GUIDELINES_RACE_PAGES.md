# Gravel God — Race Page Brand Guidelines (Variant F)

Effective February 2026. Applies to all generated HTML across race profiles, state hubs, series hubs, and homepage.

---

## Design Philosophy

**Desert Editorial** — warm, airy, readable. Brown is an accent, not the primary. The visual hierarchy flows through typography and gold hairlines, not heavy colored blocks. Every section breathes.

**Key principle**: If a surface was previously dark-brown or near-black, it is now `warm-paper` (#f5efe6) with a colored border accent (gold or teal). Heavy double-rule borders are replaced by 1-2px hairlines.

---

## Color Palette

| Token | Hex | Role |
|---|---|---|
| dark-brown | #3a2e25 | Primary text, headlines |
| primary-brown | #59473c | Body text, editorial prose |
| secondary-brown | #7d695d | Supporting labels, metadata |
| warm-brown | #A68E80 | Tertiary text, scale labels |
| tan | #d4c5b9 | Borders (structural, subtle) |
| sand | #ede4d8 | Page background, ticker bg |
| warm-paper | #f5efe6 | Section backgrounds, hero bg, cards |
| gold | #9a7e0a | Accent borders, kickers, CTA buttons, score text |
| teal | #178079 | Secondary accent, series badges, teal section borders |
| near-black | #1a1613 | Reserved: only for "BRUTAL" difficulty label |
| white | #ffffff | Text on teal/dark surfaces only |

### Color Usage Rules

1. **Backgrounds**: Sections use `warm-paper`. Page uses `sand`. Never use dark-brown/near-black as a background.
2. **Borders**: Structural borders are `1px solid tan`. Accent borders are `1-2px solid gold` (or teal for specific sections). No `4px`, no `double`, no dark-brown borders.
3. **Text hierarchy**: Headlines in `dark-brown`, body in `primary-brown`, labels/metadata in `secondary-brown`, tertiary in `warm-brown`.
4. **Score numbers**: Always `gold` (#9a7e0a).
5. **CTAs**: Gold background with dark-brown text, or gold outline buttons.

---

## Typography

| Token | Family | Usage |
|---|---|---|
| `--gg-font-editorial` | Source Serif 4 | Headlines, scores, editorial prose, taglines |
| `--gg-font-data` | Sometype Mono | Labels, kickers, metadata, nav, buttons, stat labels |

### Type Scale

- Hero h1: 42px (28px mobile) — Source Serif 4, bold
- Hero score: 72px (48px mobile) — Source Serif 4, bold, gold
- Section titles: `--gg-font-size-md` — Source Serif 4, semibold
- Section kickers ([01], [02]): `--gg-font-size-2xs` — Sometype Mono, bold, gold
- Stat values: `--gg-font-size-xl` — Source Serif 4, bold, dark-brown
- Stat labels: `--gg-font-size-2xs` — Sometype Mono, bold, gold
- Body prose: `--gg-font-size-base` — Source Serif 4, primary-brown
- Tagline: `--gg-font-size-md` — Source Serif 4, italic, primary-brown
- Metadata/vitals: 11px — Sometype Mono, secondary-brown, uppercase, letter-spacing 1px

---

## Hero (Masthead)

The hero is a **clean editorial masthead** — no photos, no overlays, no gradients.

```
┌─────────────────────────────────────────────────────────────┐
│  TIER 2  BWR SERIES                                    72  │
│  Belgian Waffle Ride California              GG SCORE      │
│  San Marcos, CA · May 2026 · 131 mi · 10,200 ft           │
└─────────────────────────────────────────────────────────────┘
```

- Background: warm-paper
- Layout: flexbox, `align-items: flex-end`, `justify-content: space-between`
- Left: tier label → h1 → vitals line
- Right: score number (72px gold) + "GG SCORE" label
- Bottom border: 2px solid gold
- Mobile: column layout, score inline with label

**Removed from hero**: photo background, tagline (moved to overview), dual-score panel, official site button.

---

## Section Pattern

All content sections follow:

```
┌─ section.gg-section ──────────────────────────────┐
│  [01]  Section Title          ← header, gold kicker│
│─────────────────────── 1px gold ──────────────────│
│  Section content               ← body, 24px pad   │
└──────────────────────── 1px tan border ───────────┘
```

- Background: warm-paper
- Outer border: 1px solid tan
- Header: warm-paper bg, gold kicker, dark-brown title, 1px gold bottom border
- Body: 24px padding

### Section Variants

- **--dark**: Same warm-paper bg, primary-brown text (NOT dark background)
- **--accent**: Same warm-paper bg (no visual difference — legacy class)
- **--teal-accent**: 2px teal top border accent
- **Header --teal**: Teal kicker + title, teal bottom border
- **Header --gold**: Gold kicker + title, gold bottom border

---

## Cards

### Stat Cards (Course Overview)

```
┌─────────────┐
│   131 mi    │  ← Source Serif, XL, dark-brown
│  DISTANCE   │  ← Sometype Mono, 2xs, gold
└─────────────┘
```

- Background: warm-paper
- Border: 1px solid tan, hover → gold
- Text-align: center

### Race Cards (State Hubs, Homepage, Series)

Score is the hero element — large, left-aligned, editorial font:
- Score: 28-32px Source Serif 4, tier-colored
- Min-width: 72px for alignment
- Name + location below score
- No tagline in card (removed for cleanliness)
- Tier badge: outline style, not solid fill

---

## Map Embed

- iframe: `sampleGraph=true` parameter for elevation profile
- Height: 500px desktop, 350px mobile
- No `scrolling="no"` — allow full map interaction
- Container: 1px subtle border

---

## Buttons

- **Primary CTA**: `background: gold`, `color: dark-brown`, no border-radius
- **Outline**: `border: 1px solid gold`, `color: gold`, transparent bg
- **Hover**: gold bg + dark-brown text (for outline buttons)
- **Site header nav**: 2px gold bottom border on header

---

## Spacing

- Section gap: 32px margin-bottom
- Section body padding: 24px 20px
- Hero padding: 48px 32px (32px 20px mobile)
- Card padding: `--gg-spacing-md` (~16px)

---

## Border Rules

| Context | Spec |
|---|---|
| Section outer | 1px solid tan |
| Section header bottom | 1px solid gold |
| Hero bottom | 2px solid gold |
| Site header bottom | 2px solid gold |
| Stat card | 1px solid tan (hover: gold) |
| Difficulty track | 1px solid dark-brown |
| Nearby races | 1px solid tan |
| Footer top | 2px solid gold |

**Never use**: 4px borders, double borders, dark-brown borders on containers.

---

## Animations

- Difficulty gauge fill: `width 1.5s cubic-bezier(0.22,1,0.36,1)`
- Score counter: JS animates from 0 to target over 800ms
- Timeline items: fade-in + translateY on scroll
- Suffering zones: fade-in + translateX on scroll
- Accordion bars: `width 0.3s` ease
- Hover transitions: `0.2s` ease

---

## Accessibility

- All text meets WCAG AA contrast on warm-paper/sand backgrounds
- gold (#9a7e0a) on warm-paper (#f5efe6): 4.8:1 ratio (AA pass)
- dark-brown (#3a2e25) on warm-paper: 9.5:1 ratio (AAA pass)
- secondary-brown (#7d695d) on warm-paper: 3.8:1 ratio (AA for large text)
- Focus states use gold outline
- All interactive elements have visible hover/focus states

---

## Critical CSS (Inline)

The critical CSS block inlined in `<style>` before the external stylesheet must match Variant F:
- `.gg-hero`: warm-paper bg, flex layout, 2px gold border
- `.gg-site-header`: 2px solid gold bottom border

---

*Last updated: February 14, 2026*
*Applies to: generate_neo_brutalist.py, generate_state_hubs.py, generate_homepage.py, generate_series_hubs.py*
