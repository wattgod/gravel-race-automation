# WordPress REST API Pipeline - Setup Guide

## Overview

This pipeline automates the creation of WordPress pages from a race database JSON file using Elementor templates and the WordPress REST API.

## Architecture

```
Race Database (JSON) + Template (JSON with placeholders)
                    ↓
              push_pages.py
                    ↓
         WordPress REST API
                    ↓
          400 Live Pages
```

## Files Created

1. **`push_pages.py`** - Main script to push pages to WordPress
2. **`convert_to_template.py`** - Helper to convert race JSON to template
3. **`template_example.json`** - Example template structure
4. **`race_database_example.json`** - Example race database structure
5. **`README_WORDPRESS.md`** - Usage documentation

## Setup Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `requests` - For WordPress REST API calls
- `python-dotenv` - For environment variable management

### 2. Configure WordPress Credentials

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your WordPress credentials:

```env
WORDPRESS_URL=https://your-site.com
WORDPRESS_USERNAME=your-username
WORDPRESS_PASSWORD=your-application-password
```

**Important:** Use WordPress Application Passwords, not your regular password:
- WordPress Admin → Users → Your Profile → Application Passwords
- Generate a new application password
- Use that password in `.env`

### 3. Prepare Your Template

#### Option A: Convert Existing Mid South JSON

If you have a Mid South race JSON file:

```bash
python convert_to_template.py mid_south.json template.json \
  --race-name "Mid South" \
  --location "Stillwater, OK"
```

This will:
- Replace "Mid South" with `{{RACE_NAME}}`
- Replace "Stillwater, OK" with `{{LOCATION}}`
- Auto-detect other fields and create placeholders

#### Option B: Create Template Manually

1. Design your page in Elementor
2. Export as JSON template
3. Replace specific content with placeholders:
   - `{{RACE_NAME}}` - Race name
   - `{{LOCATION}}` - Location
   - `{{DATE}}` - Date
   - `{{DISTANCE}}` - Distance
   - `{{ELEVATION_GAIN}}` - Elevation gain
   - `{{WEBSITE_URL}}` - Race website
   - `{{REGISTRATION_URL}}` - Registration link
   - `{{DESCRIPTION}}` - Short description
   - `{{COURSE_BREAKDOWN}}` - Detailed course info
   - `{{RACE_HISTORY}}` - Race history
   - `{{TRAINING_TIPS}}` - Training recommendations
   - `{{GEAR_RECOMMENDATIONS}}` - Gear recommendations

### 4. Prepare Race Database

Your race database JSON should have this structure:

```json
{
  "races": [
    {
      "RACE_NAME": "Mid South",
      "LOCATION": "Stillwater, OK",
      "DATE": "March 2025",
      "DISTANCE": "100 miles",
      "ELEVATION_GAIN": "6,000 ft",
      "WEBSITE_URL": "https://midsouthgravel.com",
      "REGISTRATION_URL": "https://midsouthgravel.com/register",
      "DESCRIPTION": "Short description...",
      "COURSE_BREAKDOWN": "Long detailed course breakdown...",
      "RACE_HISTORY": "Race history content...",
      "TRAINING_TIPS": "Training tips...",
      "GEAR_RECOMMENDATIONS": "Gear recommendations..."
    }
  ]
}
```

**Field Mapping:**
- Fields can be uppercase (`RACE_NAME`) or lowercase (`race_name`)
- Can be nested under `race_metadata` or `content` objects
- Script will search multiple locations automatically

## Usage

### Test Mode (First 3 Races)

```bash
python push_pages.py \
  --template template.json \
  --database race_database.json \
  --test
```

### Full Push

```bash
python push_pages.py \
  --template template.json \
  --database race_database.json
```

### With Command-Line Credentials

```bash
python push_pages.py \
  --template template.json \
  --database race_database.json \
  --url https://your-site.com \
  --username your-username \
  --password your-app-password
```

## Handling Long Content Blocks

### Strategy 1: Store in Database (Recommended)

Include full content in your race database:

```json
{
  "RACE_NAME": "Mid South",
  "COURSE_BREAKDOWN": "Full detailed course breakdown here... (can be very long)",
  "RACE_HISTORY": "Full race history here... (can be very long)"
}
```

**Pros:**
- Simple and straightforward
- Easy to edit and maintain
- Works well with placeholders

**Cons:**
- Large JSON files
- Need to manually update content

### Strategy 2: Generate Content Dynamically

Modify `push_pages.py` to generate content based on race metadata:

```python
def generate_course_breakdown(race_data):
    """Generate course breakdown from race metadata."""
    # Your generation logic here
    return f"Course breakdown for {race_data['RACE_NAME']}..."
```

**Pros:**
- Smaller database files
- Consistent formatting
- Can use templates for generation

**Cons:**
- Less flexible
- Requires code changes for different formats

### Strategy 3: Separate Content Files

Store long content in separate files:

```
races/
  mid_south.json (metadata)
  mid_south_course.txt (course breakdown)
  mid_south_history.txt (race history)
```

Then load and combine in `push_pages.py`.

## Elementor Template Structure

Your template JSON should include:

### Basic WordPress Fields

```json
{
  "title": "{{RACE_NAME}} - Gravel Race Guide",
  "status": "publish",
  "content": {
    "raw": "<p>Content here...</p>"
  }
}
```

### Elementor Meta Fields

```json
{
  "meta": {
    "_elementor_template_type": "wp-page",
    "_elementor_edit_mode": "builder",
    "_elementor_data": "[{\"id\":\"...\",\"settings\":{\"title\":\"{{RACE_NAME}}\"}}]"
  }
}
```

**Important:** Elementor data is stored as a JSON string in the `_elementor_data` meta field. The script automatically:
- Parses the JSON string
- Replaces placeholders recursively
- Re-encodes as JSON string

### ACF Fields (if using Advanced Custom Fields)

```json
{
  "acf": {
    "race_name": "{{RACE_NAME}}",
    "location": "{{LOCATION}}",
    "course_breakdown": "{{COURSE_BREAKDOWN}}"
  }
}
```

## Testing Checklist

After pushing test pages:

1. **Verify Pages Created**
   - Check WordPress admin → Pages
   - Confirm pages exist with correct titles

2. **Verify Elementor Rendering**
   - Open each page in Elementor editor
   - Check that all widgets render correctly
   - Verify placeholders were replaced

3. **Check Content Accuracy**
   - Verify race-specific data appears correctly
   - Check that long content blocks display properly
   - Test links (website URLs, registration URLs)

4. **Test Page URLs**
   - Visit live pages
   - Check permalinks are correct
   - Verify SEO settings if applicable

5. **Review Errors**
   - Check `push_results.json` for any errors
   - Fix template or database issues
   - Re-run failed pages

## Troubleshooting

### Error: "Failed to create page: 401"

**Solution:** Check your WordPress credentials:
- Verify application password is correct
- Ensure username matches WordPress username
- Check that REST API is enabled

### Error: "Failed to create page: 403"

**Solution:** Check user permissions:
- User must have `edit_pages` capability
- May need administrator role for Elementor pages

### Elementor Not Rendering

**Solution:** 
- Ensure `_elementor_data` is valid JSON
- Check that Elementor plugin is active
- Verify template type is correct (`wp-page`)

### Placeholders Not Replaced

**Solution:**
- Check placeholder format: `{{RACE_NAME}}` (double curly braces)
- Verify field names match between template and database
- Check that replacements are being built correctly (add debug prints)

## Next Steps

1. ✅ **Convert Mid South JSON → Template** - Use `convert_to_template.py`
2. ⏳ **Handle Long Content Blocks** - Choose strategy (database vs. generation)
3. ⏳ **Test Pipeline** - Push 3 test races, verify Elementor renders
4. ⏳ **Add Website URLs** - Update database with URLs for map scraper

## Resources

- [WordPress REST API Handbook](https://developer.wordpress.org/rest-api/)
- [Elementor Data Structure](https://developers.elementor.com/docs/data-structure/general-structure/)
- [WordPress Application Passwords](https://make.wordpress.org/core/2020/11/05/application-passwords-integration-guide/)

