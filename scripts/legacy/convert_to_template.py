"""
Convert Mid South (or any race) JSON to Template

Takes a specific race JSON file and converts it to a template by replacing
race-specific content with placeholders.
"""

import json
import re
from typing import Dict, Any, List


class TemplateConverter:
    def __init__(self, race_specific_terms: Dict[str, str] = None):
        """
        Initialize converter with race-specific terms to replace.
        
        Args:
            race_specific_terms: Dict mapping specific terms to placeholders
                e.g., {"Mid South": "{{RACE_NAME}}", "Stillwater": "{{LOCATION}}"}
        """
        self.race_specific_terms = race_specific_terms or {}
        
        # Common placeholders
        self.placeholder_map = {
            'RACE_NAME': ['race name', 'race', 'event'],
            'LOCATION': ['location', 'city', 'town', 'place'],
            'DATE': ['date', 'when'],
            'DISTANCE': ['distance', 'miles', 'km'],
            'ELEVATION_GAIN': ['elevation', 'climbing', 'vertical'],
            'WEBSITE_URL': ['website', 'url', 'site'],
            'REGISTRATION_URL': ['registration', 'register', 'signup'],
            'DESCRIPTION': ['description', 'about', 'overview'],
            'COURSE_BREAKDOWN': ['course', 'route', 'breakdown'],
            'RACE_HISTORY': ['history', 'background', 'founded'],
            'TRAINING_TIPS': ['training', 'tips', 'preparation'],
            'GEAR_RECOMMENDATIONS': ['gear', 'equipment', 'recommendations']
        }
    
    def detect_placeholders(self, text: str) -> List[str]:
        """
        Detect what placeholders might be needed based on text content.
        
        Returns list of suggested placeholder names.
        """
        detected = []
        text_lower = text.lower()
        
        for placeholder, keywords in self.placeholder_map.items():
            if any(keyword in text_lower for keyword in keywords):
                detected.append(placeholder)
        
        return detected
    
    def replace_specific_terms(self, text: str) -> str:
        """
        Replace race-specific terms with placeholders.
        
        Uses targeted replacements - longer strings first, simple string.replace().
        
        Args:
            text: Text containing race-specific terms
            
        Returns:
            Text with placeholders
        """
        result = text
        
        # Targeted replacements - order matters: longer strings first
        REPLACEMENTS = [
            # Map URL (full embed)
            ('https://ridewithgps.com/embeds?type=route&id=48969927&title=Mid%20South%202026%20100%20Mile&sampleGraph=true&distanceMarkers=true', '{{MAP_EMBED_URL}}'),
            
            # Race name (longer first)
            ('THE MID SOUTH', '{{RACE_NAME_UPPER}}'),
            ('The Mid South', '{{RACE_NAME}}'),
            
            # Location (longer first)
            ('STILLWATER, OKLAHOMA', '{{LOCATION_UPPER}}'),
            ('Stillwater, Oklahoma', '{{LOCATION}}'),
            ('Stillwater, OK', '{{LOCATION}}'),
            
            # Tagline
            ("Oklahoma's weather lottery with a $100K prize purse and a guaranteed Bobby hug.", '{{RACE_TAGLINE}}'),
            
            # Distance
            ('100 MILES OF STILLWATER', '{{DISTANCE}} MILES OF {{CITY}}'),
            ('100 miles of', '{{DISTANCE}} miles of'),
            
            # Title
            ('"The Mid South Landing Page"', '"{{RACE_NAME}} Landing Page"'),
        ]
        
        # Apply targeted replacements (simple string.replace, order matters)
        for old_text, new_text in REPLACEMENTS:
            result = result.replace(old_text, new_text)
        
        # Also replace known race-specific terms from initialization
        for term, placeholder in self.race_specific_terms.items():
            result = result.replace(term, placeholder)
        
        return result
    
    def convert_value_to_placeholder(self, key: str, value: Any) -> tuple[str, str]:
        """
        Convert a key-value pair to a placeholder.
        
        Returns:
            (placeholder_name, placeholder_string)
        """
        key_upper = key.upper()
        
        # Try to match key to known placeholders
        for placeholder, keywords in self.placeholder_map.items():
            if any(keyword in key.lower() for keyword in keywords):
                return placeholder, f"{{{{{placeholder}}}}}"
        
        # If no match, create placeholder from key
        placeholder_name = key_upper.replace(' ', '_').replace('-', '_')
        return placeholder_name, f"{{{{{placeholder_name}}}}}"
    
    def convert_dict(self, data: Dict[str, Any], path: str = '') -> Dict[str, Any]:
        """
        Recursively convert a dictionary, replacing values with placeholders.
        
        Args:
            data: Dictionary to convert
            path: Current path in the structure (for debugging)
            
        Returns:
            Converted dictionary with placeholders
        """
        result = {}
        
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            
            if isinstance(value, dict):
                # Recursively process nested dicts
                result[key] = self.convert_dict(value, current_path)
            elif isinstance(value, list):
                # Process lists
                result[key] = [
                    self.convert_dict(item, f"{current_path}[{i}]") if isinstance(item, dict)
                    else self.replace_specific_terms(str(item)) if isinstance(item, str)
                    else item
                    for i, item in enumerate(value)
                ]
            elif isinstance(value, str):
                # Replace specific terms and check if entire value should be placeholder
                if self._should_be_placeholder(key, value):
                    _, placeholder = self.convert_value_to_placeholder(key, value)
                    result[key] = placeholder
                else:
                    # Replace specific terms but keep structure
                    result[key] = self.replace_specific_terms(value)
            else:
                # Keep non-string values as-is (numbers, booleans, etc.)
                result[key] = value
        
        return result
    
    def _should_be_placeholder(self, key: str, value: str) -> bool:
        """
        Determine if a value should be completely replaced with a placeholder.
        
        Simple values (like race name, location) should be full placeholders.
        Long content blocks should have terms replaced but keep structure.
        """
        # Keys that should be full placeholders
        full_placeholder_keys = [
            'race_name', 'name', 'location', 'city', 'date', 
            'distance', 'elevation', 'website', 'url', 'registration'
        ]
        
        if any(k in key.lower() for k in full_placeholder_keys):
            return True
        
        # Short values are likely placeholders
        if len(value) < 100:
            return True
        
        return False
    
    def convert_file(self, input_path: str, output_path: str, 
                    race_specific_terms: Dict[str, str] = None):
        """
        Convert a race JSON file to a template.
        
        Args:
            input_path: Path to input race JSON file
            output_path: Path to save template JSON file
            race_specific_terms: Optional override for race-specific terms
        """
        # Load input file
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Update race-specific terms if provided
        if race_specific_terms:
            self.race_specific_terms = race_specific_terms
        
        # Auto-detect race-specific terms if not provided
        if not self.race_specific_terms:
            self.race_specific_terms = self._auto_detect_terms(data)
        
        # Convert data
        template = self.convert_dict(data)
        
        # Save template
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Converted {input_path} → {output_path}")
        print(f"  Detected race-specific terms: {self.race_specific_terms}")
        
        return template
    
    def _auto_detect_terms(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Auto-detect race-specific terms from the data.
        
        Looks for common patterns like race name, location, etc.
        """
        terms = {}
        
        # Common field names
        field_mappings = {
            'race_name': 'RACE_NAME',
            'name': 'RACE_NAME',
            'location': 'LOCATION',
            'city': 'LOCATION',
            'date': 'DATE',
            'distance': 'DISTANCE',
            'elevation': 'ELEVATION_GAIN',
            'website': 'WEBSITE_URL',
            'url': 'WEBSITE_URL'
        }
        
        def extract_terms(obj, path=''):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, str) and len(value) < 200:
                        # Check if this looks like a race name or location
                        if key.lower() in ['race_name', 'name']:
                            terms[value] = '{{RACE_NAME}}'
                        elif key.lower() in ['location', 'city', 'town']:
                            terms[value] = '{{LOCATION}}'
                    extract_terms(value, current_path)
            elif isinstance(obj, list):
                for item in obj:
                    extract_terms(item, path)
        
        extract_terms(data)
        
        return terms


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convert race JSON to template with placeholders'
    )
    parser.add_argument('input', help='Input race JSON file (e.g., mid_south.json)')
    parser.add_argument('output', help='Output template JSON file (e.g., template.json)')
    parser.add_argument('--race-name', help='Race name to replace (e.g., "Mid South")')
    parser.add_argument('--location', help='Location to replace (e.g., "Stillwater, OK")')
    
    args = parser.parse_args()
    
    # Build race-specific terms
    race_terms = {}
    if args.race_name:
        race_terms[args.race_name] = '{{RACE_NAME}}'
    if args.location:
        race_terms[args.location] = '{{LOCATION}}'
    
    # Convert
    converter = TemplateConverter(race_terms)
    converter.convert_file(args.input, args.output, race_terms)
    
    print(f"\n✓ Template created: {args.output}")
    print(f"  Review the template and adjust placeholders as needed.")
    print(f"  Long content blocks may need manual review.")


if __name__ == '__main__':
    main()

