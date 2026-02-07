# Converting Mid South JSON to WordPress Template

## Files Found in `gravel-landing-page-project`

### Race Data Structure
**Location:** `~/gravel-landing-page-project/data/mid-south-data.json`

The race data is nested under a `race` key:
```json
{
  "race": {
    "name": "Mid South",
    "vitals": {
      "location": "Stillwater, Oklahoma",
      "distance_mi": 100,
      "elevation_ft": 4500,
      ...
    },
    "history": {
      "founded": 2013,
      "founder": "Bobby and Crystal Wintle",
      ...
    },
    ...
  }
}
```

### Elementor JSON Structure
**Location:** `~/gravel-landing-page-project/output/elementor-mid-south.json`

The Elementor JSON has this structure:
```json
{
  "content": [
    {
      "id": "...",
      "elType": "section",
      "elements": [
        {
          "elType": "column",
          "elements": [
            {
              "elType": "widget",
              "widgetType": "html",
              "settings": {
                "html": "<div>Hardcoded content here...</div>"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

## Conversion Strategy

### Step 1: Map Race Data Fields to Placeholders

From `mid-south-data.json`, identify these fields to replace:

| Field Path | Placeholder | Example Value |
|------------|-------------|---------------|
| `race.name` | `{{RACE_NAME}}` | "Mid South" |
| `race.display_name` | `{{RACE_DISPLAY_NAME}}` | "The Mid South" |
| `race.vitals.location` | `{{LOCATION}}` | "Stillwater, Oklahoma" |
| `race.vitals.location_badge` | `{{LOCATION_BADGE}}` | "STILLWATER, OKLAHOMA" |
| `race.vitals.distance_mi` | `{{DISTANCE}}` | 100 |
| `race.vitals.elevation_ft` | `{{ELEVATION_GAIN}}` | 4500 |
| `race.gravel_god_rating.overall_score` | `{{RATING_SCORE}}` | 85 |
| `race.gravel_god_rating.tier_label` | `{{TIER_LABEL}}` | "TIER 1" |
| `race.tagline` | `{{TAGLINE}}` | "Oklahoma's weather lottery..." |
| `race.logistics.official_site` | `{{WEBSITE_URL}}` | "https://www.midsouthgravel.com" |

### Step 2: Replace in Elementor JSON

The hardcoded values appear in HTML strings within the Elementor JSON. For example:

**Before:**
```html
<div class="gg-hero-title">The Mid South</div>
<span class="gg-hero-badge-loc">STILLWATER, OKLAHOMA</span>
<div class="gg-hero-score-main">85<span>/100</span></div>
```

**After:**
```html
<div class="gg-hero-title">{{RACE_DISPLAY_NAME}}</div>
<span class="gg-hero-badge-loc">{{LOCATION_BADGE}}</span>
<div class="gg-hero-score-main">{{RATING_SCORE}}<span>/100</span></div>
```

### Step 3: Update `push_pages.py` to Handle Nested Structure

The current `push_pages.py` expects flat fields like `RACE_NAME`, but the actual data has `race.name`. Update the `_build_replacements()` method to handle nested paths:

```python
def _build_replacements(self, race_data: Dict[str, Any]) -> Dict[str, str]:
    replacements = {}
    
    # Handle nested race data structure
    race = race_data.get('race', race_data)
    
    # Map nested paths to placeholders
    field_mappings = {
        '{{RACE_NAME}}': race.get('name', ''),
        '{{RACE_DISPLAY_NAME}}': race.get('display_name', race.get('name', '')),
        '{{LOCATION}}': race.get('vitals', {}).get('location', ''),
        '{{LOCATION_BADGE}}': race.get('vitals', {}).get('location_badge', ''),
        '{{DISTANCE}}': str(race.get('vitals', {}).get('distance_mi', '')),
        '{{ELEVATION_GAIN}}': str(race.get('vitals', {}).get('elevation_ft', '')),
        '{{RATING_SCORE}}': str(race.get('gravel_god_rating', {}).get('overall_score', '')),
        '{{TIER_LABEL}}': race.get('gravel_god_rating', {}).get('tier_label', ''),
        '{{TAGLINE}}': race.get('tagline', ''),
        '{{WEBSITE_URL}}': race.get('logistics', {}).get('official_site', ''),
    }
    
    return field_mappings
```

## Next Steps

1. **Use `convert_to_template.py`** to convert `elementor-mid-south.json`:
   ```bash
   python convert_to_template.py \
     ~/gravel-landing-page-project/output/elementor-mid-south.json \
     template.json \
     --race-name "The Mid South" \
     --location "Stillwater, Oklahoma"
   ```

2. **Manually review** the template to ensure all placeholders are correct (especially in HTML strings)

3. **Update `push_pages.py`** to handle the nested `race` structure from `mid-south-data.json`

4. **Test** with a few races from the database

