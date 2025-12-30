#!/usr/bin/env python3
"""
Generate Elementor-ready JSON from race brief.
"""

import argparse
import json
import os
import anthropic
from pathlib import Path


def load_json_schema():
    """Load JSON schema for Elementor format."""
    schema_path = Path("skills/json_schema.json")
    if schema_path.exists():
        return schema_path.read_text()
    else:
        # Fallback schema based on PROJECT_DESCRIPTION.md
        return json.dumps({
            "race": {
                "name": "Race Name",
                "display_name": "The Race Name",
                "vitals": {
                    "location": "City, State",
                    "distance_mi": 100,
                    "elevation_ft": 4500,
                    "date": "2026-03-15"
                },
                "tagline": "Race tagline",
                "gravel_god_rating": {
                    "overall_score": 85,
                    "tier_label": "TIER 1"
                },
                "course_description": {
                    "ridewithgps_id": 0,
                    "character": "Course breakdown"
                },
                "history": {
                    "origin_story": "Race history"
                },
                "logistics": {
                    "official_site": "https://..."
                }
            }
        }, indent=2)


def generate_json(input_path: str, output_path: str):
    """Generate JSON from brief."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    brief = Path(input_path).read_text()
    schema = load_json_schema()
    
    prompt = f"""
Convert this race brief into JSON matching the schema below.

BRIEF:

{brief}

SCHEMA:

{schema}

Output ONLY valid JSON, no markdown code blocks, no explanation. The JSON should be ready for WordPress/Elementor publishing.
"""

    print(f"Generating JSON from {input_path}...")
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    json_text = response.content[0].text.strip()
    
    # Clean up if wrapped in code blocks
    if json_text.startswith("```"):
        json_text = json_text.split("```")[1]
        if json_text.startswith("json"):
            json_text = json_text[4:]
        json_text = json_text.strip()
    
    # Validate JSON
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON: {e}")
        print(f"Raw output (first 500 chars): {json_text[:500]}")
        # Save anyway for debugging
        Path(output_path).write_text(json_text)
        raise ValueError(f"Generated JSON is invalid: {e}")
    
    # Basic structure validation
    if "race" not in data:
        raise ValueError("Generated JSON missing 'race' key")
    
    if "name" not in data.get("race", {}):
        raise ValueError("Generated JSON missing race.name")
    
    if not data["race"]["name"].strip():
        raise ValueError("Generated JSON has empty race.name")
    
    # Pretty print and save
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    print(f"✓ JSON saved to {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    
    generate_json(args.input, args.output)

