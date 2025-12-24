"""
WordPress REST API Page Pusher

Takes race database JSON + template JSON and pushes pages to WordPress via REST API.
Replaces placeholders in template with race-specific data.
"""

import json
import requests
import os
from typing import Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

# Try to import config, fall back to env vars
try:
    from config import Config
    WP_CONFIG = Config.WP_CONFIG
except (ImportError, AttributeError):
    WP_CONFIG = {
        "site_url": os.getenv('WORDPRESS_URL', ''),
        "username": os.getenv('WORDPRESS_USERNAME', ''),
        "app_password": os.getenv('WORDPRESS_PASSWORD', ''),
    }


class WordPressPagePusher:
    def __init__(self, wordpress_url: str, username: str, password: str):
        """
        Initialize WordPress REST API client.
        
        Args:
            wordpress_url: Base URL of WordPress site (e.g., 'https://example.com')
            username: WordPress username or application password username
            password: WordPress application password (not regular password)
        """
        self.wordpress_url = wordpress_url.rstrip('/')
        self.api_url = f"{self.wordpress_url}/wp-json/wp/v2"
        self.auth = (username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        
    def replace_placeholders(self, template: Dict[str, Any], race_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replace placeholders in template with race-specific data.
        
        Handles:
        - Simple placeholders: {{RACE_NAME}}, {{LOCATION}}, etc.
        - Nested placeholders in Elementor JSON (parsed and replaced recursively)
        - Long content blocks (course breakdown, race history)
        - Converts Elementor template structure to WordPress REST API format
        
        Args:
            template: Template JSON with placeholders
            race_data: Race data from database
            
        Returns:
            Template with placeholders replaced, formatted for WordPress REST API
        """
        # Get replacement mapping from race_data
        replacements = self._build_replacements(race_data)
        
        # Deep copy to avoid modifying original
        result = json.loads(json.dumps(template))
        
        # Handle Elementor template structure
        # If template has 'content' array (Elementor structure), convert it
        if 'content' in result and isinstance(result['content'], list):
            # This is Elementor template format - convert to WordPress REST API format
            elementor_content = result['content']
            
            # Replace placeholders in Elementor content
            elementor_content = self._replace_in_dict(elementor_content, replacements)
            
            # Convert Elementor content to JSON string for _elementor_data
            elementor_data_str = json.dumps(elementor_content, ensure_ascii=False)
            
            # Set up meta fields for Elementor
            if 'meta' not in result:
                result['meta'] = {}
            
            # Elementor template type must be 'wp-page' (not from template)
            result['meta']['_elementor_template_type'] = 'wp-page'
            result['meta']['_elementor_edit_mode'] = 'builder'
            result['meta']['_elementor_data'] = elementor_data_str
            # Critical: Elementor needs _elementor_version to recognize the page
            result['meta']['_elementor_version'] = result.get('version', '0.4')
            # Elementor needs _elementor_pro_version if using Pro (empty string if not)
            result['meta']['_elementor_pro_version'] = ''
            # Elementor CSS - needed for proper rendering
            result['meta']['_elementor_css'] = ''
            
            # Set page_settings if present (must be object, not JSON string)
            if 'page_settings' in result:
                page_settings = result['page_settings']
                # Replace placeholders in page_settings
                page_settings = self._replace_in_dict(page_settings, replacements)
                result['meta']['_elementor_page_settings'] = page_settings
            
            # Clear the content array (WordPress will use Elementor data)
            # For Elementor pages, content should be empty string
            result['content'] = ''
            
            # Add AIOSEO meta fields for SEO
            race = race_data.get('race', race_data)
            race_name = race.get('display_name') or race.get('name', '')
            location = race.get('vitals', {}).get('location', '')
            tagline = race.get('tagline', '')
            
            # Build SEO title and description
            seo_title = f"{race_name} - Gravel Race Guide"
            seo_description = f"Complete guide to {race_name} in {location}. {tagline}" if tagline else f"Complete guide to {race_name} gravel race in {location}."
            
            # AIOSEO meta fields
            result['meta']['_aioseo_title'] = seo_title
            result['meta']['_aioseo_description'] = seo_description
            result['meta']['_aioseo_og_title'] = seo_title
            result['meta']['_aioseo_og_description'] = seo_description
            result['meta']['_aioseo_twitter_title'] = seo_title
            result['meta']['_aioseo_twitter_description'] = seo_description
        
        # Handle Elementor data if already in meta._elementor_data (string format)
        elif 'meta' in result and '_elementor_data' in result['meta']:
            elementor_data_str = result['meta']['_elementor_data']
            # Elementor data is stored as JSON string, need to parse and replace
            try:
                elementor_data = json.loads(elementor_data_str)
                elementor_data = self._replace_in_dict(elementor_data, replacements)
                result['meta']['_elementor_data'] = json.dumps(elementor_data, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                # If it's already a string with placeholders, replace directly
                for placeholder, value in replacements.items():
                    elementor_data_str = elementor_data_str.replace(placeholder, str(value))
                result['meta']['_elementor_data'] = elementor_data_str
        
        # Replace in all other fields recursively
        result = self._replace_in_dict(result, replacements)
        
        return result
    
    def _replace_in_dict(self, obj: Any, replacements: Dict[str, str]) -> Any:
        """
        Recursively replace placeholders in a dictionary/list structure.
        
        Args:
            obj: Object to process (dict, list, or str)
            replacements: Dict mapping placeholders to values
            
        Returns:
            Object with placeholders replaced
        """
        if isinstance(obj, dict):
            return {k: self._replace_in_dict(v, replacements) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_in_dict(item, replacements) for item in obj]
        elif isinstance(obj, str):
            result = obj
            for placeholder, value in replacements.items():
                result = result.replace(placeholder, str(value))
            return result
        else:
            return obj
    
    def _build_replacements(self, race_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Build replacement mapping from race_data.
        
        Maps placeholders like {{RACE_NAME}} to actual values.
        Handles both flat structure and nested 'race' structure from gravel-landing-page-project.
        """
        replacements = {}
        
        # Handle nested race structure (from gravel-landing-page-project)
        race = race_data.get('race', race_data)
        
        # Basic fields - try nested structure first, then flat
        field_mappings = {
            'RACE_NAME': (
                race.get('name') or
                race_data.get('RACE_NAME') or
                race_data.get('race_name') or
                ''
            ),
            'RACE_NAME_UPPER': (
                race.get('name', '').upper() or
                race_data.get('RACE_NAME', '').upper() or
                race_data.get('race_name', '').upper() or
                ''
            ),
            'RACE_DISPLAY_NAME': (
                race.get('display_name') or
                race.get('name') or
                race_data.get('RACE_DISPLAY_NAME') or
                ''
            ),
            'LOCATION': (
                race.get('vitals', {}).get('location') or
                race_data.get('LOCATION') or
                race_data.get('location') or
                ''
            ),
            'LOCATION_UPPER': (
                race.get('vitals', {}).get('location_badge') or
                race.get('vitals', {}).get('location', '').upper() or
                race_data.get('LOCATION_UPPER') or
                race_data.get('LOCATION', '').upper() or
                ''
            ),
            'LOCATION_BADGE': (
                race.get('vitals', {}).get('location_badge') or
                race.get('vitals', {}).get('location', '').upper() or
                race_data.get('LOCATION_BADGE') or
                ''
            ),
            'CITY': (
                race.get('vitals', {}).get('location', '').split(',')[0].strip() or
                race_data.get('CITY') or
                race_data.get('city') or
                ''
            ),
            'RACE_TAGLINE': (
                race.get('tagline') or
                race_data.get('RACE_TAGLINE') or
                race_data.get('tagline') or
                ''
            ),
            'MAP_EMBED_URL': (
                self._build_map_embed_url(race) or
                race_data.get('MAP_EMBED_URL') or
                race_data.get('map_embed_url') or
                ''
            ),
            'TITLE': (
                f"{race.get('display_name') or race.get('name', '')} - Gravel Race Guide"
                if (race.get('display_name') or race.get('name'))
                else (
                    f"{race_data.get('RACE_DISPLAY_NAME') or race_data.get('RACE_NAME', '')} - Gravel Race Guide"
                    if (race_data.get('RACE_DISPLAY_NAME') or race_data.get('RACE_NAME'))
                    else (race_data.get('TITLE') or '')
                )
            ),
            'DATE': (
                race.get('vitals', {}).get('date_specific') or
                race.get('vitals', {}).get('date') or
                race_data.get('DATE') or
                race_data.get('date') or
                ''
            ),
            'DISTANCE': (
                str(race.get('vitals', {}).get('distance_mi', '')) + ' miles' if race.get('vitals', {}).get('distance_mi') else
                race.get('vitals', {}).get('distance') or
                race_data.get('DISTANCE') or
                race_data.get('distance') or
                ''
            ),
            'ELEVATION_GAIN': (
                str(race.get('vitals', {}).get('elevation_ft', '')) + ' ft' if race.get('vitals', {}).get('elevation_ft') else
                race.get('vitals', {}).get('elevation') or
                race_data.get('ELEVATION_GAIN') or
                race_data.get('elevation_gain') or
                ''
            ),
            'RATING_SCORE': (
                str(race.get('gravel_god_rating', {}).get('overall_score', '')) or
                race_data.get('RATING_SCORE') or
                ''
            ),
            'TIER_LABEL': (
                race.get('gravel_god_rating', {}).get('tier_label') or
                race_data.get('TIER_LABEL') or
                ''
            ),
            'TAGLINE': (
                race.get('tagline') or
                race_data.get('TAGLINE') or
                race_data.get('tagline') or
                ''
            ),
            'RACE_TAGLINE': (
                race.get('tagline') or
                race_data.get('RACE_TAGLINE') or
                race_data.get('tagline') or
                ''
            ),
            'WEBSITE_URL': (
                race.get('logistics', {}).get('official_site') or
                race_data.get('WEBSITE_URL') or
                race_data.get('website_url') or
                ''
            ),
            'REGISTRATION_URL': (
                race.get('vitals', {}).get('registration') or
                race_data.get('REGISTRATION_URL') or
                race_data.get('registration_url') or
                ''
            ),
            'RACE_SLUG': (
                race.get('slug') or
                race_data.get('RACE_SLUG') or
                race_data.get('race_slug') or
                self._generate_slug(
                    race.get('name') or
                    race_data.get('RACE_NAME') or
                    race_data.get('race_name') or
                    ''
                )
            ),
        }

        # Add all field mappings to replacements
        for placeholder_name, value in field_mappings.items():
            replacements[f"{{{{{placeholder_name}}}}}"] = str(value) if value else ''
        
        # Handle template metadata placeholders
        # These are used in the template JSON structure itself
        if 'ID' not in replacements:
            replacements['{{ID}}'] = ''  # Elementor generates IDs automatically
        if 'VERSION' not in replacements:
            replacements['{{VERSION}}'] = '0.4'  # Elementor version
        if 'TYPE' not in replacements:
            replacements['{{TYPE}}'] = 'wp-page'  # WordPress page type

        # Elementor structural placeholders
        # These should ideally be in the template correctly, but we provide defaults
        elementor_defaults = {
            '{{ELTYPE}}': 'widget',  # Most common - sections/columns don't usually have this placeholder
            '{{WIDGETTYPE}}': 'html',  # Most widgets in this template are HTML widgets
            '{{LAYOUT}}': 'full_width',
            '{{HEIGHT}}': 'default',
            '{{CSS_CLASSES}}': '',
            '{{_CSS_CLASSES}}': '',
            '{{_ELEMENT_ID}}': '',
            '{{_ELEMENT_WIDTH}}': 'auto',
            '{{UNIT}}': '%',
            '{{STRETCH_SECTION}}': '',
            '{{GAP}}': 'default',
            '{{TOP}}': '',
            '{{RIGHT}}': '',
            '{{BOTTOM}}': '',
            '{{LEFT}}': '',
        }
        replacements.update(elementor_defaults)
        
        # Handle long content blocks
        long_content_fields = {
            'COURSE_BREAKDOWN': (
                race.get('course_description', {}).get('character') or
                race_data.get('COURSE_BREAKDOWN') or
                race_data.get('course_breakdown') or
                ''
            ),
            'RACE_HISTORY': (
                race.get('history', {}).get('origin_story') or
                race_data.get('RACE_HISTORY') or
                race_data.get('race_history') or
                ''
            ),
            'DESCRIPTION': (
                race.get('biased_opinion', {}).get('summary') or
                race_data.get('DESCRIPTION') or
                race_data.get('description') or
                ''
            ),
        }
        
        for placeholder_name, value in long_content_fields.items():
            replacements[f"{{{{{placeholder_name}}}}}"] = str(value) if value else ''
        
        return replacements
    
    def _build_map_embed_url(self, race: Dict[str, Any]) -> str:
        """
        Build RideWithGPS embed URL from race data.
        
        Args:
            race: Race data dictionary
            
        Returns:
            Full embed URL or empty string
        """
        rwgps_id = race.get('course_description', {}).get('ridewithgps_id')
        rwgps_name = race.get('course_description', {}).get('ridewithgps_name')
        
        if rwgps_id:
            # Build embed URL
            base_url = 'https://ridewithgps.com/embeds?type=route'
            params = [
                f'id={rwgps_id}',
                'sampleGraph=true',
                'distanceMarkers=true'
            ]
            
            if rwgps_name:
                params.insert(1, f'title={rwgps_name}')
            
            return f"{base_url}&{'&'.join(params)}"
        
        return ''

    def _generate_slug(self, name: str) -> str:
        """
        Generate a URL-friendly slug from a race name.

        Args:
            name: Race name (e.g., "Mid South", "Unbound 200")

        Returns:
            URL-friendly slug (e.g., "mid-south", "unbound-200")
        """
        import re

        if not name:
            return ''

        # Convert to lowercase
        slug = name.lower()

        # Remove apostrophes and quotes
        slug = slug.replace("'", "").replace('"', '')

        # Replace spaces and underscores with hyphens
        slug = slug.replace(' ', '-').replace('_', '-')

        # Remove any characters that aren't alphanumeric or hyphens
        slug = re.sub(r'[^a-z0-9-]', '', slug)

        # Collapse multiple hyphens into single hyphen
        slug = re.sub(r'-+', '-', slug)

        # Remove leading/trailing hyphens
        slug = slug.strip('-')

        return slug

    def test_connection(self) -> bool:
        """
        Test WordPress REST API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            url = f"{self.api_url}/users/me"
            response = self.session.get(url)
            
            if response.status_code == 200:
                user_data = response.json()
                print(f"✓ Connection successful!")
                print(f"  Site: {self.wordpress_url}")
                print(f"  User: {user_data.get('name', 'Unknown')} ({user_data.get('slug', 'Unknown')})")
                return True
            else:
                print(f"✗ Connection failed: {response.status_code}")
                print(f"  {response.text}")
                return False
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False
    
    def create_page(self, page_data: Dict[str, Any], regenerate_css: bool = True) -> Dict[str, Any]:
        """
        Create a WordPress page via REST API.

        Handles Elementor pages by properly formatting meta fields.
        Creates pages as published by default.
        Automatically regenerates Elementor CSS after creation.

        Args:
            page_data: Page data including title, content, Elementor data, etc.
            regenerate_css: If True, regenerate Elementor CSS after creation (default: True)

        Returns:
            Created page data from WordPress API
        """
        url = f"{self.api_url}/pages"

        # Format page data for WordPress REST API
        formatted_data = self._format_page_data(page_data)

        # Ensure page is created as published (unless explicitly set)
        if 'status' not in formatted_data:
            formatted_data['status'] = 'publish'

        response = self.session.post(url, json=formatted_data)

        # Better error handling
        if response.status_code not in [200, 201]:
            error_msg = f"Failed to create page: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {response.text}"
            raise Exception(error_msg)

        result = response.json()

        # Regenerate Elementor CSS for the new page
        # This is necessary because Elementor doesn't auto-generate CSS via REST API
        if regenerate_css and result.get('id'):
            self.regenerate_elementor_css(result['id'])

        return result
    
    def _format_page_data(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format page data for WordPress REST API.
        
        Handles:
        - Title (can be string or dict with 'rendered' key)
        - Content (can be string or dict with 'raw'/'rendered' keys)
        - Meta fields (Elementor data, ACF fields, etc.)
        
        Args:
            page_data: Raw page data
            
        Returns:
            Formatted page data for REST API
        """
        formatted = {}
        
        # Handle title
        if 'title' in page_data:
            if isinstance(page_data['title'], dict):
                formatted['title'] = page_data['title'].get('rendered', '')
            else:
                formatted['title'] = str(page_data['title'])
        
        # Handle content
        # For Elementor pages, content should be empty or minimal HTML
        if 'content' in page_data:
            if isinstance(page_data['content'], dict):
                formatted['content'] = page_data['content'].get('raw', page_data['content'].get('rendered', ''))
            elif isinstance(page_data['content'], list):
                # If content is a list (Elementor structure), it should be empty
                # The Elementor data is in meta._elementor_data
                formatted['content'] = ''
            else:
                formatted['content'] = str(page_data['content'])
        
        # Handle status (default to publish for live pages)
        formatted['status'] = page_data.get('status', 'publish')
        
        # Handle meta fields (Elementor, ACF, etc.)
        # WordPress REST API requires meta fields to be sent with proper structure
        if 'meta' in page_data:
            formatted['meta'] = {}
            for key, value in page_data['meta'].items():
                # Special handling for Elementor fields
                if key == '_elementor_data':
                    # Must be JSON string
                    if isinstance(value, (dict, list)):
                        formatted['meta'][key] = json.dumps(value, ensure_ascii=False)
                    else:
                        formatted['meta'][key] = str(value)
                elif key == '_elementor_page_settings':
                    # Must be object (dict), not JSON string
                    if isinstance(value, str):
                        try:
                            formatted['meta'][key] = json.loads(value)
                        except:
                            formatted['meta'][key] = {}
                    elif isinstance(value, dict):
                        formatted['meta'][key] = value
                    else:
                        formatted['meta'][key] = {}
                else:
                    # Other meta fields as-is
                    formatted['meta'][key] = value
        
        # Handle ACF fields (if using ACF plugin)
        if 'acf' in page_data:
            # ACF fields need to be sent via meta with 'acf_' prefix
            if 'meta' not in formatted:
                formatted['meta'] = {}
            for key, value in page_data['acf'].items():
                formatted['meta'][f'acf_{key}'] = value
        
        # Copy other fields
        for key in ['excerpt', 'slug', 'parent', 'menu_order', 'comment_status', 
                    'ping_status', 'template', 'featured_media']:
            if key in page_data:
                formatted[key] = page_data[key]
        
        return formatted
    
    def get_page(self, page_id: int) -> Dict[str, Any]:
        """
        Retrieve a WordPress page by ID.
        
        Args:
            page_id: Page ID to retrieve
            
        Returns:
            Page data from WordPress API
        """
        url = f"{self.api_url}/pages/{page_id}"
        response = self.session.get(url)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get page {page_id}: {response.status_code} - {response.text}")
    
    def regenerate_elementor_css(self, page_id: int) -> Dict[str, Any]:
        """
        Regenerate Elementor CSS for a page after creation via REST API.

        This is necessary because Elementor doesn't automatically generate CSS
        when pages are created via REST API - it only generates CSS when saving
        through the Elementor editor.

        Requires the 'elementor-css-regenerator' plugin to be installed on WordPress.

        Args:
            page_id: WordPress page ID

        Returns:
            Response from the regeneration endpoint
        """
        url = f"{self.wordpress_url}/wp-json/gravel-god/v1/regenerate-css/{page_id}"

        try:
            response = self.session.post(url)

            if response.status_code == 200:
                result = response.json()
                print(f"  ✓ CSS regenerated for page {page_id}")
                return result
            elif response.status_code == 404:
                print(f"  ⚠ CSS regeneration endpoint not found - is the plugin installed?")
                return {'success': False, 'error': 'Plugin not installed'}
            else:
                error_msg = f"CSS regeneration failed: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail.get('message', response.text)}"
                except:
                    error_msg += f" - {response.text}"
                print(f"  ⚠ {error_msg}")
                return {'success': False, 'error': error_msg}
        except Exception as e:
            print(f"  ⚠ CSS regeneration error: {e}")
            return {'success': False, 'error': str(e)}

    def regenerate_elementor_css_bulk(self, page_ids: List[int]) -> Dict[str, Any]:
        """
        Regenerate Elementor CSS for multiple pages at once.

        Args:
            page_ids: List of WordPress page IDs

        Returns:
            Response from the bulk regeneration endpoint
        """
        url = f"{self.wordpress_url}/wp-json/gravel-god/v1/regenerate-css-bulk"

        try:
            response = self.session.post(url, json={'post_ids': page_ids})

            if response.status_code == 200:
                result = response.json()
                print(f"  ✓ Bulk CSS regeneration: {result.get('success_count', 0)} succeeded, {result.get('error_count', 0)} failed")
                return result
            else:
                error_msg = f"Bulk CSS regeneration failed: {response.status_code}"
                print(f"  ⚠ {error_msg}")
                return {'success': False, 'error': error_msg}
        except Exception as e:
            print(f"  ⚠ Bulk CSS regeneration error: {e}")
            return {'success': False, 'error': str(e)}

    def delete_page(self, page_id: int, force: bool = True) -> bool:
        """
        Delete a WordPress page via REST API.
        
        Args:
            page_id: Page ID to delete
            force: If True, permanently delete (bypass trash)
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{self.api_url}/pages/{page_id}"
        params = {'force': force} if force else {}
        
        response = self.session.delete(url, params=params)
        
        if response.status_code in [200, 202]:
            return True
        else:
            print(f"Failed to delete page {page_id}: {response.status_code} - {response.text}")
            return False
    
    def update_page(self, page_id: int, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing WordPress page.
        
        Args:
            page_id: WordPress page ID
            page_data: Updated page data
            
        Returns:
            Updated page data from WordPress API
        """
        url = f"{self.api_url}/pages/{page_id}"
        
        response = self.session.post(url, json=page_data)
        response.raise_for_status()
        
        return response.json()
    
    def push_race_page(self, race_data: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Push a single race page to WordPress.
        
        Args:
            race_data: Race data from database
            template: Template JSON with placeholders
            
        Returns:
            Created/updated page data
        """
        # Replace placeholders
        page_data = self.replace_placeholders(template, race_data)
        
        # Create or update page
        if page_data.get('id'):
            # Update existing page
            return self.update_page(page_data['id'], page_data)
        else:
            # Create new page
            return self.create_page(page_data)
    
    def dry_run(self, races: List[Dict[str, Any]], template: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Dry run: show what would be replaced without actually pushing to WordPress.
        
        Args:
            races: List of race data dictionaries
            template: Template JSON with placeholders
            
        Returns:
            List of replacement previews
        """
        results = []
        
        for race_data in races:
            try:
                # Get race name for display
                race = race_data.get('race', race_data)
                race_name = race.get('name') or race_data.get('RACE_NAME') or race_data.get('race_name', 'Unknown')
                
                # Build replacements
                replacements = self._build_replacements(race_data)
                
                # Show what would be replaced
                print(f"\n{'='*60}")
                print(f"📄 Race: {race_name}")
                print(f"{'='*60}")
                print(f"\n🔍 Placeholder Replacements:")
                for placeholder, value in sorted(replacements.items()):
                    if value:  # Only show non-empty replacements
                        # Truncate long values for display
                        display_value = value[:100] + "..." if len(value) > 100 else value
                        print(f"  {placeholder:30} → {display_value}")
                
                # Count placeholders found in template
                template_str = json.dumps(template)
                found_placeholders = [p for p in replacements.keys() if p in template_str]
                missing_placeholders = [p for p in replacements.keys() if p not in template_str]
                
                print(f"\n📊 Template Analysis:")
                print(f"  ✓ Placeholders found in template: {len(found_placeholders)}")
                if missing_placeholders:
                    print(f"  ⚠ Placeholders not found in template: {len(missing_placeholders)}")
                    for p in missing_placeholders[:5]:  # Show first 5
                        print(f"    - {p}")
                
                results.append({
                    'race': race_name,
                    'status': 'preview',
                    'replacements': {k: v[:50] + "..." if len(v) > 50 else v for k, v in replacements.items() if v},
                    'found_placeholders': len(found_placeholders),
                    'missing_placeholders': len(missing_placeholders)
                })
                
            except Exception as e:
                results.append({
                    'race': race_data.get('race', {}).get('name', 'Unknown'),
                    'status': 'error',
                    'error': str(e)
                })
                print(f"✗ Error processing race: {e}")
        
        return results
    
    def batch_push(self, races: List[Dict[str, Any]], template: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Push multiple race pages.
        
        Args:
            races: List of race data dictionaries
            template: Template JSON with placeholders
            
        Returns:
            List of created/updated page data
        """
        results = []
        
        for race_data in races:
            try:
                result = self.push_race_page(race_data, template)
                race = race_data.get('race', race_data)
                race_name = race.get('name') or race_data.get('RACE_NAME') or race_data.get('race_name', 'Unknown')
                results.append({
                    'race': race_name,
                    'status': 'success',
                    'page_id': result.get('id'),
                    'page_url': result.get('link')
                })
                print(f"✓ Pushed: {result.get('title', {}).get('rendered', 'Unknown')}")
            except Exception as e:
                race = race_data.get('race', race_data)
                race_name = race.get('name') or race_data.get('RACE_NAME') or race_data.get('race_name', 'Unknown')
                results.append({
                    'race': race_name,
                    'status': 'error',
                    'error': str(e)
                })
                print(f"✗ Error pushing race: {e}")
        
        return results


def load_template(template_path: str) -> Dict[str, Any]:
    """Load template JSON file."""
    with open(template_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_race_database(db_path: str) -> List[Dict[str, Any]]:
    """Load race database JSON file."""
    with open(db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Handle both list and dict formats
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and 'races' in data:
            return data['races']
        elif isinstance(data, dict) and 'race' in data:
            # Handle single race wrapped in 'race' key (from gravel-landing-page-project)
            return [data]
        else:
            return [data]


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Push race pages to WordPress')
    parser.add_argument('--template', help='Path to template JSON file')
    parser.add_argument('--database', help='Path to race database JSON file (deprecated, use --races)')
    parser.add_argument('--races', help='Path to race data JSON file')
    parser.add_argument('--url', help='WordPress URL (or set WORDPRESS_URL env var)')
    parser.add_argument('--username', help='WordPress username (or set WORDPRESS_USERNAME env var)')
    parser.add_argument('--password', help='WordPress app password (or set WORDPRESS_PASSWORD env var)')
    parser.add_argument('--test', action='store_true', help='Test mode: only push first 3 races')
    parser.add_argument('--dry-run', action='store_true', help='Dry run: show replacements without pushing')
    parser.add_argument('--test-connection', action='store_true', help='Test WordPress connection only')
    parser.add_argument('--delete-pages', nargs='+', type=int, metavar='ID', help='Delete pages by ID (e.g., --delete-pages 4794 4795 4796)')
    
    args = parser.parse_args()
    
    # Delete pages mode
    if args.delete_pages:
        wordpress_url = args.url or os.getenv('WORDPRESS_URL') or WP_CONFIG.get('site_url')
        username = args.username or os.getenv('WORDPRESS_USERNAME') or WP_CONFIG.get('username')
        password = args.password or os.getenv('WORDPRESS_PASSWORD') or WP_CONFIG.get('app_password')
        
        if not all([wordpress_url, username, password]):
            print("✗ Error: WordPress credentials required (--url, --username, --password or env vars)")
            return
        
        pusher = WordPressPagePusher(wordpress_url, username, password)
        print(f"🗑️  Deleting {len(args.delete_pages)} pages...")
        for page_id in args.delete_pages:
            if pusher.delete_page(page_id):
                print(f"✓ Deleted page {page_id}")
            else:
                print(f"✗ Failed to delete page {page_id}")
        return
    
    # Test connection mode (doesn't require template)
    if args.test_connection:
        # Get credentials from args, env, or config
        wordpress_url = args.url or os.getenv('WORDPRESS_URL') or WP_CONFIG.get('site_url')
        username = args.username or os.getenv('WORDPRESS_USERNAME') or WP_CONFIG.get('username')
        password = args.password or os.getenv('WORDPRESS_PASSWORD') or WP_CONFIG.get('app_password')
        
        if not all([wordpress_url, username, password]):
            print("✗ Missing credentials. Provide via:")
            print("  - Command line: --url, --username, --password")
            print("  - Environment: WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD")
            print("  - config.py: WP_CONFIG dictionary")
            return
        
        pusher = WordPressPagePusher(wordpress_url, username, password)
        success = pusher.test_connection()
        exit(0 if success else 1)
    
    # Template and database are required for actual push
    if not args.template:
        raise ValueError("Must provide --template argument (or use --test-connection to test credentials)")
    
    # Load template and database
    template = load_template(args.template)
    race_file = args.races or args.database
    if not race_file:
        raise ValueError("Must provide --races or --database argument")
    races = load_race_database(race_file)
    
    # Test mode: only first 3
    if args.test:
        races = races[:3]
        print(f"🧪 TEST MODE: Processing {len(races)} races")
    
    # Dry run mode
    if args.dry_run:
        print(f"🔍 DRY RUN MODE: Previewing replacements for {len(races)} race(s)...")
        print(f"   (No pages will be pushed to WordPress)\n")
        
        # Create a dummy pusher just for dry run (no credentials needed)
        pusher = WordPressPagePusher('https://dummy.com', 'dummy', 'dummy')
        results = pusher.dry_run(races, template)
        
        print(f"\n{'='*60}")
        print(f"📊 Dry Run Summary:")
        print(f"{'='*60}")
        for result in results:
            if result['status'] == 'preview':
                print(f"  ✓ {result['race']}: {result['found_placeholders']} placeholders found")
            else:
                print(f"  ✗ {result['race']}: {result.get('error', 'Unknown error')}")
        
        # Save results
        with open('dry_run_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Dry run results saved to dry_run_results.json")
        return
    
    # Get credentials from args, env, or config (required for actual push)
    wordpress_url = args.url or os.getenv('WORDPRESS_URL') or WP_CONFIG.get('site_url')
    username = args.username or os.getenv('WORDPRESS_USERNAME') or WP_CONFIG.get('username')
    password = args.password or os.getenv('WORDPRESS_PASSWORD') or WP_CONFIG.get('app_password')
    
    if not all([wordpress_url, username, password]):
        raise ValueError(
            "Must provide WordPress URL, username, and password via:\n"
            "  - Command line: --url, --username, --password\n"
            "  - Environment: WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_PASSWORD\n"
            "  - config.py: WP_CONFIG dictionary"
        )
    
    # Initialize pusher
    pusher = WordPressPagePusher(wordpress_url, username, password)
    
    # Push pages
    print(f"🚀 Pushing {len(races)} race pages to WordPress...")
    results = pusher.batch_push(races, template)
    
    # Print summary
    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = sum(1 for r in results if r['status'] == 'error')
    
    print(f"\n📊 Summary:")
    print(f"  ✓ Success: {success_count}")
    print(f"  ✗ Errors: {error_count}")
    
    # Save results
    with open('push_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to push_results.json")


if __name__ == '__main__':
    main()

