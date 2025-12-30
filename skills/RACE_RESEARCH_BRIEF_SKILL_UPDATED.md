# GRAVEL GOD RACE RESEARCH BRIEF SKILL
## Claude-to-Cursor Handoff Protocol

**Purpose:** Claude performs deep research synthesis and strategic analysis. Cursor executes mechanical JSON generation. This division maximizes token efficiency and output quality.

**Workflow:**
1. Claude creates Research Brief (this format)
2. User hands brief to Cursor
3. Cursor generates JSON using schema from `GRAVEL_GOD_LANDING_PAGE_AUTOMATION_SKILL.md`
4. Cursor applies voice from `GG_VoiceTone.pdf`

---

## RESEARCH DEPTH REQUIREMENTS

**This is non-negotiable: Research must be COMPREHENSIVE.**

Every race brief requires deep research across multiple source types. Surface-level Googling produces generic content. The differentiator is specificity that only comes from triangulating multiple perspectives.

### Required Source Categories

**1. Official Sources**
- Race website (current year + archived versions via Wayback Machine)
- Race results/timing data (finishing times, DNF rates, field sizes over time)
- Course maps and elevation profiles
- Official social media (Instagram, Facebook announcements)
- Press releases and media kits

**2. Forum Deep Dives**
- **Reddit:** Search r/gravelcycling, r/cycling, r/Velo for race name
  - Race reports (gold mine for suffering zones, unexpected challenges)
  - "Is [race] worth it?" threads
  - Equipment/tire recommendation threads (reveals terrain truth)
  - Weather horror stories
- **TrainerRoad Forum:** Search for race name
  - Training approach discussions
  - Pacing strategy threads
  - "How hard is [race] really?" posts
- **Slowtwitch** (for races with triathlete crossover)
- **Weight Weenies** (equipment-focused insights)

**3. YouTube Research**
- Race recap videos (watch for course footage, not just highlights)
- GCN/TrainerRoad/Dylan Johnson coverage
- Amateur race reports (often more honest than pro content)
- **READ THE COMMENTS** - real riders share what videos don't show
- Look for multi-year comparisons (how has race changed?)

**4. Strava/RideWithGPS**
- Segment data for key climbs
- Ride reports with photos
- Surface condition notes
- Local rider insights in comments

**5. Podcasts & Interviews**
- Race director interviews (origin story, philosophy)
- Pro rider race reports
- Coaching podcasts discussing race-specific prep

**6. News & Media**
- VeloNews, CyclingTips, Escape Collective coverage
- Local newspaper articles (often have details nationals miss)
- Race incident reports (crashes, weather events, controversies)

### Research Process

**Step 1: Cast Wide Net (30 min)**
- Search "[Race Name] race report" across all platforms
- Search "[Race Name] reddit" 
- Search "[Race Name] review"
- Open 15-20 tabs minimum

**Step 2: Extract Specifics (45 min)**
- Document specific mile markers where shit gets hard
- Note weather patterns across multiple years
- Collect direct quotes from forum posts (for Black Pill authenticity)
- Identify recurring themes (what do people consistently mention?)

**Step 3: Verify & Cross-Reference (15 min)**
- Cross-check stats against official sources
- Confirm distances/elevation haven't changed
- Note any recent course changes

**Step 4: Find the Angle (15 min)**
- What's the story nobody else is telling?
- What do the forums say that the marketing doesn't?
- What's the uncomfortable truth?

### What "Comprehensive" Looks Like

**NOT comprehensive:**
- "Unbound is a 200-mile gravel race in Kansas known for being challenging"
- Generic stats pulled from race website only
- No specific mile markers or suffering zones named
- Black Pill that could apply to any race

**COMPREHENSIVE:**
- "The Teterville rollers at mile 120 are where Unbound breaks people - 15 miles of 8-12% peanut butter hills when your legs are already cooked"
- Forum quote: "I've done Leadville twice and IMTX. Unbound 200 was harder than both."
- Specific weather data: "In 2023, temps hit 103°F by 2pm. In 2019, thunderstorms forced a 2-hour shelter-in-place at mile 80."
- DNF rate trends with reasons (mechanicals vs bonking vs cutoff)

### Research Quality Checklist

Before writing the brief, verify you can answer:

- [ ] What are the 3 specific sections where people suffer most? (with mile markers)
- [ ] What does the forum consensus say about difficulty vs marketing claims?
- [ ] What weather scenarios have actually happened in past years?
- [ ] What equipment failures are common? (reveals terrain truth)
- [ ] What do repeat racers say is different from first-timers' expectations?
- [ ] What's the real DNF rate and why do people quit?
- [ ] What logistics catch people off guard?
- [ ] What's the one thing everyone wishes they'd known?

**If you can't answer these, you haven't researched enough.**

### Research → Training Plan Translation

The whole point of deep research is informing what athletes actually need to train for. Every research finding should trigger a training consideration.

**Research Finding → Training Implication Matrix:**

| What You Discover | Training Plan Consideration |
|-------------------|----------------------------|
| Extreme heat history (90°F+) | Heat adaptation protocol required (10-14 days pre-race sauna/overdress work) |
| High altitude (8,000ft+) | Altitude acclimatization guidance, arrival timing, adjusted power targets |
| Technical sections (sand, mud, rock gardens) | Skills sessions, off-road handling work, MTB trail time |
| Long climbs (20+ min sustained) | Tempo/threshold climbing blocks, seated climbing drills |
| Punchy terrain (repeated short efforts) | VO2max intervals, over-unders, anaerobic capacity work |
| Late-race difficulty (suffering zones after mile 100+) | Durability protocols - quality work after 3+ hours fatigue |
| High DNF rate from mechanicals | Bike handling skills, equipment prep guidance, spare strategy |
| Notorious mud/conditions | Tire pressure strategy, bike fit for conditions, cleaning/lube prep |
| Aid station gaps (30+ miles) | Fueling protocols, self-sufficiency training, stomach training |
| Cutoff pressure | Pacing strategy, minimum sustainable power calculations |
| Night riding (ultras) | Night ride training, lighting setup, fatigue management |
| River crossings/hike-a-bike | Dismount/remount practice, running fitness, shoe choice |

**Required in Every Brief:**

After research, explicitly document:

```markdown
### TRAINING PLAN IMPLICATIONS

Based on research, these training considerations are NON-NEGOTIABLE for this race:

**Protocol Triggers:**
- [ ] Heat Adaptation: [Yes/No] - [specific temps, timing]
- [ ] Altitude Protocol: [Yes/No] - [elevation, arrival strategy]
- [ ] Technical Skills: [Yes/No] - [specific skills needed]
- [ ] Durability Focus: [Yes/No] - [where race breaks people]
- [ ] Fueling Strategy: [Yes/No] - [aid gaps, calorie requirements]

**Race-Specific Training Emphasis:**
1. [Primary physical demand] - [how to train it]
2. [Secondary demand] - [how to train it]
3. [Tertiary demand] - [how to train it]

**The One Thing That Will Get You:**
[Single most important preparation element based on forum consensus]
```

**Example: Unbound 200**

Research reveals:
- Heat: 2023 hit 103°F, 2022 had 95°F+ by noon
- Terrain: Teterville rollers at mile 120 destroy people (repeated 8-12% punches)
- Fueling: 35-mile gaps between some aid stations
- DNFs: Most quit mile 100-150 from accumulated fatigue + heat

Training implications:
- **Heat Adaptation:** MANDATORY - 10-14 day protocol
- **Durability:** Primary focus - must do quality work at 4+ hours fatigue
- **Punchy power:** Over-unders and 30/30s for roller resilience
- **Fueling:** Train stomach to handle 80-100g carbs/hour in heat
- **The One Thing:** "Your fitness at mile 0 is irrelevant. It's your fitness at mile 130 in 100°F heat that matters."

This section gets passed directly to the Training Recommendations skill to inform plan structure.

---

## RESEARCH BRIEF TEMPLATE

```markdown
# [RACE NAME] RESEARCH BRIEF
## Gravel God Landing Page Data

### THE ANGLE
[1-2 sentences: What's the story? Why does this race matter? What's the unique positioning opportunity?]

### STRATEGIC VALUE
- **Competition:** [None / Low / Medium / High] - [specifics on existing training plans]
- **Market Opportunity:** [Why this race, why now]
- **Protocol Fit:** [Heat ✓ / Altitude ✓ / Skills ✓ / Standard]

---

### VITAL STATISTICS
| Field | Value |
|-------|-------|
| Distance | [mi / km] |
| Elevation | [ft / m] |
| Location | [City, State/Country] |
| Date | [Timing + specific 2026 date if known] |
| Field Size | [number + context] |
| Entry Cost | [range] |
| Cutoff | [time limit] |
| Aid Stations | [number + spacing] |

### TERRAIN PROFILE
- **Primary Surface:** [description]
- **Technical Rating:** [1-5] - [justification]
- **Signature Features:** [bullet list of what makes terrain unique]

### CLIMATE REALITY
- **Conditions:** [what to expect]
- **Primary Challenge:** [heat / cold / wet / variable]
- **Preparation Required:** [specific training implications]

---

### GRAVEL GOD RATINGS - COURSE PROFILE (RADAR CHART)

These 7 variables describe **what the course is like** - the physical characteristics you'll experience on race day.

| Category | Score | Justification |
|----------|-------|---------------|
| Logistics | [1-5] | [travel complexity, lodging availability, race-day logistics] |
| Length | [1-5] | [duration context, not just miles] |
| Technicality | [1-5] | [what skills required] |
| Elevation | [1-5] | [climbing character, not just feet] |
| Climate | [1-5] | [challenge level and type] |
| Altitude | [1-5] | [elevation impact on performance] |
| Adventure | [1-5] | [bucket-list factor, destination-worthiness] |

**Course Profile Score:** [sum of all 7 / 35 possible]

---

### COURSE NARRATIVE

**Character:** [1-2 sentences capturing the essence]

**Suffering Zones:**
1. [Mile/KM X] - [Name] - [What happens here]
2. [Mile/KM X] - [Name] - [What happens here]  
3. [Mile/KM X] - [Name] - [What happens here]

**Signature Challenge:** [The ONE thing that defines this race]

---

### HISTORY & REPUTATION

- **Founded:** [year]
- **Origin:** [brief story]
- **Notable Moments:** [2-3 bullets]
- **Reputation:** [How the gravel community sees this race]

---

### BLACK PILL REALITY

**The Truth:** [What nobody tells you - honest, direct, Matti voice]

**Consequences:**
- [Real cost - time, money, suffering]
- [Real preparation required]
- [Real likelihood of suffering/DNF]

**Expectation Reset:** [What training actually needs to focus on]

---

### BIASED OPINION (EDITORIAL JUDGMENT)

This section captures **subjective editorial assessment** - reputation, cultural weight, and value judgment.

**Prestige:** [1-5] - [Why this score - is it THE race? Regional star? Up-and-comer?]

**Verdict:** [One word: Icon / Essential / Must-Do / Hidden Gem / Bucket List / OG / etc.]

**Summary:** [2-3 sentences in Matti voice - direct, honest, no BS]

**Strengths:**
- [What this race does well]
- [Why people love it]
- [Unique value proposition]

**Weaknesses:**
- [Honest drawbacks]
- [Logistical challenges]
- [Who should skip this]

**Bottom Line:** [One sentence decision-maker]

**Overall Score:** [X/100] - calculated from Course Profile + Editorial multipliers

---

### LOGISTICS SNAPSHOT

| Field | Details |
|-------|---------|
| Airport | [code + distance] |
| Lodging | [strategy + booking timeline] |
| Packet Pickup | [when/where + time needed] |
| Parking | [situation] |
| Official Site | [URL] |

---

### TRAINING PLAN IMPLICATIONS

Based on research, these training considerations are NON-NEGOTIABLE for this race:

**Protocol Triggers:**
- [ ] Heat Adaptation: [Yes/No] - [specific temps, timing]
- [ ] Altitude Protocol: [Yes/No] - [elevation, arrival strategy]
- [ ] Technical Skills: [Yes/No] - [specific skills needed]
- [ ] Durability Focus: [Yes/No] - [where race breaks people]
- [ ] Fueling Strategy: [Yes/No] - [aid gaps, calorie requirements]

**Race-Specific Training Emphasis:**
1. [Primary physical demand] - [how to train it]
2. [Secondary demand] - [how to train it]
3. [Tertiary demand] - [how to train it]

**The One Thing That Will Get You:**
[Single most important preparation element based on forum consensus]

---

### CURSOR INSTRUCTIONS

```
Generate JSON following schema in: /mnt/project/GRAVEL_GOD_LANDING_PAGE_AUTOMATION_SKILL.md

Apply voice guidelines from: /mnt/project/GG_VoiceTone.pdf

Key voice notes for this race:
- [Specific tone guidance]
- [Phrases to use/avoid]
- [Angle to emphasize]

Training plans section: Leave plans array empty (populated separately)

RideWithGPS: Use "TBD" for IDs until actual routes sourced
```
```

---

## RATING CALIBRATION GUIDE

Use these anchors for consistent scoring:

### Logistics (1-5) - RADAR VARIABLE
*How hard is it to get there and execute race day?*
- **5:** Remote/international, limited lodging, complex logistics - Migration, The Rift, Traka
- **4:** Destination race, book months ahead, significant travel - Leadville, Crusher
- **3:** Regional hub, moderate planning needed - SBT GRVL, Mid South
- **2:** Easy access, plenty of lodging options - Barry-Roubaix, most US races
- **1:** Local race, minimal logistics - Drive there morning-of

### Length (1-5) - RADAR VARIABLE
- **5:** 200+ miles or multi-day - Ultra/expedition territory
- **4:** 100-150 miles - Full day efforts (8-12+ hours)
- **3:** 60-100 miles - Long but manageable (4-8 hours)
- **2:** 40-60 miles - Half-day events
- **1:** Under 40 miles - Short format

### Technicality (1-5) - RADAR VARIABLE
- **5:** MTB skills required - Singletrack, rock gardens, mandatory hike-a-bike
- **4:** Significant bike handling - Sand, mud, technical descents
- **3:** Moderate skills - Rough gravel, some technical sections
- **2:** Basic gravel - Generally smooth with occasional rough patches
- **1:** Pavement-adjacent - Smooth gravel roads

### Elevation (1-5) - RADAR VARIABLE
- **5:** 15,000+ ft or sustained HC climbs - Mountain race
- **4:** 10,000-15,000 ft or significant climbing - Serious elevation
- **3:** 6,000-10,000 ft - Moderate climbing
- **2:** 3,000-6,000 ft - Rolling terrain
- **1:** Under 3,000 ft - Flat/minimal climbing

### Climate (1-5) - RADAR VARIABLE
- **5:** Extreme conditions - Kansas heat, hypothermia risk, severe weather likely
- **4:** Challenging conditions - Hot/cold likely, weather impacts race
- **3:** Variable conditions - Could go either way
- **2:** Generally favorable - Mild with occasional challenges
- **1:** Ideal conditions - Comfortable racing weather expected

### Altitude (1-5) - RADAR VARIABLE
- **5:** 10,000+ ft race elevation - Severe oxygen reduction
- **4:** 8,000-10,000 ft - Significant altitude impact
- **3:** 6,000-8,000 ft - Noticeable altitude effect
- **2:** 4,000-6,000 ft - Minor altitude consideration
- **1:** Under 4,000 ft - Altitude irrelevant

### Adventure (1-5) - RADAR VARIABLE
- **5:** Bucket-list destination - Migration, The Rift, once-in-lifetime terrain
- **4:** Destination-worthy - Beautiful terrain worth traveling for
- **3:** Regional appeal - Nice scenery, good experience
- **2:** Functional - Gets the job done, not destination-worthy
- **1:** Unremarkable - Racing is the only draw

---

### Prestige (1-5) - EDITORIAL (Biased Opinion section)
*NOT a radar variable - this is subjective reputation/cultural weight*
- **5:** Unbound, Traka - THE races everyone knows
- **4:** SBT GRVL, BWR, Barry-Roubaix - Major events with recognition
- **3:** Regional flagships - Known in their area/niche
- **2:** Growing events - Building reputation
- **1:** New/local events - Limited recognition

---

## VOICE CALIBRATION

### Matti Voice Characteristics
- **Direct:** No hedging, no corporate speak
- **Honest:** If it sucks, say it sucks
- **Specific:** Real numbers, real consequences
- **Earned Authority:** 15 years of cycling credibility
- **Confrontational Helpfulness:** Challenge assumptions while providing value

### Phrases to USE
- "The thing nobody tells you..."
- "Your FTP doesn't matter if..."
- "This isn't about watts, it's about..."
- "Show up undertrained and you'll..."
- "The [X] doesn't negotiate"

### Phrases to AVOID
- "Amazing opportunity"
- "World-class experience" 
- "Don't miss out"
- Generic marketing language
- Excessive enthusiasm without substance

---

## QUALITY CHECKLIST

Before handoff to Cursor, verify:

- [ ] All vital statistics sourced/verified
- [ ] Radar ratings (7 course variables) justified with specific reasoning
- [ ] Prestige score in Biased Opinion section (not radar)
- [ ] Black Pill is genuinely honest (not marketing-softened)
- [ ] Voice is distinctly Matti (not generic coaching)
- [ ] Logistics snapshot is actionable (not vague)
- [ ] Angle/positioning is clear and differentiated
- [ ] Competition gap identified and addressed
- [ ] **Training Plan Implications section completed with specific protocol triggers**
- [ ] **Research findings directly inform training emphasis (not generic)**
- [ ] **"The One Thing" identified from forum consensus**

---

## FILE ORGANIZATION

```
/race-research-briefs/
  barry-roubaix-brief.md
  traka-brief.md
  migration-gravel-race-brief.md
  ...
```

Cursor outputs to:
```
/race-data/
  barry-roubaix-data.json
  traka-data.json
  ...
```

---

## BATCH HANDOFF FORMAT

For multiple races, create single handoff document:

```markdown
# RACE RESEARCH BRIEFS - BATCH HANDOFF
## [Date] - [Number] Races

### Cursor Global Instructions
- Schema: /mnt/project/GRAVEL_GOD_LANDING_PAGE_AUTOMATION_SKILL.md
- Voice: /mnt/project/GG_VoiceTone.pdf
- Output: /race-data/[slug]-data.json

---

## RACE 1: [Name]
[Full brief]

---

## RACE 2: [Name]
[Full brief]

---
```

This allows single-prompt Cursor execution for multiple races.
