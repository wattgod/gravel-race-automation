# WordPress REST API Pipeline

Automated pipeline to push race pages from JSON database to WordPress via REST API.

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

## Setup

1. **Install dependencies:**
   ```bash
   pip install requests python-dotenv
   ```

2. **Configure WordPress credentials:**
   - Copy `.env.example` to `.env`
   - Add your WordPress URL, username, and application password
   - **Enable Application Passwords:**
     - If disabled by All-In-One Security plugin: WordPress Admin > All-In-One Security > User Login > Application Passwords (enable)
     - Or: WordPress Admin > Users > Your Profile > Application Passwords
   - Generate application password: Click "Add New Application Password" and copy the generated password

3. **Prepare your files:**
   - `race_database.json` - Your race database (see `race_database_example.json`)
   - `template.json` - Elementor page template with placeholders (see `template_example.json`)

## Usage

### Basic Usage
```bash
python push_pages.py --template template.json --database race_database.json
```

### Test Mode (first 3 races)
```bash
python push_pages.py --template template.json --database race_database.json --test
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

## Template Placeholders

Replace specific content in your template with these placeholders:

- `{{RACE_NAME}}` - Race name
- `{{LOCATION}}` - Race location
- `{{DATE}}` - Race date
- `{{DISTANCE}}` - Race distance
- `{{ELEVATION_GAIN}}` - Elevation gain
- `{{WEBSITE_URL}}` - Race website URL
- `{{REGISTRATION_URL}}` - Registration URL
- `{{DESCRIPTION}}` - Short description
- `{{COURSE_BREAKDOWN}}` - Detailed course breakdown (long content)
- `{{RACE_HISTORY}}` - Race history (long content)
- `{{TRAINING_TIPS}}` - Training recommendations
- `{{GEAR_RECOMMENDATIONS}}` - Gear recommendations

## Long Content Blocks

For long content blocks (course breakdown, race history), you have two options:

### Option 1: Store in Database (Recommended)
Include the full content in your race database JSON:
```json
{
  "RACE_NAME": "Mid South",
  "COURSE_BREAKDOWN": "Full detailed course breakdown here...",
  "RACE_HISTORY": "Full race history here..."
}
```

### Option 2: Generate Content
Modify `push_pages.py` to generate content dynamically based on race metadata.

## Elementor Template Structure

Your template JSON should include:
- Page title with `{{RACE_NAME}}`
- Elementor data (JSON) with placeholders in widget settings
- ACF fields (if using Advanced Custom Fields)
- Any other WordPress meta fields

## Testing

1. **Test with 3 races:**
   ```bash
   python push_pages.py --template template.json --database race_database.json --test
   ```

2. **Verify in WordPress:**
   - Check that pages were created
   - Verify Elementor renders correctly
   - Check that all placeholders were replaced
   - Test page URLs

3. **Fix issues:**
   - Check `push_results.json` for errors
   - Adjust template structure if needed
   - Verify placeholder names match database fields

## Next Steps

1. ✅ Convert Mid South JSON → Template (replace specific content with placeholders)
2. ⏳ Handle long content blocks (determine strategy)
3. ⏳ Test the pipeline (push 3 test races, verify Elementor renders)
4. ⏳ Add website URLs to database (for map scraper)

