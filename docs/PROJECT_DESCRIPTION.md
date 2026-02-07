# WordPress REST API Pipeline - Project Description

## Overview

This project automates the creation of WordPress pages from a race database JSON file using Elementor page builder templates and the WordPress REST API. The goal is to generate 400+ live race guide pages programmatically, replacing a manual Elementor workflow.

## Architecture

```
Race Database (JSON) + Elementor Template (JSON with placeholders)
                    ↓
              push_pages.py
                    ↓
         WordPress REST API
                    ↓
          400+ Live Pages
```

## Problem Statement

**Before:** Manual workflow where each race page was created individually in Elementor, requiring:
- Manual copy/paste of race data
- Manual replacement of race-specific content
- Time-consuming and error-prone for 400+ races

**After:** Automated pipeline that:
- Reads race data from JSON database
- Replaces placeholders in Elementor template
- Pushes pages to WordPress via REST API
- Publishes pages live with SEO metadata

## Key Components

### 1. `push_pages.py` - Main Script

**Purpose:** Core script that handles the entire pipeline from JSON to WordPress.

**Key Features:**
- **Placeholder Replacement:** Replaces `{{PLACEHOLDER}}` syntax in templates with actual race data
- **Elementor Integration:** Properly formats Elementor JSON data for WordPress REST API
- **SEO Automation:** Populates AIOSEO meta fields (title, description, OG tags)
- **Publishing:** Creates pages as published (not drafts) by default
- **Error Handling:** Comprehensive error handling and logging

**Main Classes:**
- `WordPressPagePusher`: Handles WordPress REST API communication and page creation

**Key Methods:**
- `replace_placeholders()`: Replaces `{{PLACEHOLDER}}` with actual values from race data
- `_build_replacements()`: Maps race data fields to placeholder names
- `create_page()`: Creates WordPress page via REST API
- `push_race_page()`: Main method that combines template + race data → WordPress page

### 2. `convert_to_template.py` - Template Converter

**Purpose:** Converts a specific race JSON (e.g., Mid South) into a reusable template by replacing hardcoded values with placeholders.

**Process:**
1. Takes an Elementor-exported JSON file (specific race)
2. Replaces race-specific content with placeholders:
   - "Mid South" → `{{RACE_NAME}}`
   - "Stillwater, Oklahoma" → `{{LOCATION}}`
   - Specific URLs → `{{WEBSITE_URL}}`
   - etc.
3. Outputs template JSON that can be reused for all races

### 3. Template Structure (`templates/template-master.json`)

**Format:** Elementor page export JSON with placeholders

**Structure:**
```json
{
  "content": [
    {
      "id": "{{ID}}",
      "elType": "section",
      "elements": [...],
      "settings": {
        "title": "{{RACE_NAME}}",
        "html": "<div>{{LOCATION}}</div>"
      }
    }
  ],
  "title": "{{TITLE}}",
  "page_settings": {...},
  "version": "{{VERSION}}"
}
```

**Key Points:**
- Elementor stores page structure as JSON in `content` array
- Each widget/section can contain placeholders
- Placeholders are replaced before sending to WordPress

### 4. Race Database (`~/gravel-landing-page-project/data/mid-south-data.json`)

**Format:** Nested JSON structure with race information

**Structure:**
```json
{
  "race": {
    "name": "Mid South",
    "display_name": "The Mid South",
    "vitals": {
      "location": "Stillwater, Oklahoma",
      "distance_mi": 100,
      "elevation_ft": 4500,
      "date": "2025-03-15"
    },
    "tagline": "Oklahoma's weather lottery...",
    "gravel_god_rating": {
      "overall_score": 85,
      "tier_label": "TIER 1"
    },
    "course_description": {
      "ridewithgps_id": 48969927,
      "ridewithgps_name": "Mid South 2026 100 Mile",
      "character": "Course breakdown text..."
    },
    "history": {
      "origin_story": "Race history text..."
    },
    "logistics": {
      "official_site": "https://www.midsouthgravel.com"
    }
  }
}
```

## Placeholder System

### Supported Placeholders

| Placeholder | Maps To | Example |
|------------|---------|---------|
| `{{RACE_NAME}}` | `race.name` | "Mid South" |
| `{{RACE_DISPLAY_NAME}}` | `race.display_name` | "The Mid South" |
| `{{LOCATION}}` | `race.vitals.location` | "Stillwater, Oklahoma" |
| `{{LOCATION_BADGE}}` | `race.vitals.location_badge` | "STILLWATER, OKLAHOMA" |
| `{{DATE}}` | `race.vitals.date_specific` | "March 15, 2025" |
| `{{DISTANCE}}` | `race.vitals.distance_mi` | "100 miles" |
| `{{ELEVATION_GAIN}}` | `race.vitals.elevation_ft` | "4500 ft" |
| `{{RATING_SCORE}}` | `race.gravel_god_rating.overall_score` | "85" |
| `{{TIER_LABEL}}` | `race.gravel_god_rating.tier_label` | "TIER 1" |
| `{{TAGLINE}}` | `race.tagline` | "Oklahoma's weather lottery..." |
| `{{WEBSITE_URL}}` | `race.logistics.official_site` | "https://..." |
| `{{MAP_EMBED_URL}}` | Generated from `ridewithgps_id` | "https://ridewithgps.com/embeds..." |
| `{{COURSE_BREAKDOWN}}` | `race.course_description.character` | Long text... |
| `{{RACE_HISTORY}}` | `race.history.origin_story` | Long text... |
| `{{DESCRIPTION}}` | `race.biased_opinion.summary` | Long text... |
| `{{TITLE}}` | Generated | "The Mid South - Gravel Race Guide" |

### Replacement Process

1. **Load Template:** Read template JSON with placeholders
2. **Load Race Data:** Read race database JSON
3. **Build Replacements:** Map race data fields to placeholder names
4. **Recursive Replacement:** Replace all `{{PLACEHOLDER}}` instances in:
   - Template title
   - Elementor JSON structure (nested in `content` array)
   - Page settings
   - Meta fields
5. **Format for WordPress:** Convert Elementor structure to WordPress REST API format

## WordPress REST API Integration

### Elementor Page Format

Elementor pages require specific meta fields:

```json
{
  "title": "The Mid South - Gravel Race Guide",
  "status": "publish",
  "content": "",  // Empty - Elementor uses its own data
  "meta": {
    "_elementor_template_type": "wp-page",
    "_elementor_edit_mode": "builder",
    "_elementor_data": "[{\"id\":\"...\",\"elType\":\"section\",...}]",  // JSON string
    "_elementor_version": "0.4",
    "_elementor_pro_version": "",
    "_elementor_css": "",
    "_elementor_page_settings": {...}  // Object, not string
  }
}
```

**Critical Points:**
- `_elementor_data` must be a JSON **string** (not object)
- `_elementor_page_settings` must be an **object** (not string)
- `content` field should be empty (Elementor renders from `_elementor_data`)
- Page must have `_elementor_template_type: "wp-page"` and `_elementor_edit_mode: "builder"`

### SEO Integration (AIOSEO)

Automatically populates SEO meta fields:

```json
{
  "meta": {
    "_aioseo_title": "The Mid South - Gravel Race Guide",
    "_aioseo_description": "Complete guide to The Mid South in Stillwater, Oklahoma...",
    "_aioseo_og_title": "...",
    "_aioseo_og_description": "...",
    "_aioseo_twitter_title": "...",
    "_aioseo_twitter_description": "..."
  }
}
```

## Workflow

### Step 1: Create Template

```bash
python convert_to_template.py \
  output/elementor-mid-south.json \
  templates/template-master.json \
  --race-name "Mid South" \
  --location "Stillwater, OK"
```

This converts a specific race page into a template with placeholders.

### Step 2: Push Pages

```bash
python push_pages.py \
  --template templates/template-master.json \
  --races ~/gravel-landing-page-project/data/mid-south-data.json
```

This:
1. Loads template and race data
2. Replaces all placeholders
3. Formats for WordPress REST API
4. Creates published page with SEO metadata

### Step 3: Verify

- Check WordPress admin → Pages
- Verify page is published (not draft)
- Check SEO fields are populated
- Open in Elementor editor to verify rendering

## Configuration

### WordPress Credentials

Set via environment variables or `config.py`:

```python
WP_CONFIG = {
    "site_url": "https://gravelgodcycling.com",
    "username": "your_wp_username",
    "app_password": "xxxx xxxx xxxx xxxx"  # Application password, not regular password
}
```

**Important:** Must use WordPress Application Passwords (not regular password):
- WordPress Admin → Users → Your Profile → Application Passwords
- Generate new password and use that

## Current Status

### ✅ Completed

1. Template conversion system (`convert_to_template.py`)
2. Placeholder replacement system
3. WordPress REST API integration
4. Elementor data formatting
5. SEO metadata population (AIOSEO)
6. Publishing (pages created as published, not drafts)
7. Nested JSON data structure support (`race.vitals.location`, etc.)

### 🔄 In Progress

1. Testing pipeline with multiple races
2. Verifying Elementor rendering (may require opening in Elementor editor once)

### ⏳ Pending

1. Scale to 400+ races
2. Add website URLs to database for map scraper
3. Handle edge cases (missing data, special characters, etc.)

## Known Issues & Solutions

### Issue: Elementor Shows Raw JSON Instead of Rendered Page

**Cause:** Elementor sometimes needs pages to be "activated" by opening in Elementor editor.

**Solution:** 
1. Open page in WordPress admin
2. Click "Edit with Elementor"
3. Click "Update" (even without changes)
4. This activates Elementor rendering

### Issue: Placeholders Not Replaced

**Check:**
- Placeholder format: `{{PLACEHOLDER}}` (double curly braces)
- Field names match between template and database
- Race data structure matches expected format

### Issue: SEO Fields Not Populated

**Verify:**
- AIOSEO plugin is active
- Meta fields are being sent correctly
- Check page meta in WordPress admin

## File Structure

```
Zwift Batcher/
├── push_pages.py              # Main script
├── convert_to_template.py     # Template converter
├── config.py                  # WordPress credentials
├── requirements.txt           # Python dependencies
├── templates/
│   └── template-master.json   # Elementor template with placeholders
├── push_results.json         # Results log
└── PROJECT_DESCRIPTION.md     # This file

~/gravel-landing-page-project/
└── data/
    └── mid-south-data.json    # Race database (nested structure)
```

## Dependencies

- `requests` - WordPress REST API calls
- `python-dotenv` - Environment variable management

## Usage Examples

### Test Connection
```bash
python push_pages.py --test-connection
```

### Dry Run (Preview Replacements)
```bash
python push_pages.py \
  --template templates/template-master.json \
  --races data/mid-south-data.json \
  --dry-run
```

### Push Single Race
```bash
python push_pages.py \
  --template templates/template-master.json \
  --races ~/gravel-landing-page-project/data/mid-south-data.json
```

### Delete Pages
```bash
python push_pages.py --delete-pages 4794 4795 4796
```

## Technical Details

### Elementor Data Structure

Elementor stores page structure as nested JSON:
- Sections → Columns → Widgets
- Each element has `id`, `elType`, `widgetType`, `settings`, `elements`
- Settings contain actual content (text, HTML, etc.)
- Placeholders can appear anywhere in this structure

### Replacement Algorithm

1. **Deep Copy:** Clone template to avoid modifying original
2. **Build Mapping:** Create `{"{{PLACEHOLDER}}": "value"}` dictionary
3. **Recursive Replace:** Walk through entire JSON structure (dicts, lists, strings)
4. **String Replacement:** For each string, replace all placeholder occurrences
5. **Elementor Special Handling:** Parse `_elementor_data` JSON string, replace, re-encode

### WordPress REST API Endpoints

- `POST /wp-json/wp/v2/pages` - Create page
- `GET /wp-json/wp/v2/pages/{id}` - Get page
- `DELETE /wp-json/wp/v2/pages/{id}?force=true` - Delete page
- `GET /wp-json/wp/v2/users/me` - Test authentication

## Future Enhancements

1. **Batch Processing:** Process multiple races at once
2. **Update Existing Pages:** Update pages instead of always creating new ones
3. **Error Recovery:** Retry failed pages, log errors
4. **Content Generation:** Generate course breakdowns/history from metadata
5. **Image Handling:** Upload and attach featured images
6. **Category/Tag Assignment:** Automatically assign categories and tags
7. **Scheduling:** Schedule pages to publish at specific dates

## Related Files

- `README_WORDPRESS.md` - User-facing documentation
- `WORDPRESS_SETUP_GUIDE.md` - Setup instructions
- `CONVERSION_GUIDE.md` - Template conversion guide
- `push_results.json` - Execution results log

