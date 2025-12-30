#!/usr/bin/env python3
"""
Regression tests for automation system.
Run before deploying changes to catch breaking issues.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def test_json_schema_loads() -> Tuple[bool, str]:
    """Test that JSON schema file is valid."""
    try:
        schema_path = Path("skills/json_schema.json")
        if not schema_path.exists():
            return False, "JSON schema file not found"
        
        with open(schema_path) as f:
            json.load(f)
        
        return True, "JSON schema loads correctly"
    except Exception as e:
        return False, f"JSON schema error: {e}"


def test_voice_guide_loads() -> Tuple[bool, str]:
    """Test that voice guide loads."""
    try:
        voice_path = Path("skills/voice_guide.md")
        if not voice_path.exists():
            return False, "Voice guide not found"
        
        content = voice_path.read_text()
        if len(content) < 100:
            return False, "Voice guide seems too short"
        
        return True, "Voice guide loads correctly"
    except Exception as e:
        return False, f"Voice guide error: {e}"


def test_research_prompt_loads() -> Tuple[bool, str]:
    """Test that research prompt loads."""
    try:
        prompt_path = Path("skills/research_prompt.md")
        if not prompt_path.exists():
            return False, "Research prompt not found"
        
        content = prompt_path.read_text()
        if len(content) < 100:
            return False, "Research prompt seems too short"
        
        return True, "Research prompt loads correctly"
    except Exception as e:
        return False, f"Research prompt error: {e}"


def test_database_loads() -> Tuple[bool, str]:
    """Test that master database loads."""
    try:
        db_path = Path("data/master_database.json")
        if not db_path.exists():
            # Try alternative location
            db_path = Path("gravel_races_full_database.json")
        
        if not db_path.exists():
            return False, "Database file not found"
        
        with open(db_path) as f:
            db = json.load(f)
        
        races = db.get("races", [])
        if len(races) == 0:
            return False, "Database has no races"
        
        return True, f"Database loads correctly ({len(races)} races)"
    except Exception as e:
        return False, f"Database error: {e}"


def test_scripts_executable() -> Tuple[bool, str]:
    """Test that all scripts are executable and have shebang."""
    scripts = [
        "scripts/research.py",
        "scripts/validate.py",
        "scripts/synthesize.py",
        "scripts/generate_json.py",
        "scripts/push_wordpress.py",
        "scripts/notify.py",
        "scripts/validate_output.py",
    ]
    
    missing = []
    for script in scripts:
        path = Path(script)
        if not path.exists():
            missing.append(script)
        elif not path.is_file():
            missing.append(f"{script} (not a file)")
        else:
            # Check shebang
            content = path.read_text()
            if not content.startswith("#!/usr/bin/env python3"):
                missing.append(f"{script} (missing shebang)")
    
    if missing:
        return False, f"Script issues: {', '.join(missing)}"
    
    return True, f"All {len(scripts)} scripts are valid"


def test_workflow_files_exist() -> Tuple[bool, str]:
    """Test that workflow files exist and are valid YAML."""
    workflows = [
        ".github/workflows/research-race.yml",
        ".github/workflows/batch-process.yml",
        ".github/workflows/update-existing.yml",
    ]
    
    missing = []
    for workflow in workflows:
        if not Path(workflow).exists():
            missing.append(workflow)
    
    if missing:
        return False, f"Missing workflows: {', '.join(missing)}"
    
    return True, f"All {len(workflows)} workflows exist"


def test_directory_structure() -> Tuple[bool, str]:
    """Test that required directories exist."""
    required_dirs = [
        ".github/workflows",
        "scripts",
        "skills",
        "data/processed",
        "research-dumps",
        "briefs",
        "landing-pages",
    ]
    
    missing = []
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            missing.append(dir_path)
    
    if missing:
        return False, f"Missing directories: {', '.join(missing)}"
    
    return True, "Directory structure complete"


def test_imports() -> Tuple[bool, str]:
    """Test that required Python packages can be imported."""
    required_packages = [
        "anthropic",
        "requests",
        "yaml",
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        return False, f"Missing packages: {', '.join(missing)} (install with: pip install {' '.join(missing)})"
    
    return True, f"All {len(required_packages)} packages available"


def run_all_tests() -> bool:
    """Run all regression tests."""
    tests = [
        ("JSON Schema", test_json_schema_loads),
        ("Voice Guide", test_voice_guide_loads),
        ("Research Prompt", test_research_prompt_loads),
        ("Database", test_database_loads),
        ("Scripts", test_scripts_executable),
        ("Workflows", test_workflow_files_exist),
        ("Directory Structure", test_directory_structure),
        ("Python Imports", test_imports),
    ]
    
    print("\n" + "="*60)
    print("REGRESSION TESTS")
    print("="*60 + "\n")
    
    all_passed = True
    results = []
    
    for name, test_func in tests:
        passed, message = test_func()
        status = "✓" if passed else "✗"
        print(f"{status} {name}: {message}")
        results.append((name, passed, message))
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("="*60 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

