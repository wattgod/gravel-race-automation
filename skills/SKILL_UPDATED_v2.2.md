# Gravel Race Landing Page Builder v2.2

## Purpose
Generate component-based race landing pages for Gravel God Cycling optimized for WordPress/Elementor. This skill creates **individual sections** that can be assembled in Elementor, avoiding massive single-file HTML generation and timeout issues.

## Major Changes in v2.2

### Radar Variables Updated
- **OLD:** 7 variables including Prestige
- **NEW:** 7 variables describing COURSE CHARACTERISTICS (what you'll physically experience):
  - **Logistics** (NEW - replaces Prestige)
  - Length
  - Technicality
  - Elevation
  - Climate
  - Altitude
  - Adventure
- **Prestige** moved to "Why It Matters" editorial section (subjective reputation, not course characteristic)

### Component-Based Generation
- **OLD:** Generate entire page as one massive HTML file
- **NEW:** Generate individual components (hero, sections, charts) that can be assembled in Elementor
- **Why:** Prevents timeouts, easier maintenance, better SEO, native WordPress functionality

### WordPress/Elementor Integration
- Hero header can remain custom HTML for brand consistency
- All content sections → Elementor Text Editor (markdown format)
- Tables → Elementor Table Widget with custom CSS
- Radar charts → Uploaded as images
- CTAs → Elementor Button Widgets

### Generation Strategy
When user requests a landing page, offer two approaches:
1. **Component-by-component** (recommended) - Generate pieces sequentially
2. **Full markdown document** (fallback) - Single markdown file for quick setup

## Brand Guidelines

### Visual Identity

**Color Palette:**
- Primary: #59473C (earth brown)
- Secondary: #8C7568, #A68E80, #BFA595
- Accent: #40E0D0 (turquoise)
- Background: #F5F5DC (cream/off-white)
- Grid: #8C7568 (lighter brown)

**Typography:**
- Font: Sometype Mono (bold, minimal, sketchbook energy)
- All caps for headers
- Monospace throughout

**Aesthetic:**
- Semi-realistic, painterly, muted tones with turquoise accents
- Evokes grit, dust, self-reliance
- NOT corporate clean, NOT TrainingPeaks blue
- Think: BTB meets Cormac McCarthy with a gravel bike

### Voice & Tone

**Matti Style Principles:**
1. **Conversational but sharp** - Speak directly like they're already in the arena
2. **Sentences punch** - Short, declarative, visceral
3. **Humor cuts** - Dark, knowing, never soft
4. **Provocative** - Challenge assumptions, expose delusions
5. **No formal cadence** - Avoid "coachly encouragement"
6. **Every line builds the myth or exposes the reality**

**What This Sounds Like:**
- "You don't ride Unbound. You survive it."
- "Palomar doesn't negotiate."
- "The heat is the third discipline after fitness and mental fortitude."
- "Pray for sun. B-roads after rain become a bike-destroying hellscape."

**Anti-Patterns (Never Write):**
- Corporate marketing speak ("Join us for an unforgettable experience!")
- Generic encouragement ("You've got this!")
- Overly technical without context ("This race features 847m of Category 2 climbs")
- Apologetic or hedging language ("This race might be challenging for some")

## Tier System

**Tier 1:** 80-100 (Iconic, essential races - Unbound, SBT GRVL, BWR, Leadville)
**Tier 2:** 65-79 (Great races, maybe regional stars)
**Tier 3:** 50-64 (Solid races, less cultural weight)
**Tier 4:** <50 (Atmosphere/adventure > production/racing - lifestyle gravel, fondos, beer garden vibes)

## Component Generation Workflow

### Component 1: Hero Header (Custom HTML)

**Purpose:** Visual brand signature, first impression
**Format:** HTML/CSS with inline styles
**Deliverable:** Copy-paste ready HTML block for Elementor

**Rules:**
- Follow gravel_god_header_design_rules.md exactly
- 1200x400px dimensions
- Book Cliffs geometric pattern (6 shapes per layer, 7 layers)
- Location badge (state-shaped clip-path)
- Tier badge (tier number only, no distance/route info)
- Race title (turquoise with yellow shadow)
- Quote box (compact, bottom placement, must NOT obscure title)
- NO course maps, lollipop lines, or route visualizations
- NO subtitle (redundant with badges)

**Generation approach:**
```
User: "Generate hero header for Mid South"
Claude: [Generates standalone HTML with inline CSS following header rules]
```

### Component 2: SEO Metadata

**Purpose:** WordPress SEO plugin configuration
**Format:** Structured text with clear labels
**Deliverable:** Copy-paste values for Yoast/RankMath

**Contents:**
```
META TITLE: [Race Name] – Gravel Race Info & Training Guide | Gravel God
META DESCRIPTION: Complete guide to [Race Name]: race vitals, route, history, and how to train for success. Get a custom training plan & coaching tips.
URL SLUG: /races/[race-name-slug]
FOCUS KEYWORD: [race name]
H1: [Race Name] – Overview & Training Guide

SCHEMA JSON-LD (Event):
[Event schema code]

SCHEMA JSON-LD (Review):
[Review schema code]

SCHEMA JSON-LD (Breadcrumb):
[Breadcrumb schema code]

OPENGRAPH TAGS:
og:title: [Race Name] – Training Guide | Gravel God
og:description: [Meta description]
og:image: [URL to radar chart or hero image]
og:url: https://gravelgodcycling.com/races/[race-slug]
```

### Component 3: Race Vitals Table

**Purpose:** Quick reference data table
**Format:** Markdown table (converts to Elementor Table Widget)
**Deliverable:** Clean markdown table

**Structure:**
```markdown
| **Distance** | **Elevation Gain** | **Surface** | **Cutoff** | **Entry Fee** |
|--------------|-------------------|-------------|------------|---------------|
| [X] miles | [X] ft | [surface types] | [X] hours | $[XXX] |

**Additional Details:**
| **Location** | [City, State] |
| **Date** | [Month/Season] |
| **Field Size** | [Number] riders |
| **Registration** | [Opens when, cost] |
| **Aid Stations** | [Number/locations] |
```

### Component 4: What It Means Section

**Purpose:** Race overview with visceral opening, history, random facts
**Format:** Markdown with proper H2/H3 structure
**Deliverable:** Paste into Elementor Text Editor widget

**Structure:**
```markdown
## What It Means

### The Experience
[3-5 sentences - visceral, gut-level, what it FEELS like]

### History
[2-3 paragraphs - who created it, when, why, evolution, current state]
[Use superscript citations: [^1], [^2]]

### Random Facts
[3-5 interesting/weird/specific facts about the race]
[End with transition line connecting to race profile]
```

**Citations format:**
- Use superscript numbers: [^1], [^2], etc.
- Compile full bibliography in footer component

### Component 5: Radar Chart

**Purpose:** Visual course profile showing physical characteristics
**Format:** Python script → PNG image
**Deliverable:** Two items:
1. Python code to generate chart
2. Instructions for uploading to WordPress media library

**Generation:**
```python
# Standalone script with all dependencies
# Saves to /mnt/user-data/outputs/[race_name]_radar.png
# Gravel God color scheme
# 300 DPI, properly sized labels (not cut off)
```

**Chart specs:**
- **7 COURSE VARIABLES** (what the course is like - physical characteristics):
  - Logistics
  - Length
  - Technicality
  - Elevation
  - Climate
  - Altitude
  - Adventure
- Each scored 1-5
- Gravel God earth-tone colors
- Turquoise accent for data polygon
- Cream background
- Monospace bold labels
- Proper padding to prevent label cutoff

**NOTE:** Prestige is NOT a radar variable. It's editorial judgment in "Why It Matters."

### Component 6: The Stats Table (Course Profile)

**Purpose:** Explain each radar variable in Matti voice
**Format:** Markdown table
**Deliverable:** Paste into Elementor Text Editor or Table Widget

**Structure:**
```markdown
## The Stats: What The Course Is Like

| **Category** | **Score** | **What It Means** |
|--------------|-----------|-------------------|
| **Logistics** | X/5 | [2-3 sentences in Matti voice - travel complexity, lodging, race-day execution] |
| **Length** | X/5 | [2-3 sentences in Matti voice] |
| **Technicality** | X/5 | [2-3 sentences in Matti voice] |
| **Elevation Gain** | X/5 | [2-3 sentences in Matti voice] |
| **Climate** | X/5 | [2-3 sentences in Matti voice] |
| **Altitude** | X/5 | [2-3 sentences in Matti voice] |
| **Adventure** | X/5 | [2-3 sentences in Matti voice] |
```

### Component 7: Why It Matters Table (Editorial Judgment)

**Purpose:** Subjective editorial judgment on race quality/value/reputation
**Format:** Markdown table
**Deliverable:** Paste into Elementor Text Editor or Table Widget

**NOTE:** This is where **Prestige** lives - it's editorial opinion, not course characteristic.

**Structure:**
```markdown
## Why It Matters: Editorial Judgment

| **Category** | **Score** | **What It Means** |
|--------------|-----------|-------------------|
| **Prestige** | X/5 | [2-3 sentences in Matti voice - reputation, cultural weight, "the-ness"] |
| **Cultural Weight** | X/5 | [2-3 sentences in Matti voice] |
| **Race Quality** | X/5 | [2-3 sentences in Matti voice] |
| **Experience** | X/5 | [2-3 sentences in Matti voice] |
| **Community/Vibe** | X/5 | [2-3 sentences in Matti voice] |
| **Field Depth** | X/5 | [2-3 sentences in Matti voice] |
| **Value Proposition** | X/5 | [2-3 sentences in Matti voice] |
```

### Component 8: Overall Score Section

**Purpose:** Holistic judgment with score breakdown
**Format:** Markdown with clear structure
**Deliverable:** Paste into Elementor Text Editor

**Structure:**
```markdown
## Overall Score: [XX]/100

*[One sentence on the stats/mythology duality]. [Race name] scores a [XX] because [2-3 sentences explaining the holistic judgment]. [One sentence on who this race is for].*

### How We Got Here:

**Raw Radar Total (Course Profile):** [X]/35 points
(Logistics + Length + Technicality + Elevation + Climate + Altitude + Adventure)

**Editorial Multipliers:**
- Prestige: +[X] ([reason])
- [Category]: +[X] ([reason])
- [Category]: +[X] ([reason])
...

**Total: [XX]/100**

[Closing paragraph explaining tier placement and what the score means]
```

### Component 9: The Black Pill Section

**Purpose:** Contrarian take, uncomfortable truths
**Format:** Markdown prose
**Deliverable:** Paste into Elementor Text Editor

**Structure:**
```markdown
## The Black Pill

[Paragraph 1: The overarching criticism, race-specific]

[Paragraph 2: The kicker - uncomfortable truth, reality vs marketing]
```

**Critical rules:**
- 2 paragraphs only (not 3)
- Race-specific criticisms from forums/reddit
- NEVER use "you could do this for free" as punchline
- Dark humor, reply guy energy
- NOT mean-spirited - cynical truth-telling

### Component 10: Coach's Note Section

**THIS SECTION IS GENERATED BY THE TRAINING RECOMMENDATIONS SKILL**

Pass race data to Gravel God Training Recommendations skill:
- Race name
- All 7 radar scores (course profile: Logistics, Length, Technicality, Elevation, Climate, Altitude, Adventure)
- Prestige score (from editorial section)
- Weeks available for training
- Race-specific demands summary
- **Training Plan Implications from Research Brief:**
  - Protocol triggers (Heat/Altitude/Technical/Durability/Fueling)
  - Race-specific training emphasis (primary/secondary/tertiary demands)
  - "The One Thing That Will Get You"

The Training skill returns complete Coach's Note with:
- 4 performance categories (Ayahuasca, Finisher, Compete, Podium)
- 7-8 training plan products per race
- Race-specific non-negotiables (derived from research implications)
- Direct links to TrainingPeaks offerings

### Component 11: Footer Section

**Purpose:** Race info, citations, disclaimer
**Format:** Markdown
**Deliverable:** Paste into Elementor Text Editor in footer

**Structure:**
```markdown
---

## Race Information

**Date:** [Month] (annually)  
**Registration:** [Lottery/Open/Qualifier details]  
**Official Website:** [Race official site URL]

---

## Sources

[^1]: [Source title/description] - [URL]
[^2]: [Source title/description] - [URL]
[^3]: [Source title/description] - [URL]

---

## Disclaimer

This page is an independent analysis by Gravel God Cycling and is not affiliated with, endorsed by, or sponsored by [Race Name] or its organizers. All opinions, ratings, and recommendations are editorial content based on publicly available information, race reports, and community feedback. For official race information, registration, and rules, please visit the official race website linked above.

© 2025 Gravel God Cycling. All race names and logos are property of their respective organizations.

---
```

## User Interaction Pattern

### Three-Phase Workflow (RECOMMENDED)

#### Phase 1: Research & Content Draft (Markdown)

**User:** "Generate landing page for [Race Name]"

**Claude:** "I'll start by researching and drafting all the content in markdown format so you can review it before I generate the final components. This lets you make changes before I commit to the hero HTML and charts.

Let me gather information about [Race Name] and create the draft..."

**Claude then generates:**
1. **Content research** (COMPREHENSIVE - see Race Research Brief Skill for full requirements)
   - Official sources (race website, results, course data)
   - Forum deep dives (Reddit r/gravelcycling, TrainerRoad forum, Slowtwitch)
   - YouTube race reports + comments (comments often more honest than videos)
   - Strava/RideWithGPS segment data and ride reports
   - News coverage (VeloNews, CyclingTips, local papers)
   - **Must identify:** specific suffering zones with mile markers, forum consensus on difficulty, weather history, real DNF rates and reasons
2. **Complete markdown draft** with all sections:
   - Race vitals table
   - What It Means (opening, history, facts)
   - Stats table (7 course variables with scores and commentary)
   - Why It Matters table (editorial scores including Prestige)
   - Overall Score breakdown
   - The Black Pill
   - Footer with citations

3. **Radar scores proposal** (the 7 COURSE variables rated 1-5 with brief justification)
4. **Editorial scores proposal** (Prestige and other editorial categories)

**Output format:**
```
# [RACE NAME] - Content Draft for Review

## Proposed Course Profile (Radar Chart):
- Logistics: X/5 (reason - travel/lodging complexity)
- Length: X/5 (reason)
- Technicality: X/5 (reason)
- Elevation: X/5 (reason)
- Climate: X/5 (reason)
- Altitude: X/5 (reason)
- Adventure: X/5 (reason)

## Proposed Editorial Scores:
- Prestige: X/5 (reason - reputation/cultural weight)
- Cultural Weight: X/5 (reason)
- Race Quality: X/5 (reason)
- etc.

## Race Vitals
[table]

## What It Means
[sections]

## The Stats (Course Profile)
[table with 7 course scores]

## Why It Matters (Editorial)
[table with editorial scores including Prestige]

## Overall Score: XX/100
[breakdown]

## The Black Pill
[contrarian take]

## Footer
[race info, citations, disclaimer]

---

**REVIEW THIS DRAFT** - Let me know if you want changes to:
- Course profile scores (too high/low?)
- Prestige/editorial scores?
- Race facts/history (missing anything?)
- Matti voice tone (too harsh/soft?)
- Overall score (seem right?)
- The Black Pill (hit the right note?)

Once approved, I'll generate:
1. Custom hero header HTML
2. SEO metadata with schemas
3. Radar chart PNG (7 course variables)
4. Training recommendations (via Training skill)
5. Elementor assembly instructions
```

#### Phase 2: Revisions (If Needed)

**User:** "Change Climate score to 4/5, add more about the mud history"

**Claude:** [Updates specific sections in the markdown draft]

**Repeat until user approves**

#### Phase 3: Component Generation

**User:** "Looks good, generate the components"

**Claude:** "Perfect! Now I'll generate the final components for WordPress/Elementor assembly.

Component 1/5: Hero Header..."

**Then sequentially generates:**
1. Hero header (custom HTML with approved race data)
2. SEO metadata (with approved scores and content)
3. Radar chart (Python → PNG with 7 COURSE variables only)
4. Training recommendations (passes data to Training skill)
5. Elementor assembly guide

**Each component delivered as separate, copy-paste ready block.**

---

### Alternative: Direct Component Generation (If User Has Data Ready)

If user provides complete race data upfront (all scores, facts, history):

**User:** "Generate components for Mid South. Here are the scores: [complete data]"

**Claude:** "You've provided everything I need. Skipping the draft phase and generating final components directly..."

**Then generates all 5 final components without markdown draft phase.**

---

### Fallback: Full Markdown Document Only

If user just wants markdown for quick WordPress deployment:

**User:** "Just give me the full markdown page, I'll handle the rest"

**Claude:** [Generates complete markdown document without hero HTML or component segmentation]

**Use case:** User wants to paste directly into WordPress page editor, skip Elementor entirely

### Alternative: Full Markdown Document

If user prefers single file for quick deployment:

**Claude generates:** Complete markdown document with all sections (no HTML hero), designed for direct paste into WordPress page editor.

**Benefits:** Fast deployment, can edit in WordPress
**Drawbacks:** No custom hero header, less visual polish

## SEO Optimization Guidelines

### WordPress/Elementor Implementation

**Site Structure:**
- Domain: gravelgodcycling.com
- Breadcrumb: Home > Races > [Race Name]
- URL Structure: gravelgodcycling.com/races/[race-name-slug]

**Required WordPress Plugins:**
- Yoast SEO or RankMath (meta tags, schema, breadcrumbs)
- MonsterInsights (analytics tracking)
- WP Rocket or SiteGround Optimizer (caching)
- Image compression plugin (Smush or ShortPixel)

### Meta Tags

**Title Tag:**
- Format: "[Race Name] – Gravel Race Info & Training Guide | Gravel God"
- Max 60 characters
- Example: "Unbound 200 – Gravel Race Info & Training Guide | Gravel God"

**Meta Description:**
- 150-160 characters
- Format: "Complete guide to [Race Name]: race vitals, route, history, and how to train for success. Get a custom training plan & coaching tips."

**H1 Optimization:**
- Format: "# [Race Name] – Overview & Training Guide"
- Example: "# Unbound 200 – Overview & Training Guide"

### Heading Structure (H2-H4)

**H2 Subheadings** - Descriptive and keyword-rich:
- "## [Race Name] Race Vitals: Key Stats"
- "## What It Means: [Race Name] Experience"
- "## The Stats: [Race Name] Course Profile"
- "## Why It Matters: Editorial Judgment"
- "## Overall Score: [XX]/100"

**H3 and H4** - Subsections within H2:
- Never skip levels (H2 → H3 → H4)
- Use for category breakdowns, training sections

### Image Optimization

**File Naming:**
- Format: [race-name]-[descriptor].jpg/png
- Examples: unbound-200-radar-chart.png, mid-south-hero.jpg
- NOT: IMG_1234.jpg

**Alt Text:**
- Every image needs descriptive alt text
- Example: "Radar chart showing Unbound 200 course profile with high scores for length, climate difficulty, and adventure factor"

**Image Specs:**
- Compress to <200KB without quality loss
- Use WebP format when possible
- Lazy loading for below-fold images

### Structured Data (Schema Markup)

Generated in SEO Metadata component (Component 2).

Three schemas required:
1. **Event Schema** - Race date, location, organizer
2. **Review Schema** - Overall score as rating
3. **Breadcrumb Schema** - Site navigation path

### Internal Linking Strategy

**Hub Page:**
- Main /races page lists all races
- Each race page links back to hub

**Cross-Linking:**
- Link to related races contextually
- Example: "Unlike Leadville 100, this race..." (link "Leadville 100")

**Conversion Links:**
- Deep-link to training plans naturally
- Link to coaching page when relevant

**Breadcrumbs:**
- Enable in WordPress SEO plugin
- Format: Home > Races > [Race Name]

### Call-to-Action Placement

**Primary CTAs:**
1. Get [Race Name] Training Plan
2. Get Coaching for [Race Name]

**CTA Placement:**
1. **Above fold** - Subtle banner after hero
2. **In-text** - Woven into Coach's Note naturally
3. **Bottom CTA** - Prominent button after Coach's Note

**Implementation in Elementor:**
- Use Button Widget
- Turquoise background (#40E0D0)
- Earth brown text (#59473C)
- 3px border
- Track clicks with MonsterInsights

### Technical Performance

**Page Speed (Core Web Vitals):**
- Use caching plugin
- Minify CSS/JS
- Compress images
- Lazy-load images
- Target: LCP <2.5s, FID <100ms, CLS <0.1

**Mobile Optimization:**
- Test all components on mobile
- Ensure tables are responsive
- Check radar chart scaling
- Verify text readability

## File Naming Conventions

**Components:**
- Hero HTML: `[race_name]_hero.html`
- Radar chart: `[race_name]_radar.png`
- Metadata: `[race_name]_seo_metadata.txt`
- Full markdown: `[race_name]_landing_page.md`

**WordPress:**
- URL slug: `/races/[race-name-slug]`
- Use lowercase, hyphens for URLs

**Examples:**
- Hero: `unbound_200_hero.html`
- Chart: `unbound_200_radar.png`
- URL: `gravelgodcycling.com/races/unbound-200`

## Integration with Training Recommendations Skill

After completing sections 1-9, pass data to Gravel God Training Recommendations skill:

```
Race: [Race Name]
Course Profile (Radar): Logistics [X], Length [X], Technicality [X], Elevation [X], Climate [X], Altitude [X], Adventure [X]
Editorial: Prestige [X]
Weeks Available: [typically 15, adjust if needed]
Race Demands Summary: [brief description, e.g., "climbing-heavy, technical descents, extreme heat"]

Training Plan Implications (from research):
- Heat Adaptation: [Yes/No + specifics]
- Altitude Protocol: [Yes/No + specifics]
- Technical Skills: [Yes/No + specifics]
- Durability Focus: [Yes/No + where race breaks people]
- Fueling Strategy: [Yes/No + aid gaps]

Race-Specific Training Emphasis:
1. [Primary demand]
2. [Secondary demand]
3. [Tertiary demand]

The One Thing: [forum consensus on what catches people]
```

The Training skill returns complete Coach's Note section with 7-8 training plan recommendations across 4 performance categories, with non-negotiables derived directly from research implications.

## Elementor Assembly Instructions

When all components are generated, provide user with assembly guide:

```
## Assembling Your Landing Page in Elementor

1. **Create New Page:** 
   - WordPress > Pages > Add New
   - Title: "[Race Name]"
   - Set URL slug: /races/[race-name-slug]

2. **Edit with Elementor:**
   - Click "Edit with Elementor" button

3. **Add Hero Header:**
   - Drag "HTML" widget to top
   - Paste hero HTML code
   - Set section height: 400px
   - Full width stretch

4. **Add SEO Metadata:**
   - Scroll down to Yoast SEO or RankMath box below editor
   - Paste title, description, focus keyword
   - Add schemas to "Schema & Structured Data" section

5. **Add Race Vitals:**
   - Drag "Table" widget
   - Set columns/rows, paste data
   - Style: Gravel God colors

6. **Add Text Sections:**
   - Drag "Text Editor" widget for each section
   - Paste markdown (Elementor renders H2/H3 automatically)
   - Sections: What It Means, Stats (Course Profile), Why It Matters (Editorial), Overall Score, Black Pill, Coach's Note, Footer

7. **Add Radar Chart:**
   - Upload PNG to Media Library first
   - Drag "Image" widget
   - Select uploaded radar chart
   - Add alt text: "[Race Name] course profile radar chart"
   - Set alignment: center

8. **Add CTAs:**
   - Drag "Button" widget where needed
   - Text: "Get [Race Name] Training Plan"
   - Link to training plan page
   - Style: Turquoise bg, brown text

9. **Configure Breadcrumbs:**
   - Yoast/RankMath handles automatically
   - Verify format: Home > Races > [Race Name]

10. **Test & Publish:**
    - Preview on mobile
    - Check all links work
    - Verify images load
    - Test page speed
    - Publish!
```

## Rating Calibration Guide

### COURSE PROFILE VARIABLES (Radar Chart)

These describe **what the course is like** - physical characteristics you'll experience.

**Logistics (1-5):**
*How hard is it to get there and execute race day?*
- **5:** Remote/international, limited lodging, complex logistics - Migration, The Rift, Traka
- **4:** Destination race, book months ahead, significant travel - Leadville, Crusher
- **3:** Regional hub, moderate planning needed - SBT GRVL, Mid South
- **2:** Easy access, plenty of lodging options - Barry-Roubaix, most US races
- **1:** Local race, minimal logistics - Drive there morning-of

**Length (1-5):**
- **5:** 200+ miles or multi-day - Ultra/expedition territory
- **4:** 100-150 miles - Full day efforts (8-12+ hours)
- **3:** 60-100 miles - Long but manageable (4-8 hours)
- **2:** 40-60 miles - Half-day events
- **1:** Under 40 miles - Short format

**Technicality (1-5):**
- **5:** MTB skills required - Singletrack, rock gardens, mandatory hike-a-bike
- **4:** Significant bike handling - Sand, mud, technical descents
- **3:** Moderate skills - Rough gravel, some technical sections
- **2:** Basic gravel - Generally smooth with occasional rough patches
- **1:** Pavement-adjacent - Smooth gravel roads

**Elevation (1-5):**
- **5:** 15,000+ ft or sustained HC climbs - Mountain race
- **4:** 10,000-15,000 ft or significant climbing - Serious elevation
- **3:** 6,000-10,000 ft - Moderate climbing
- **2:** 3,000-6,000 ft - Rolling terrain
- **1:** Under 3,000 ft - Flat/minimal climbing

**Climate (1-5):**
- **5:** Extreme conditions - Kansas heat, hypothermia risk, severe weather likely
- **4:** Challenging conditions - Hot/cold likely, weather impacts race
- **3:** Variable conditions - Could go either way
- **2:** Generally favorable - Mild with occasional challenges
- **1:** Ideal conditions - Comfortable racing weather expected

**Altitude (1-5):**
- **5:** 10,000+ ft race elevation - Severe oxygen reduction
- **4:** 8,000-10,000 ft - Significant altitude impact
- **3:** 6,000-8,000 ft - Noticeable altitude effect
- **2:** 4,000-6,000 ft - Minor altitude consideration
- **1:** Under 4,000 ft - Altitude irrelevant

**Adventure (1-5):**
- **5:** Bucket-list destination - Migration, The Rift, once-in-lifetime terrain
- **4:** Destination-worthy - Beautiful terrain worth traveling for
- **3:** Regional appeal - Nice scenery, good experience
- **2:** Functional - Gets the job done, not destination-worthy
- **1:** Unremarkable - Racing is the only draw

### EDITORIAL VARIABLES (Why It Matters)

These are **subjective editorial judgments** - reputation, value, cultural weight.

**Prestige (1-5):**
*NOT a radar variable - editorial opinion on reputation/cultural weight*
- **5:** Unbound, Traka - THE races everyone knows
- **4:** SBT GRVL, BWR, Barry-Roubaix - Major events with recognition
- **3:** Regional flagships - Known in their area/niche
- **2:** Growing events - Building reputation
- **1:** New/local events - Limited recognition

## Success Criteria

A successful landing page:
✅ Maintains Matti voice throughout
✅ Clearly separates Course Profile (radar) from Editorial Judgment (prestige, etc.)
✅ Provides both objective data and editorial judgment
✅ Includes historical context and random facts
✅ Offers contrarian perspective in Black Pill
✅ Generates actionable training recommendations
✅ All components load without timeout issues
✅ SEO metadata properly configured
✅ Mobile responsive
✅ Page speed optimized
✅ Makes the reader either more excited or more scared to do the race (not ambivalent)

## Common Pitfalls to Avoid

1. **Putting Prestige in the radar chart** - It's editorial, not course characteristic
2. **Massive single-file HTML** - Use component approach instead
3. **Generic descriptions** - Every race needs specific voice
4. **Skipping SEO metadata** - Critical for organic traffic
5. **Poor image optimization** - Compress everything
6. **Forgetting citations** - Use superscript numbers, full bibliography
7. **Quote box too large in hero** - Must not obscure title
8. **Missing CTAs** - Training plan links are the conversion goal

The goal is maintainable, SEO-optimized pages that drive training plan sales while maintaining Gravel God brand voice and visual identity.
