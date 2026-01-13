# Website Data for gravelgodcycling.com

JSON data files for the `/races` section of the GravelGod Cycling website.

## Files

| File | Description | Records |
|------|-------------|---------|
| `race-calendar.json` | Chronological race listing with dates, locations, tiers | 388 races |
| `difficulty-rankings.json` | Races with full course profiles and scoring | 21 races |
| `geographic-clusters.json` | Races grouped by region with tier breakdown | 11 regions |

---

## GravelGod Tier System

| Tier | Description | Count |
|------|-------------|-------|
| **TIER 1** | Premier events - Life Time Grand Prix, UCI qualifiers, iconic races | 23 |
| **TIER 2** | Established events - strong reputation, quality organization | 64 |
| **TIER 3** | Regional/emerging events - local favorites, growing scene | 301 |

---

## Schema: race-calendar.json

```json
{
  "generated": "2026-01-13T00:00:00Z",
  "total_races": 388,
  "tier_counts": { "tier_1": 23, "tier_2": 64, "tier_3": 301 },
  "races": [
    {
      "name": "Unbound Gravel 200",
      "slug": "unbound-gravel",
      "date": "May 31",
      "date_specific": "2026: May 30",
      "location": {
        "city": "Emporia",
        "state": "Kansas",
        "country": "USA",
        "full": "Emporia, Kansas"
      },
      "distances": ["200", "100", "50", "25"],
      "elevation_gain": "11,000 ft",
      "website_url": "https://www.unboundgravel.com",
      "entry_cost": "$200-300",
      "field_size": "4000+",
      "tier": 1,
      "tier_label": "TIER 1",
      "overall_score": 93,
      "has_detailed_profile": true
    }
  ]
}
```

---

## Schema: difficulty-rankings.json

Uses the GravelGod course profile system with 7 dimensions (1-5 scale each):

```json
{
  "generated": "2026-01-13T00:00:00Z",
  "schema_version": "2.0",
  "tier_system": {
    "1": "Premier events",
    "2": "Established events",
    "3": "Regional/emerging events"
  },
  "course_profile_dimensions": [
    "length", "technicality", "elevation",
    "climate", "altitude", "logistics", "adventure"
  ],
  "races": [
    {
      "name": "Unbound Gravel 200",
      "slug": "unbound-200",
      "overall_score": 93,
      "display_tier": 1,
      "display_tier_label": "TIER 1",
      "course_profile": {
        "length": 5,
        "technicality": 3,
        "elevation": 4,
        "climate": 4,
        "altitude": 2,
        "logistics": 3,
        "adventure": 5
      },
      "course_profile_total": 26,
      "distance_mi": 200,
      "elevation_ft": 11000
    }
  ]
}
```

### Course Profile Dimensions

| Dimension | What it measures |
|-----------|-----------------|
| **Length** | Distance - 5 = 200+ miles, 1 = under 40 miles |
| **Technicality** | Surface difficulty, descents, bike handling required |
| **Elevation** | Total climbing - 5 = 10,000+ ft |
| **Climate** | Weather challenges - heat, cold, storms |
| **Altitude** | Max elevation impact - 5 = 10,000+ ft finish |
| **Logistics** | Travel difficulty, remoteness, support availability |
| **Adventure** | Epic factor, scenery, memorable experience |

---

## Schema: geographic-clusters.json

```json
{
  "generated": "2026-01-13T00:00:00Z",
  "total_regions": 11,
  "total_races": 388,
  "clusters": [
    {
      "region": "Midwest",
      "description": "The heartland of American gravel - Flint Hills, farm roads, lake country",
      "race_count": 61,
      "tier_breakdown": { "tier_1": 3, "tier_2": 9, "tier_3": 49 },
      "signature_races": ["Unbound Gravel", "Almanzo 100", "Gravel Worlds"],
      "races": [...]
    }
  ]
}
```

### Regions

| Region | Races | Tier 1 | Description |
|--------|-------|--------|-------------|
| Midwest | 61 | 3 | Unbound country - Kansas, Iowa, Minnesota |
| Europe | 47 | 4 | Alps to Mediterranean diversity |
| Southeast | 35 | 1 | Rolling terrain, southern hospitality |
| Mountain West | 30 | 4 | High altitude, spectacular scenery |
| California | 26 | 1 | Year-round racing, coast to mountains |
| Pacific Northwest | 19 | 0 | Forests, volcanic terrain |
| Northeast | 15 | 0 | New England gravel, fall foliage |
| Canada | 14 | 1 | Canadian Gravel Cup, wilderness |
| Southwest | 12 | 2 | Desert gravel, heat challenges |

---

## WordPress Integration

### Option 1: WP All Import
Import JSON directly to custom post type `gravel_race`.

### Option 2: REST API Endpoint
```php
add_action('rest_api_init', function() {
    register_rest_route('gravelgod/v1', '/races', [
        'methods' => 'GET',
        'callback' => function() {
            $json = file_get_contents(get_template_directory() . '/data/race-calendar.json');
            return json_decode($json);
        }
    ]);
});
```

### Option 3: JavaScript Fetch
```javascript
fetch('/wp-content/themes/your-theme/data/race-calendar.json')
  .then(res => res.json())
  .then(data => {
    const tier1 = data.races.filter(r => r.tier === 1);
    renderRaceCalendar(tier1);
  });
```

---

## Data Sources

| Source | Records | Detail Level |
|--------|---------|--------------|
| `gravel_races_full_database.json` | 388 | Basic (tier, location, dates) |
| `race-data/*.json` | 53 | Enhanced (vitals, terrain) |
| `research-dumps/*.md` | 61 | Full research (21 with course profiles) |

---

## Updates

- **Generated**: January 13, 2026
- **Schema version**: 2.0 (GravelGod 3-tier system)
- **Source repo**: https://github.com/wattgod/gravel-race-automation
