# GravelGod Race Scoring System v2.2

> **CRITICAL DOCUMENT FOR ALL AGENTS**
> This is the definitive scoring system for all GravelGod race profiles.
> Follow this EXACTLY when creating or updating race data.

---

## Overview

Each race is scored on **14 base dimensions** across two categories, plus a **bonus dimension**:
- **Course Profile** (7 dimensions) - Physical and logistical demands
- **Editorial** (7 dimensions) - Race quality and value assessment
- **Cultural Impact** (1 bonus dimension, 0-5) - Attendance, media coverage, cultural significance

Plus a **4-tier classification system** and **overall score** (0-100+).

---

## Tier System

| Tier | Label | Score | Description | Examples |
|------|-------|-------|-------------|----------|
| **1** | Elite | >= 80 | The definitive gravel events. World-class fields, iconic courses, bucket-list status. | Unbound, Badlands, SBT GRVL, Crusher |
| **2** | Contender | >= 60 | Established races with strong reputations and competitive fields. The next tier of must-do events. | Barry-Roubaix, Rebecca's Private Idaho, Dirty Reiver |
| **3** | Solid | >= 45 | Regional favorites and emerging races. Strong local scenes, genuine gravel character. | Most local gravel races |
| **4** | Roster | < 45 | Up-and-coming races and local grinders. Grassroots gravel — small fields, raw vibes. | New/niche events |

### Prestige Override

Some races carry outsized cultural significance beyond their raw score:

- **Prestige 5** (World-class) + score >= 75 → Promoted to Tier 1
- **Prestige 5** (World-class) + score < 75 → Capped at Tier 2 (not T1)
- **Prestige 4** (National) → Promoted 1 tier, but never into Tier 1
- **Prestige 1-3** → No override, tier determined by score alone

The >= 75 floor for prestige-5 T1 promotion prevents low-scoring races from reaching Elite status purely on name recognition.

### Discipline Tagging

Races are tagged with a `discipline` field in `gravel_god_rating`:
- `"gravel"` — default for all gravel events
- `"mtb"` — used for MTB-primary events included for cultural significance (e.g., Leadville 100, Chequamegon)

---

## Course Profile (7 Dimensions)

These measure the **physical and logistical demands** of the race.

| Dimension | Score 1 | Score 2 | Score 3 | Score 4 | Score 5 |
|-----------|---------|---------|---------|---------|---------|
| **Length** | <40 mi | 40-60 mi | 60-100 mi | 100-150 mi | 150+ mi |
| **Technicality** | Smooth gravel | Some rough sections | Mixed terrain | Technical descents | Singletrack/extreme |
| **Elevation** | <2,000 ft | 2,000-4,000 ft | 4,000-6,000 ft | 6,000-10,000 ft | 10,000+ ft |
| **Climate** | Mild/ideal | Slightly challenging | Moderate challenge | Significant challenge | Extreme (heat/cold/storms) |
| **Altitude** | Sea level | <3,000 ft | 3,000-6,000 ft | 6,000-9,000 ft | 9,000+ ft / finish above 10k |
| **Logistics** | Easy access | Minor travel | Moderate planning | Remote/difficult | Extreme remoteness |
| **Adventure** | Standard race | Some character | Memorable | Epic scenery/experience | Bucket list / life-changing |

### Course Profile JSON Structure

```json
"course_profile": {
  "length": {
    "score": 4,
    "explanation": "100 miles is substantial but not ultra territory..."
  },
  "technicality": {
    "score": 3,
    "explanation": "Mixed surfaces with some technical descents..."
  },
  "elevation": {
    "score": 4,
    "explanation": "6,500ft of climbing challenges most riders..."
  },
  "climate": {
    "score": 3,
    "explanation": "Variable spring weather, potential for rain..."
  },
  "altitude": {
    "score": 2,
    "explanation": "Moderate elevation, minimal altitude impact..."
  },
  "logistics": {
    "score": 3,
    "explanation": "Regional airport nearby, hotels available..."
  },
  "adventure": {
    "score": 4,
    "explanation": "Iconic course through stunning terrain..."
  }
}
```

---

## Editorial (7 Dimensions)

These measure the **race quality and value proposition**.

| Dimension | Score 1 | Score 2 | Score 3 | Score 4 | Score 5 |
|-----------|---------|---------|---------|---------|---------|
| **Prestige** | Unknown | Local recognition | Regional reputation | National significance | World-class / iconic |
| **Race Quality** | Basic | Adequate | Good organization | Professional | Elite / flawless |
| **Experience** | Forgettable | Pleasant | Enjoyable | Memorable | Life-changing |
| **Community** | Sparse | Small group | Good vibe | Strong community | Legendary culture |
| **Field Depth** | Casual only | Some competition | Competitive | Strong pros | Elite field / LTGP |
| **Value** | Overpriced | Below average | Fair | Good value | Exceptional value |
| **Expenses** | Extreme ($2k+) | High ($1-2k) | Moderate ($500-1k) | Reasonable ($300-500) | Budget-friendly (<$300) |

### Editorial JSON Structure

```json
"biased_opinion_ratings": {
  "prestige": {
    "score": 5,
    "explanation": "Part of Life Time Grand Prix, legendary status..."
  },
  "race_quality": {
    "score": 4,
    "explanation": "Well-organized with quality aid stations..."
  },
  "experience": {
    "score": 5,
    "explanation": "Unforgettable race day atmosphere..."
  },
  "community": {
    "score": 4,
    "explanation": "Strong gravel community, welcoming vibe..."
  },
  "field_depth": {
    "score": 5,
    "explanation": "Top pros attend, LTGP points on the line..."
  },
  "value": {
    "score": 4,
    "explanation": "Premium event with premium support..."
  },
  "expenses": {
    "score": 3,
    "explanation": "Moderate travel costs, hotels available..."
  }
}
```

---

## Cultural Impact (Bonus Dimension)

A bonus dimension that captures attendance, media coverage, and cultural significance — factors not covered by the 14 base dimensions. Defaults to 0 if not set.

| CI | Level | Criteria |
|----|-------|----------|
| 5 | Global Icon | Defines gravel cycling. 2,000+ riders, massive mainstream + cycling media, cultural landmark. |
| 4 | Major International | 1,000+ riders, significant international draw, strong media presence, established legacy. |
| 3 | Notable National | Nationally recognized, growing media, solid participation, strong regional significance. |
| 2 | Established Regional | Quality event with dedicated following but limited broader cultural footprint. |
| 1 | Emerging | Building reputation, minimal media beyond local cycling communities. |
| 0 | Default | No bonus. Most T3/T4 races. |

## Overall Score (0-100+)

The overall score is calculated as:

```
overall_score = round((sum of 14 base scores + cultural_impact) / 70 × 100)
```

- Maximum raw base score: 70 (14 dimensions × 5)
- Cultural impact adds 0-5 bonus points to the numerator without increasing the denominator
- Theoretical maximum with CI=5: ~107 (75/70 × 100)
- A race scoring 3/5 across all 14 dimensions with CI=0 = **60**
- A race scoring 4/5 across all 14 dimensions with CI=0 = **80**
- A race scoring 4/5 across all 14 dimensions with CI=5 = **87**

---

## Complete JSON Structure

```json
{
  "race": {
    "name": "RACE NAME",
    "slug": "race-name",
    "display_name": "Race Name",
    "tagline": "One-liner in Matti voice",

    "vitals": {
      "distance_mi": 100,
      "elevation_ft": 6500,
      "location": "City, State",
      "location_badge": "CITY, STATE",
      "date": "Month annually",
      "date_specific": "2026: Month DD"
    },

    "gravel_god_rating": {
      "overall_score": 85,
      "course_profile": 24,
      "biased_opinion": 28,
      "editorial_tier": 1,
      "editorial_tier_label": "TIER 1",
      "business_tier": 1,
      "business_tier_label": "TIER 1",
      "display_tier": 1,
      "display_tier_label": "TIER 1"
    },

    "course_profile": {
      "length": { "score": 4, "explanation": "..." },
      "technicality": { "score": 3, "explanation": "..." },
      "elevation": { "score": 4, "explanation": "..." },
      "climate": { "score": 3, "explanation": "..." },
      "altitude": { "score": 2, "explanation": "..." },
      "logistics": { "score": 3, "explanation": "..." },
      "adventure": { "score": 4, "explanation": "..." }
    },

    "biased_opinion_ratings": {
      "prestige": { "score": 5, "explanation": "..." },
      "race_quality": { "score": 4, "explanation": "..." },
      "experience": { "score": 5, "explanation": "..." },
      "community": { "score": 4, "explanation": "..." },
      "field_depth": { "score": 5, "explanation": "..." },
      "value": { "score": 4, "explanation": "..." },
      "expenses": { "score": 3, "explanation": "..." }
    }
  }
}
```

---

## Scoring Examples

### Tier 1 Example: Unbound Gravel 200
| Category | Dimension | Score | Why |
|----------|-----------|-------|-----|
| Course | Length | 5 | 200 miles |
| Course | Technicality | 3 | Flint Hills gravel, not extreme |
| Course | Elevation | 4 | 11,000 ft total |
| Course | Climate | 4 | Kansas heat, storms possible |
| Course | Altitude | 2 | Low elevation |
| Course | Logistics | 3 | Emporia accessible |
| Course | Adventure | 5 | Iconic, bucket list |
| **Course Total** | | **26/35** | |
| Editorial | Prestige | 5 | The gravel race |
| Editorial | Race Quality | 4 | Life Time production |
| Editorial | Experience | 5 | Unforgettable |
| Editorial | Community | 5 | Gravel mecca |
| Editorial | Field Depth | 5 | Best in the world |
| Editorial | Value | 4 | Premium but worth it |
| Editorial | Expenses | 3 | Moderate total cost |
| **Editorial Total** | | **31/35** | |
| **Overall** | | **93/100** | |

### Tier 2 Example: Barry-Roubaix
| Category | Dimension | Score | Why |
|----------|-----------|-------|-----|
| Course | Length | 3 | 62 miles (Killer) |
| Course | Technicality | 3 | Sandy two-track |
| Course | Elevation | 2 | ~2,500 ft |
| Course | Climate | 3 | Michigan spring - mud! |
| Course | Altitude | 1 | Low elevation |
| Course | Logistics | 3 | Midwest accessible |
| Course | Adventure | 3 | Fun, not epic |
| **Course Total** | | **18/35** | |
| Editorial | Prestige | 4 | Largest in Midwest |
| Editorial | Race Quality | 4 | Well-organized |
| Editorial | Experience | 4 | Great atmosphere |
| Editorial | Community | 5 | Amazing vibe |
| Editorial | Field Depth | 3 | Regional pros |
| Editorial | Value | 4 | Good value |
| Editorial | Expenses | 4 | Budget-friendly |
| **Editorial Total** | | **28/35** | |
| **Overall** | | **72/100** | |

---

## Agent Instructions

When creating or updating race profiles:

1. **Research thoroughly** - Get actual distance, elevation, dates
2. **Score each dimension** with explanation (1-2 sentences)
3. **Be consistent** - Use the rubrics above
4. **Assign tier** based on prestige, field depth, series affiliation
5. **Calculate overall** considering both category totals + tier

**DO NOT:**
- Invent your own scoring system
- Skip the explanations
- Use different dimension names
- Forget the tier assignment

---

## Version History

- **v2.3** (Feb 2026): Cultural Impact bonus dimension, score formula update, dimension adjustments
- **v2.2** (Feb 2026): 4-tier system, prestige >= 75 floor for T1, discipline tags, methodology page
- **v2.1** (Jan 2026): Dual scoring system (Course + Editorial)
- **v2.0** (Jan 2026): 3-tier system standardized
- **v1.0** (Dec 2025): Initial scoring framework

---

*This document is the source of truth for all GravelGod race scoring.*
