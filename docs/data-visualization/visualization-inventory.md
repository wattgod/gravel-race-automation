# Training Guide Visualization Inventory

Chapter-by-chapter audit of data visualization opportunities in the Gravel God Training Guide. Each entry identifies content that would benefit from a chart, infographic, or diagram — with recommended chart type, generation method, and priority.

**Last updated:** 2026-02-10

---

## Existing Assets (from `guide/guide-media-manifest.json`)

| ID | Ch | Type | Status |
|---|---|---|---|
| `ch1-hero` through `ch8-hero` | 1-8 | Hero photos (1920x640) | Pending (API) |
| `ch1-gear-essentials` | 1 | Gear grid infographic | Pending (API) |
| `ch1-hierarchy-of-speed` | 1 | Speed factors pyramid | Pending (API) |
| `ch2-scoring-dimensions` | 2 | 14 dimensions radar/grid | Pending (API) |
| `ch3-zone-spectrum` | 3 | 7-zone horizontal bars | **Complete** (Pillow) |
| `ch3-training-phases` | 3 | 12-week periodization timeline | **Complete** (Pillow) |
| `ch5-fueling-timeline` | 5 | Race-day fueling timeline | Pending (API) |
| `ch6-three-acts` | 6 | Three-act race structure | Pending (API) |
| `ch7-race-week-countdown` | 7 | 7-day countdown calendar | Pending (API) |

---

## Priority Tier A: Highest Impact (build first)

These are the most educational, most scannable, and most shareable visualizations. Each replaces significant prose with immediate visual understanding.

### 1. `ch3-supercompensation` — Adaptation Cycle Curve
- **Chapter:** 3 (Training Fundamentals) | **Section:** `ch3-adaptation`
- **Content:** 5-step cycle: Stress → Fatigue → Recovery → Supercompensation → Apply New Stress
- **Chart type:** Line chart showing fitness dipping below baseline (fatigue), returning (recovery), then overshooting (supercompensation)
- **Why high impact:** THE foundational concept for all training. A single clean diagram replaces an entire section of prose. Every training decision traces back to this curve.
- **Dimensions:** 1200x600 | **Generation:** Pillow-only (line/curve drawing)

### 2. `ch3-pmc-chart` — Performance Management Chart (CTL/ATL/TSB)
- **Chapter:** 3 (Training Fundamentals) | **Section:** `ch3-load`
- **Content:** CTL (42-day avg, slowly rising), ATL (7-day avg, volatile), TSB (CTL-ATL) over 12 weeks. CTL builds +3-5 pts/week, race day TSB target +15 to +25.
- **Chart type:** Dual-line chart with TSB as shaded area. The classic PMC that every cycling platform uses.
- **Why high impact:** THE chart every endurance athlete needs to understand. Beginners have never seen one; intermediates finally "get it" when they see it mapped out.
- **Dimensions:** 1600x600 | **Generation:** Pillow-only (line charts + area fill)

### 3. `ch6-psych-phases` — Psychological Phases Mood Curve
- **Chapter:** 6 (Mental Training) | **Section:** `ch6-mental-landmarks`
- **Content:** 5 predictable phases: Honeymoon (15-30%), Shattering (40-55%), Dark Patch (60-75%), Second Wind (75-85%), Late-Race Relief (85-95%)
- **Chart type:** Horizontal timeline with motivation/mood curve overlaid — dipping at Dark Patch, recovering at Second Wind
- **Why high impact:** Normalizes the Dark Patch. Every long-distance athlete recognizes these phases. This is the kind of visual people screenshot and save. Enormously reassuring for first-timers.
- **Dimensions:** 1200x600 | **Generation:** Pillow-only (line curve + labeled zones)

### 4. `ch5-bonk-math` — The Bonk Math Equation
- **Chapter:** 5 (Nutrition) | **Section:** `ch5-common-mistakes`
- **Content:** "100-mile race = 6-8 hours. At 75g carbs/hr = 450-600g total = 18-24 gels or equivalent"
- **Chart type:** Large equation-style infographic with icon grid of gel packets
- **Why high impact:** Shock value. Makes the abstract real. Changes behavior. The visual of 24 gel packets laid out is immediately memorable.
- **Dimensions:** 1200x600 | **Generation:** Pillow-only (text + rectangle grid)

### 5. `ch4-execution-gap` — Plan vs. Reality Intervals
- **Chapter:** 4 (Workout Execution) | **Section:** `ch4-gap`
- **Content:** Bad: 105%→95%→bail at 10min. Good: 300W/300W/295W/295W consistent.
- **Chart type:** Side-by-side interval power charts. LEFT = fading/abandoned intervals. RIGHT = consistent, completed intervals.
- **Why high impact:** Immediately relatable for anyone who trains with power. Reinforces the chapter's core message visually.
- **Dimensions:** 1200x600 | **Generation:** Pillow-only (paired bar charts)

### 6. `ch4-traffic-light` — Autoregulation System
- **Chapter:** 4 (Workout Execution) | **Section:** `ch4-autoregulation`
- **Content:** Green (proceed as planned), Yellow (modify intensity/volume), Red (skip or replace with recovery)
- **Chart type:** Traffic light diagram with criteria lists and prescribed actions
- **Why high impact:** Simple, memorable, referenceable during actual training. Athletes can recall "am I green, yellow, or red?" before every session.
- **Dimensions:** 1200x800 | **Generation:** Pillow-only (circles + text blocks)

### 7. `ch2-tier-distribution` — Race Tier Distribution
- **Chapter:** 2 (Race Selection) | **Section:** `ch2-tiers`
- **Content:** T1=25 races (8%), T2=73 (22%), T3=154 (47%), T4=76 (23%) out of 328 total
- **Chart type:** Horizontal stacked bar or proportional bar with tier colors (T1=#59473c, T2=#8c7568, T3=#999, T4=#ccc)
- **Why high impact:** Makes the tier system tangible. Shows the pyramid shape — most races are T3, elite T1 is rare.
- **Dimensions:** 1200x400 | **Generation:** Pillow-only (stacked rectangles)

### 8. `ch1-rider-grid` — Four Rider Categories
- **Chapter:** 1 (What Is Gravel Racing?) | **Section:** `ch1-rider-categories`
- **Content:** Ayahuasca (0-5 hrs, 150W), Finisher (5-12 hrs, 200W), Competitor (12-18 hrs, 260W), Podium (18-25+ hrs, 320W)
- **Chart type:** Horizontal comparison grid with colored segments for hours/week and FTP
- **Why high impact:** First thing readers encounter. Helps them self-identify immediately.
- **Dimensions:** 1200x600 | **Generation:** Pillow-only (grid layout)

---

## Priority Tier B: Medium Impact (build second)

### Chapter 1

#### `ch1-gear-costs` — Gear Cost Breakdown
- **Section:** `ch1-gear` | **Content:** 8 gear items, Retail vs Deal-Hunter columns, $3,500 vs $2,250 totals
- **Chart type:** Paired horizontal bar chart (retail vs deal-hunter per item)
- **Dimensions:** 1200x800 | **Generation:** Pillow-only

### Chapter 3

#### `ch3-philosophy-zones` — Training Philosophy Volume Distribution
- **Section:** `ch3-philosophies` | **Content:** Pyramidal (~80/15/5), Polarized (80/0/20), HIIT (~50/0/50), Block (varies), GOAT (hybrid)
- **Chart type:** Grouped stacked bar chart showing easy/moderate/hard distribution per philosophy
- **Dimensions:** 1200x600 | **Generation:** Pillow-only

#### `ch3-zone-triple` — Power vs HR vs RPE Alignment
- **Section:** `ch3-zones` | **Content:** 8 zones with % FTP, % HRmax, and RPE on parallel scales
- **Chart type:** Triple parallel horizontal bar segments showing alignment/misalignment across metrics
- **Dimensions:** 1200x800 | **Generation:** Pillow-only
- **Note:** Distinct from existing `ch3-zone-spectrum` which shows power only

### Chapter 4

#### `ch4-good-bad-intervals` — Consistent vs Fading Intervals
- **Section:** `ch4-rules` | **Content:** Bad: 320W/290W/270W/Failed. Good: 300W/300W/295W/295W
- **Chart type:** Two small bar charts side by side with X (bad) and checkmark (good)
- **Dimensions:** 1200x500 | **Generation:** Pillow-only

#### `ch4-zone-targets` — Zone Execution Quick Reference
- **Section:** `ch4-zones` | **Content:** Z2, G Spot, Threshold, VO2max each with target %, RPE, key cue
- **Chart type:** Horizontal comparison card grid (4 colored cards)
- **Dimensions:** 1200x500 | **Generation:** Pillow-only

### Chapter 5

#### `ch5-macro-targets` — Daily Macronutrient Targets
- **Section:** `ch5-daily` | **Content:** 70kg rider: Protein 112-154g, Carbs 140-490g, Fat 56-84g across Easy/Hard/Rest days
- **Chart type:** Grouped bar chart. Dramatic carb swing is the visual punchline.
- **Dimensions:** 1200x600 | **Generation:** Pillow-only

#### `ch5-fueling-rates` — Workout Fueling by Type
- **Section:** `ch5-fueling` | **Content:** Z2 (40-60g/hr), Tempo (60-80g/hr), Threshold (pre-workout), Race Sim (70-80g/hr)
- **Chart type:** Horizontal bar chart or gauge-style visualization
- **Dimensions:** 1200x500 | **Generation:** Pillow-only

#### `ch5-gut-training` — Gut Training Progression
- **Section:** `ch5-gut-training` | **Content:** Weeks 1-4 (40-50g/hr), 5-8 (60-70g/hr), 9-10 (70-80g/hr), Race Week (proven only)
- **Chart type:** Stepped line chart / rising staircase with filled area
- **Dimensions:** 1200x500 | **Generation:** Pillow-only

### Chapter 6

#### `ch6-mental-pyramid` — Mental Framework Layers
- **Section:** `ch6-mental-framework` | **Content:** Breathing 100%, Reframing 80%, Anchoring 60%, Acceptance 40%, Purpose 20%
- **Chart type:** Layered pyramid (foundation = Breathing, apex = Purpose)
- **Dimensions:** 1200x800 | **Generation:** Pillow-only

#### `ch6-breathing` — 6-2-7 Breathing Pattern
- **Section:** `ch6-breathing` | **Content:** Inhale 6s, Hold 2s, Exhale 7s
- **Chart type:** Waveform/sine diagram with labeled timing segments
- **Dimensions:** 1200x400 | **Generation:** Pillow-only

### Chapter 7

#### `ch7-race-morning` — Race Morning Countdown
- **Section:** `ch7-morning` | **Content:** 8 steps from "3 Hours Before" to "5 Minutes Before"
- **Chart type:** Vertical countdown timeline with clock icons and actions
- **Dimensions:** 1200x800 | **Generation:** Pillow-only
- **Note:** Zooms into race morning, distinct from `ch7-race-week-countdown` (7-day view)

#### `ch7-sleep-banking` — Sleep Banking Strategy
- **Section:** `ch7-sleep` | **Content:** Mon-Wed bank 8-9hrs, Thu-Fri maintain, Sat accept poor sleep
- **Chart type:** 7-bar chart with "banked" vs "actual" indicators, Saturday annotated
- **Dimensions:** 1200x500 | **Generation:** Pillow-only

---

## Priority Tier C: Lower Impact (build third)

### Chapter 2

#### `ch2-tier-flowchart` — "Which Tier Is Right for Me?"
- **Section:** `ch2-how-to-use` | Decision flowchart: experience level → endurance background → recommended tier range
- **Dimensions:** 1200x800 | **Generation:** Pillow-only

### Chapter 5

#### `ch5-nutrition-archetypes` — Four Failure Archetypes
- **Section:** `ch5-common-mistakes` | The Optimist, Minimalist, Experimenter, Denier as 2x2 character cards
- **Dimensions:** 1200x800 | **Generation:** Pillow (layout) + icons would benefit from AI

### Chapter 6

#### `ch6-decision-tree` — In-Race Crisis Protocol
- **Section:** `ch6-decision-tree` | Flat/Dropped/Bonking/Cramping branching flowchart
- **Dimensions:** 1200x800 | **Generation:** Pillow-only

#### `ch6-drafting` — Drafting Energy Savings
- **Section:** `ch6-group-scenario` | Solo 100% vs drafting 70-80% energy comparison
- **Dimensions:** 1200x500 | **Generation:** Pillow (bars) + rider silhouettes benefit from AI

### Chapter 8

#### `ch8-recovery-ramp` — Post-Race Recovery Timeline
- **Section:** `ch8-recovery-week` | Days 1-3 rest → Week 2 easy → Week 3 tempo → Week 4+ normal
- **Dimensions:** 1200x400 | **Generation:** Pillow-only

#### `ch8-off-season` — Off-Season Phases
- **Section:** `ch8-off-season` | Weeks 1-2 True Rest, 3-4 Ride for Fun, 5+ Rebuild Base
- **Dimensions:** 1200x400 | **Generation:** Pillow-only

#### `ch8-progression-curve` — Multi-Year Diminishing Returns
- **Section:** `ch8-progression` | Year 1 massive gains → Year 3-5 incremental → Year 5+ maintaining
- **Dimensions:** 1200x500 | **Generation:** Pillow-only (logarithmic curve)

#### `ch8-backward-timeline` — Goal-Setting Backward Planning
- **Section:** `ch8-goals` | Race Day → minus 12 weeks training → minus 4-8 weeks off-season
- **Dimensions:** 1200x400 | **Generation:** Pillow-only

#### `ch8-burnout` — Burnout Warning Dashboard
- **Section:** `ch8-burnout` | Warning signs (red), causes (arrows), prevention (green) — 3 panels
- **Dimensions:** 1200x600 | **Generation:** Pillow-only

---

## Summary

| Priority | Count | Pillow-Only | Needs API |
|---|---|---|---|
| Tier A (highest impact) | 8 | 8 | 0 |
| Tier B (medium impact) | 12 | 12 | 0 |
| Tier C (lower impact) | 9 | 7 | 2 (partial) |
| **Total new** | **29** | **27** | **2** |
| Existing (manifest) | 16 | 2 complete | 14 pending |
| **Grand total** | **45** | **29** | **16** |

All Tier A and Tier B assets (20 total) are fully Pillow-generatable with zero API cost.
