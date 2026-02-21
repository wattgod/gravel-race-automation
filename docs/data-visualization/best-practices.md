# Data Visualization Best Practices

General rules and reference points for presenting data and information across Gravel God properties. Based on research from Tufte, Knaflic (Storytelling with Data), Evergreen, NNGroup, and current industry standards (2024-2026).

---

## 1. Chart Type Selection

### When to Use What

| Data Pattern | Best Chart Type | Notes |
|---|---|---|
| Comparing items side by side | **Horizontal bar chart** | The workhorse. Default starting point for most data. Vertical bars only for time-based x-axis. |
| Parts of a whole | **Donut or waffle chart** | 2-5 slices max. Waffle charts are more perceptually accurate than pie. Never use pie with 6+ slices. |
| Composition across categories | **Stacked bar chart** | Better than pie for comparing composition across multiple groups. |
| Trends over time (7+ points) | **Line chart** | Standard for time series. Use for continuous data. |
| Before/after (2 points) | **Slopegraph** | Specifically recommended by Knaflic for two-timepoint comparisons. |
| Multi-variable profile | **Radar/spider chart** | 5-8 normalized axes max. 1-4 overlapping polygons max. All variables must be on the same scale. |
| Process or sequence | **Flowchart or timeline** | Directional cues (arrows, numbers). S-shaped layouts conserve vertical space. |
| Hierarchy or ranking | **Pyramid or funnel** | Natural narrowing. Good for "importance" rankings. |
| Density or patterns | **Heatmap** | Many variables across many categories. Good for training schedules, weekly loads. |
| Ranking changes over time | **Bump chart** | Shows position shifts. Recommended by Evergreen. |
| Relationships (2 variables) | **Scatter plot** | Add trend lines for clarity. Keep to 5-7 bubbles if using bubble variant. |

### Infographic Format Selection

| Format | Best For | Example |
|---|---|---|
| Timeline | Chronological sequences, milestones | Race week countdown, periodization phases |
| Process | Step-by-step procedures | Bike maintenance checklist, warm-up protocol |
| Comparison | Pros/cons, A vs B | Rider categories, training philosophies |
| Data visualization | Statistics, research findings | Tier distribution, zone charts |
| List | Tips, rankings, checklists | Gear essentials, race-day bag |
| Flowchart | Decision trees, workflows | "Which tier for me?", in-race crisis protocol |

---

## 2. Design Principles

### Data-Ink Ratio (Tufte)

Maximize the proportion of ink (pixels) that conveys actual data. Every non-data element must justify its existence.

- **Eliminate chartjunk**: No decorative gridlines, no 3D effects, no gradient fills, no background images that add no information
- **Reduce non-data ink**: Lighten or remove gridlines, reduce tick marks, simplify axes
- **Direct labeling**: Label data points directly rather than using legends. Reduces eye movement and cognitive load. Strongly endorsed by both Evergreen and Knaflic.

**Nuance** (Elavsky, 2025): Tufte's minimalism taken to extremes can harm accessibility. Some "redundant" visual cues (borders, patterns, labels) serve important accessibility functions. Err on the side of clarity over minimalism.

### Color Usage

- **3-5 colors maximum** in any single infographic
- **Human eye processes 5-7 colors pre-attentively** — qualitative scales work best with 3-5 categories
- **Never use color as sole encoding** — always pair with text labels, patterns, icons, or position. 8% of men have red-green color blindness.
- **Reserve bright/saturated colors for emphasis**; use neutral grays for context
- **Complementary pairs** (blue/orange, purple/yellow) for natural contrast
- **Dark backgrounds expand accessible palettes** — 61 compliant shades on dark vs 40 on white (Google Material analysis)

### Engagement Statistics

- Infographics are **shared 300% more** than text-only articles
- Colored infographics boost **attention and comprehension by 82%**
- Colored infographics are **39% more memorable** than grayscale
- Reading equivalent info: **<2 min** (infographic) vs **5-8 min** (text)
- **40% of viewers abandon** pages with confusing or visually taxing graphics
- Original graphics are the **#1 visual content type** used by marketers (36%, HubSpot 2025)

### Typography in Charts

- Use readable, scalable typefaces. Avoid script and decorative fonts.
- Use varied font sizes for hierarchy: title > subtitle > body > annotation
- Bold typography for impact on key numbers and labels
- Ensure text is legible at mobile sizes (minimum ~11px rendered)

### Whitespace and Layout

- More whitespace = improved readability (2025 trend)
- Establish clear visual hierarchy through size, color, position, contrast
- Guide the reader's eye through intended sequence
- Group related info with borders, boxes, or background colors
- Number sections to aid comprehension

---

## 3. Accessibility (WCAG)

### Contrast Requirements

| Element | Minimum Ratio | Standard |
|---|---|---|
| Regular text (<18px) | 4.5:1 | WCAG AA |
| Large text (18px+) | 3:1 | WCAG AA |
| Chart elements (bars, lines, nodes) | 3:1 with neighbors | WCAG 1.4.11 |

### Dual Encoding

Never rely on color alone. Always use at least one additional encoding:
- Text labels on/near data points
- Patterns or hatching (stripes, dots)
- Icons or shapes
- Position/size differences
- Border styles

### Other Requirements

- Avoid red-green combinations as primary distinguishing colors
- Provide meaningful alt text for all images in HTML
- Test at 200% zoom for readability
- Ensure all chart text is actual text (not rasterized at unreadable sizes)

---

## 4. Sports/Fitness-Specific Guidelines

### Training Zone Charts

- **Most common visualization** in endurance sports content
- **Established color conventions**: Z1=blue/gray (easy) → Z2=blue/green (aerobic) → Z3=green/yellow (tempo) → Z4=orange (threshold) → Z5=red (VO2max)
- Always label both percentage ranges AND physiological purpose
- Our brand adaptation: teal (easy) → gold (threshold) → brown (max) to stay on-brand

### Radar Charts for Race/Athlete Profiling

- Ideal for our 15-criteria scoring system (1-5 normalized scale)
- Place related attributes on adjacent axes (group difficulty metrics, group community metrics)
- Limit to 4-5 overlapping polygons maximum
- For single-entity profiles: one filled polygon against a "tier average" reference outline
- Used extensively in sports analytics (PFF soccer, cycling power profiles)

### Periodization Timelines

- Block periodization diagrams are standard for showing training phases
- Gantt-chart style with distinct color blocks per phase
- Include volume/intensity indicators and milestone markers

### Nutrition Visualizations

- Timeline infographics for pre/during/post fueling protocols
- Equation-style infographics for "shock value" calorie/carb math
- Checklist infographics for race-day nutrition plans

---

## 5. Programmatic Generation (Pillow)

### What Works Well

| Visualization | Difficulty | Notes |
|---|---|---|
| Bar charts (horizontal/vertical) | Easy | Rectangles + text labels |
| Stacked bars | Easy | Layered rectangles |
| Line charts | Medium | `ImageDraw.line()` or polygon fill for areas |
| Radar/spider charts | Medium | Trigonometric polygon vertices with `ImageDraw.polygon()` |
| Timelines | Easy | Rectangles + connecting lines + text |
| Pyramids/funnels | Easy | Centered trapezoids stacked vertically |
| Heatmaps | Easy | Grid of colored rectangles |
| Flowcharts | Medium | Boxes + arrows + text routing |
| Donut charts | Medium | Arc drawing with `ImageDraw.arc()` or `pieslice()` |
| Comparison grids | Easy | Table-like layout with colored cells |

### What Doesn't Work Well

- Complex illustrations, characters, organic shapes
- Curved text paths (no native Pillow support)
- Gradient fills under curves (must simulate with pixel manipulation)
- Sophisticated typography (kerning, ligatures, variable fonts)
- Interactive elements (static output only)

### Technical Best Practices

1. **Ship fonts with the project** — load with `ImageFont.truetype('path/to/font.ttf', size)`. Never rely on OS fonts.
2. **Use `textbbox()` or `textlength()`** to measure text before placing. Enables dynamic centering and wrapping.
3. **Generate at 2x resolution** — anti-aliased text looks clean when downsampled.
4. **Define a box model** — anchors (top-left, center, baseline), margins, padding. Most layout bugs are positioning bugs.
5. **PNG for raw output** — text and solid colors get JPEG artifacts. Convert to WebP at final output.
6. **All colors as hex constants** in one place. Use the brand palette from `base.py`.
7. **Matplotlib + Pillow hybrid** for complex charts: render Matplotlib to `BytesIO`, paste onto Pillow canvas.

### Architecture

```
1. Define template (canvas size, background color, content zones)
2. Load brand assets (fonts, colors from base.py)
3. For each data record:
   a. Create Pillow Image canvas at 2x dimensions
   b. Draw background elements (rectangles, lines, section headers)
   c. Render data visualizations (bars, lines, polygons)
   d. Render text (titles, labels, values, captions)
   e. Apply brand border (3px solid black)
   f. Resize to 1x + 2x
   g. Save as WebP
```

---

## 6. Common Mistakes to Avoid

### Data Integrity

1. **Manipulating axes** — Always start y-axis at zero for bar charts. Line charts can use non-zero baselines if clearly labeled.
2. **Cherry-picking data** — Show full context or clearly label truncation.
3. **Mislabeling** — Wrong units, swapped labels, unclear axis names destroy trust instantly.
4. **3D effects** — Distort perception. Angles and perspective make some sections look larger. **Always use 2D.**

### Design

5. **Too many colors** — Stick to 3-5 meaningful colors. Use gray for everything else.
6. **Overloading** — Split into multiple focused charts rather than one overwhelming one.
7. **Wrong chart type** — Pie charts for 15 categories, line charts for categorical data. Function over form.
8. **Cluttering with text** — Use callouts sparingly. Let the data speak.
9. **No context or narrative** — Every infographic should answer "so what?"

### Production

10. **Poor mobile rendering** — Test at 375px width minimum. Vertical formats outperform wide horizontal on phones.
11. **No source attribution** — Cite data sources. Builds credibility.
12. **Color-only encoding** — Inaccessible to colorblind users. Always dual-encode.
13. **Over-relying on metaphors** — Visual puns that overshadow actual data (NNGroup warning).
14. **Copy as afterthought** — Text in infographics should be concise, scannable, carefully written.

---

## Sources

- Tufte, E. — *The Visual Display of Quantitative Information*
- Knaflic, C.N. — *Storytelling with Data* (storytellingwithdata.com)
- Evergreen, S. — *Effective Data Visualization* (2025 edition)
- Elavsky, F. — "Minimalism and the Data-to-Ink Ratio" (2025)
- NNGroup — "Designing Effective Infographics", "Choosing Chart Types"
- Smashing Magazine — "Accessibility Standards Empower Better Chart Design" (2024)
- HubSpot — "Types of Charts and Graphs", "Visual Content Marketing Statistics" (2025)
- Piktochart — "The 10 Types of Infographics"
- Datawrapper — "A Friendly Guide to Choosing a Chart Type"
- Highcharts — "Radar Chart Explained" (2024)
- WebFX — "Visual Content Statistics" (2026)
- DemandSage — "Infographic Statistics" (2026)
- WCAG 2.1 — Non-Text Contrast SC 1.4.11
