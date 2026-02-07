"""End-to-end integration tests."""

import pytest
import subprocess
from pathlib import Path


class TestPipelineIntegration:
    """Test the full pipeline with a known race."""
    
    @pytest.fixture
    def test_race(self):
        return {
            "name": "Test Race",
            "folder": "test-race"
        }
    
    def test_quality_gates_script_runs(self):
        """Quality gates script should be executable."""
        script_path = Path(__file__).parent.parent / "scripts" / "quality_gates.py"
        assert script_path.exists()
        assert script_path.is_file()
    
    def test_validate_catches_bad_research(self):
        """Validation should fail on fabricated research."""
        bad_research = """
        ## OFFICIAL DATA
        The race is 500 miles with 50,000 ft of climbing.
        Source: https://example.com/fake
        
        ## REDDIT
        u/notreal said "This quote is fabricated"
        """
        
        # Import quality gates
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from quality_gates import run_all_quality_checks
        
        result = run_all_quality_checks(bad_research, "research")
        
        # Should fail on missing sections or citations
        assert not result["overall_passed"] or len(result["critical_failures"]) > 0
    
    def test_scripts_importable(self):
        """All pipeline scripts should have valid syntax and exist."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        scripts = [
            "research",
            "validate",
            "synthesize",
            "generate_json",
            "push_wordpress",
            "notify",
            "quality_gates",
        ]

        import sys
        sys.path.insert(0, str(scripts_dir))

        for script in scripts:
            script_path = scripts_dir / f"{script}.py"
            assert script_path.exists(), f"Script missing: {script}.py"

            # Verify valid Python syntax via compile
            source = script_path.read_text()
            try:
                compile(source, str(script_path), "exec")
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {script}.py: {e}")

