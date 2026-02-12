# Gravel God Chart Style Guide

Specific styling rules for all data visualizations generated for Gravel God properties. These rules build on the general best practices and adapt them to the neo-brutalist brand.

---

## Color Palette for Charts

### Primary Data Colors

Use these for main data elements (bars, lines, fills, polygons):

| Color | Hex | Usage |
|---|---|---|
| Primary Brown | `#59473c` | Default bar fill, T1 elements, primary data series |
| Secondary Brown | `#7d695d` | Secondary data series, T2 elements, hover/active states |
| Dark Teal | `#178079` | Accent/highlight, positive indicators, high scores |
| Teal | `#4ECDC4` | Lighter accent, secondary highlight |
| Dark Gold | `#9a7e0a` | Warning/threshold indicators, mid-range scores |
| Gold | `#F4D03F` | Lighter warning, secondary mid-range |

### Background and Structure Colors

| Color | Hex | Usage |
|---|---|---|
| Off-White | `#f5f0eb` | Chart background, card backgrounds |
| White | `#FFFFFF` | Canvas background (infographic overall) |
| Muted Tan | `#c4b5ab` | Axis labels, secondary text, gridlines (if needed) |
| Cream | `#d4c5b9` | Section dividers, subtle separators |
| Black | `#000000` | Borders, primary text, axis lines |

### Tier Colors (for race-related charts)

| Tier | Hex | Label |
|---|---|---|
| T1 | `#59473c` | Elite |
| T2 | `#7d695d` | Strong |
| T3 | `#766a5e` | Solid |
| T4 | `#5e6868` | Entry |

### Training Zone Colors (for fitness charts)

Adapted from standard endurance sport conventions to stay on-brand:

| Zone | Hex | Name |
|---|---|---|
| Z1 Active Recovery | `#4ECDC4` | Teal (easy) |
| Z2 Endurance | `#178079` | Dark Teal (aerobic) |
| Z3 Tempo | `#9a7e0a` | Dark Gold (moderate) |
| G Spot (Race Pace) | `#F4D03F` | Gold (threshold approach) |
| Z4 Lactate Threshold | `#c4713a` | Burnt Orange (hard) |
| Z5 VO2max | `#7d695d` | Secondary Brown (very hard) |
| Z6 Anaerobic | `#59473c` | Primary Brown (max) |
| Z7 Neuromuscular | `#2d2420` | Near-Black (sprint) |

### Status/Indicator Colors

| State | Hex | Usage |
|---|---|---|
| Good/Go | `#178079` | Green light, positive, correct |
| Caution | `#F4D03F` | Yellow light, warning, modify |
| Stop/Bad | `#c0392b` | Red light, danger, incorrect |
| Neutral | `#766a5e` | Disabled, inactive, N/A |

---

## Typography

### Font

**Sometype Mono** — used for ALL text in generated infographics.

| Weight | File | Usage |
|---|---|---|
| Regular (400) | `guide/fonts/SometypeMono-Regular.ttf` | Body text, labels, captions, axis labels |
| Bold (700) | `guide/fonts/SometypeMono-Bold.ttf` | Titles, key numbers, emphasis, section headers |

### Font Sizes (at 2x canvas resolution)

| Element | Size | Weight |
|---|---|---|
| Main title | 48-56px | Bold |
| Section header | 36-40px | Bold |
| Key number / stat | 60-80px | Bold |
| Body label | 24-28px | Regular |
| Axis label | 20-24px | Regular |
| Caption / source | 18-20px | Regular |
| Annotation | 16-18px | Regular |

These are at 2x canvas size. Final 1x output will be half these values.

### Text Colors

| Context | Color |
|---|---|
| On white/off-white background | `#000000` (black) |
| On dark background (brown, teal) | `#f5f0eb` (off-white) or `#FFFFFF` |
| Secondary/de-emphasized | `#7d695d` (secondary brown) |
| Caption / source attribution | `#c4b5ab` (muted tan) |

---

## Borders and Structure

### Neo-Brutalist Rules

All Gravel God visualizations follow the neo-brutalist aesthetic:

- **No border-radius** — all corners are sharp 90-degree angles
- **No box-shadow** — flat design only
- **No gradient fills** — solid colors only
- **3px solid black border** on the outer edge of every infographic
- **2-3px solid black borders** on internal section dividers where needed
- **No decorative elements** that don't convey data

### Internal Structure

- Use **solid black lines** (2px at 2x) for axis lines and section dividers
- Use **dashed lines** (1px at 2x, pattern 8,4) for reference lines and gridlines (sparingly)
- Bars and data elements should have **1px black stroke** at 2x for definition against backgrounds

---

## Layout Templates

### Standard Infographic (1200x600 @ 2x = 2400x1200 canvas)

```
┌─────────────────────────────────────────────┐
│  TITLE (48px bold, black, top-left)         │ ← 60px top padding
│  Subtitle (24px regular, #7d695d)           │ ← 20px gap
├─────────────────────────────────────────────┤ ← 40px gap
│                                             │
│              [CHART AREA]                   │ ← Main content zone
│              (flexible height)              │
│                                             │
├─────────────────────────────────────────────┤ ← 30px gap
│  Source: gravelgodcycling.com  (18px, tan)  │ ← 40px bottom padding
└─────────────────────────────────────────────┘
  ↑ 60px left padding            60px right ↑
```

### Full-Width Infographic (1600x500 @ 2x = 3200x1000 canvas)

Same structure, wider canvas. Used for timelines and periodization charts.

### Tall Infographic (1200x800 @ 2x = 2400x1600 canvas)

Used for flowcharts, checklists, multi-section layouts.

### Padding Constants

| Element | Value (at 2x) |
|---|---|
| Outer padding (all sides) | 60px |
| Title to chart gap | 40px |
| Chart to footer gap | 30px |
| Bar spacing (between bars) | 16px |
| Section gap (between chart sections) | 40px |
| Label to data element gap | 12px |

---

## Bar Chart Specifications

### Horizontal Bars

- Bar height: 40-48px at 2x
- Bar spacing: 16px at 2x
- Bar fill: solid brand color (no gradient)
- Bar stroke: 1px black at 2x (optional, use when bars are on colored background)
- Label: left-aligned, vertically centered with bar, 24px regular
- Value: right-aligned inside or outside bar, 24px bold

### Vertical Bars

- Bar width: 48-64px at 2x
- Bar spacing: 16-24px at 2x
- Same fill/stroke rules as horizontal

### Stacked Bars

- No gap between segments
- 1px black stroke between segments for definition
- Legend or direct labels on each segment

---

## Line Chart Specifications

- Line width: 4px at 2x for primary series, 3px for secondary
- Data points: 8px diameter circles at key points (optional — only on sparse data)
- Fill area: 20% opacity of line color for area charts
- Axis lines: 2px solid black
- Grid lines: 1px dashed `#c4b5ab` (use sparingly — max 4-5 horizontal)

---

## Radar Chart Specifications

- Axes: 2px solid black lines from center to perimeter
- Grid rings: 1px dashed `#c4b5ab`
- Polygon fill: 30% opacity of brand color
- Polygon stroke: 3px solid brand color
- Axis labels: 24px regular, positioned outside the outermost ring
- Reference polygon (e.g., tier average): 2px dashed `#766a5e`, 10% fill

---

## Source Attribution

Every generated infographic includes a source line in the bottom-left:

```
gravelgodcycling.com
```

- Font: Sometype Mono Regular, 18px at 2x
- Color: `#c4b5ab` (muted tan)
- Position: 60px from left, 40px from bottom

---

## File Naming Convention

```
{chapter}-{descriptive-id}-{resolution}.webp
```

Examples:
- `ch3-supercompensation-1x.webp`
- `ch3-supercompensation-2x.webp`
- `ch4-execution-gap-1x.webp`
- `ch6-psych-phases-2x.webp`

---

## Checklist: Before Publishing Any Infographic

- [ ] Uses only Sometype Mono font
- [ ] 3-5 colors max from brand palette
- [ ] 3px solid black outer border
- [ ] No border-radius, no box-shadow, no gradients
- [ ] Text contrast meets 4.5:1 (regular) or 3:1 (large)
- [ ] Color is not the sole encoding — text/patterns/position also used
- [ ] Direct labeling (no separate legend unless unavoidable)
- [ ] Source attribution present
- [ ] Looks correct at both 1x and 2x
- [ ] Title clearly states what the chart shows
- [ ] Alt text written for HTML embedding
