# Website Data for gravelgodcycling.com

JSON data files for the `/races` section of the GravelGod Cycling website.

## Files

| File | Description | Records |
|------|-------------|---------|
| `race-calendar.json` | Chronological race listing with dates, locations, registration | 388 races |
| `difficulty-rankings.json` | Races scored by difficulty factors | 388 races |
| `geographic-clusters.json` | Races grouped by region | 10 regions |

---

## Schema: race-calendar.json

```json
{
  "generated": "2026-01-13T00:00:00Z",
  "total_races": 388,
  "races": [
    {
      "name": "Unbound Gravel",
      "slug": "unbound-gravel",
      "date": "May 31",
      "date_2026": "May 30, 2026",
      "location": {
        "city": "Emporia",
        "state": "Kansas",
        "country": "USA"
      },
      "distances": ["200", "100", "50", "25"],
      "website_url": "https://www.unboundgravel.com",
      "registration_url": "https://www.unboundgravel.com/register",
      "entry_cost": "$200-300",
      "field_size": "4000+",
      "tier": "1"
    }
  ]
}
```

---

## Schema: difficulty-rankings.json

```json
{
  "generated": "2026-01-13T00:00:00Z",
  "scoring_methodology": "5-point scale per category",
  "races": [
    {
      "name": "Unbound XL",
      "slug": "unbound-xl",
      "scores": {
        "distance": 5,
        "elevation": 4,
        "technical": 3,
        "altitude": 2,
        "weather": 4
      },
      "total_score": 18,
      "difficulty_tier": "Elite",
      "distance_miles": 350,
      "elevation_ft": 14000,
      "cutoff_hours": 36,
      "notes": "Overnight self-supported ultra"
    }
  ]
}
```

### Difficulty Tiers
- **Beginner** (5-8 points): Short distance, low elevation, forgiving cutoffs
- **Intermediate** (9-12 points): Moderate challenge, standard gravel
- **Advanced** (13-16 points): Significant distance/climbing, competitive
- **Expert** (17-20 points): Major events, demanding courses
- **Elite** (21-25 points): Ultra-distance, extreme conditions, self-supported

---

## Schema: geographic-clusters.json

```json
{
  "generated": "2026-01-13T00:00:00Z",
  "clusters": [
    {
      "region": "Midwest",
      "description": "Kansas, Iowa, Minnesota, Wisconsin, Illinois",
      "race_count": 45,
      "signature_races": ["Unbound Gravel", "Almanzo 100"],
      "races": [
        {
          "name": "Unbound Gravel",
          "slug": "unbound-gravel",
          "date": "May 31",
          "location": "Emporia, KS",
          "difficulty_tier": "Expert"
        }
      ]
    }
  ]
}
```

---

## WordPress Integration

### Option 1: WP All Import
Import JSON directly to a custom post type `gravel_race`.

### Option 2: ACF JSON Sync
Place field group JSON in `/wp-content/themes/your-theme/acf-json/`.

### Option 3: REST API Endpoint
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

### Option 4: JavaScript Fetch
```javascript
fetch('/wp-content/themes/your-theme/data/race-calendar.json')
  .then(res => res.json())
  .then(data => renderRaceCalendar(data.races));
```

---

## Data Sources

- **Primary**: `gravel_races_full_database.json` (388 races)
- **Enhanced**: `research-dumps/*.md` (61 detailed research files)
- **Structured**: `race-data/*.json` (53 individual race files)

---

## Updates

Generated: January 13, 2026
Source repo: https://github.com/wattgod/gravel-race-automation
