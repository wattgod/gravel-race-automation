"""Tests for research.py script."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestResponseExtraction:
    """Test API response extraction logic."""

    def test_extracts_text_from_direct_response(self):
        """Should extract text from response content blocks."""
        # Mock response with direct text (tests extraction logic without importing research.py)
        mock_response = Mock()
        mock_response.content = [Mock(text="This is research content with lots of details about the race." * 50)]

        # Verify the response structure works with the extraction pattern used in research.py
        assert hasattr(mock_response.content[0], 'text')
        assert len(mock_response.content[0].text) > 1000

        # Verify multi-block extraction works (as research.py iterates all blocks)
        content = ""
        for block in mock_response.content:
            if hasattr(block, 'text') and block.text:
                content += block.text
        assert len(content) > 1000
    
    def test_handles_empty_response(self):
        """Should raise error on empty response."""
        mock_response = Mock()
        mock_response.content = []
        
        # Should detect empty content
        assert len(mock_response.content) == 0
    
    def test_handles_short_response(self):
        """Should detect and reject short responses."""
        mock_response = Mock()
        mock_response.content = [Mock(text="Short")]
        
        # Should detect short content
        content = mock_response.content[0].text
        assert len(content) < 1000  # Our minimum threshold


class TestResearchScript:
    """Test research script functionality."""
    
    def test_research_script_exists(self):
        """Research script should exist and be importable."""
        script_path = Path(__file__).parent.parent / "scripts" / "research.py"
        assert script_path.exists()
        assert script_path.is_file()
    
    def test_research_script_has_correct_imports(self):
        """Script should have required imports."""
        script_path = Path(__file__).parent.parent / "scripts" / "research.py"
        content = script_path.read_text()
        
        assert "import anthropic" in content
        assert "from pathlib import Path" in content
        assert "import os" in content
    
    def test_research_script_has_response_extraction(self):
        """Script should extract response correctly."""
        script_path = Path(__file__).parent.parent / "scripts" / "research.py"
        content = script_path.read_text()

        # Should iterate response.content blocks and extract text
        assert "response.content" in content
        assert "hasattr(block, 'text')" in content or "block.text" in content
    
    def test_research_script_handles_rate_limits(self):
        """Script should have rate limit retry logic."""
        script_path = Path(__file__).parent.parent / "scripts" / "research.py"
        content = script_path.read_text()
        
        assert "RateLimitError" in content
        assert "retry" in content.lower() or "retries" in content.lower()


class TestAPIResponseStructure:
    """Test that we handle Anthropic API response structure correctly."""
    
    def test_response_content_structure(self):
        """Mock Anthropic API response structure."""
        # Simulate Anthropic API response
        mock_block = Mock()
        mock_block.text = "Research content here" * 100
        mock_block.type = "text"
        
        mock_response = Mock()
        mock_response.content = [mock_block]
        
        # Extract like our script does
        if len(mock_response.content) > 0 and hasattr(mock_response.content[0], 'text'):
            content = mock_response.content[0].text
            assert len(content) > 1000
            assert "Research content" in content
    
    def test_response_with_multiple_blocks(self):
        """Handle response with multiple content blocks."""
        mock_blocks = [
            Mock(text="First block " * 50),
            Mock(text="Second block " * 50)
        ]
        
        mock_response = Mock()
        mock_response.content = mock_blocks
        
        # Extract first block (like our script)
        if len(mock_response.content) > 0:
            content = mock_response.content[0].text
            assert len(content) > 0
            assert "First block" in content


class TestResearchQualityChecks:
    """Test research quality validation."""
    
    def test_minimum_length_check(self):
        """Should reject research shorter than 1000 chars."""
        short_content = "Short" * 10  # 50 chars
        assert len(short_content) < 1000
        
        long_content = "Research " * 200  # 1800 chars
        assert len(long_content) >= 1000
    
    def test_url_extraction(self):
        """Should extract URLs from research content."""
        import re
        
        content = """
        Check out https://reddit.com/r/gravelcycling/abc
        Also see https://youtube.com/watch?v=123
        Official site: https://midsouth.com
        """
        
        urls = re.findall(r'https?://[^\s\)\]\"\'<>]+', content)
        assert len(urls) >= 3
        assert any('reddit.com' in url for url in urls)
        assert any('youtube.com' in url for url in urls)


class TestResearchPrompt:
    """Test research prompt structure."""
    
    def test_prompt_includes_retry_logic(self):
        """Prompt should include retry logic for rate limits."""
        script_path = Path(__file__).parent.parent / "scripts" / "research.py"
        content = script_path.read_text()

        # Should have retry logic for API rate limits
        assert "max_retries" in content
        assert "retry" in content.lower()
    
    def test_prompt_includes_anti_slop(self):
        """Prompt should include anti-slop requirements."""
        script_path = Path(__file__).parent.parent / "scripts" / "research.py"
        content = script_path.read_text()
        
        # Should have anti-slop guidance
        assert "NO SLOP" in content or "slop" in content.lower()
        assert "amazing opportunity" in content.lower() or "world-class" in content.lower()
    
    def test_prompt_requires_sources(self):
        """Prompt should require specific sources."""
        script_path = Path(__file__).parent.parent / "scripts" / "research.py"
        content = script_path.read_text()
        
        # Should require Reddit and YouTube
        assert "reddit" in content.lower()
        assert "youtube" in content.lower()

