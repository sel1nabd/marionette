#!/usr/bin/env python3
"""
Test suite for Marionette orchestrator.
Run with: python -m pytest tests/
"""

import pytest
import asyncio
from orchestrator.marionette import Marionette
from orchestrator.config import Config
from orchestrator.monitors import (
    DebugLoopMonitor,
    SycophancyDetector,
    PromptQualityAnalyzer
)
from orchestrator.gemini_client import GeminiClient
import os


# Mock Gemini client for testing without API calls
class MockGeminiClient:
    """Mock Gemini client for testing."""
    
    def __init__(self, api_key: str, model_name: str):
        self.model_name = model_name
    
    async def generate(self, prompt: str, **kwargs) -> str:
        return "Mock response"
    
    async def generate_json(self, prompt: str, **kwargs) -> dict:
        # Return appropriate mock responses based on prompt
        if "debug loop" in prompt.lower():
            return {
                "in_loop": True,
                "pattern": "Repetitive error",
                "confidence": 85
            }
        elif "sycophantic" in prompt.lower():
            return {
                "sycophantic": True,
                "reason": "Excessive agreement",
                "confidence": 90
            }
        elif "rate this" in prompt.lower():
            return {
                "specificity": 3,
                "completeness": 4,
                "ambiguity": 8,
                "approved": False,
                "feedback": "Too vague",
                "suggestions": ["Be more specific"]
            }
        return {}
    
    async def count_tokens(self, text: str) -> int:
        return len(text) // 4


@pytest.fixture
def mock_config():
    """Create mock configuration for testing."""
    return Config(
        gemini_api_key="mock_key",
        debug_loop_window=3,
        context_drift_threshold=0.7,
        auto_kill_loops=True,
        force_prompt_quality=False,  # Disable for most tests
        enable_grounding=False
    )


class TestDebugLoopMonitor:
    """Test debug loop detection."""
    
    @pytest.mark.asyncio
    async def test_detects_identical_errors(self, mock_config):
        mock_client = MockGeminiClient("key", "flash")
        monitor = DebugLoopMonitor(mock_client, window=3)
        
        errors = [
            {"error": "File not found: test.py"},
            {"error": "File not found: test.py"},
            {"error": "File not found: test.py"}
        ]
        
        result = await monitor.check(errors)
        assert result["in_loop"] is True
        assert "Identical" in result["pattern"]
    
    @pytest.mark.asyncio
    async def test_no_loop_with_varied_errors(self, mock_config):
        mock_client = MockGeminiClient("key", "flash")
        monitor = DebugLoopMonitor(mock_client, window=3)
        
        errors = [
            {"error": "File not found"},
            {"error": "Syntax error"},
            {"error": "Import error"}
        ]
        
        # Will use mock which returns in_loop based on prompt
        result = await monitor.check(errors)
        # Since errors are different, mock won't trigger
        assert result["in_loop"] is False
    
    @pytest.mark.asyncio
    async def test_insufficient_history(self, mock_config):
        mock_client = MockGeminiClient("key", "flash")
        monitor = DebugLoopMonitor(mock_client, window=5)
        
        errors = [{"error": "Error 1"}]
        
        result = await monitor.check(errors)
        assert result["in_loop"] is False


class TestSycophancyDetector:
    """Test sycophancy detection."""
    
    @pytest.mark.asyncio
    async def test_detects_agreement_patterns(self, mock_config):
        mock_client = MockGeminiClient("key", "flash")
        detector = SycophancyDetector(mock_client, threshold=2)
        
        sycophantic_text = "You're absolutely right! That's a great idea! Perfect approach!"
        
        result = await detector.check(sycophantic_text)
        assert result["detected"] is True
    
    @pytest.mark.asyncio
    async def test_normal_response_passes(self, mock_config):
        mock_client = MockGeminiClient("key", "flash")
        detector = SycophancyDetector(mock_client, threshold=3)
        
        normal_text = "I'll implement that feature. Here are three potential issues to consider first."
        
        result = await detector.check(normal_text)
        assert result["detected"] is False


class TestPromptQualityAnalyzer:
    """Test prompt quality analysis."""
    
    @pytest.mark.asyncio
    async def test_rejects_vague_prompt(self, mock_config):
        mock_client = MockGeminiClient("key", "pro")
        analyzer = PromptQualityAnalyzer(mock_client)
        
        vague_prompt = "make it better"
        
        result = await analyzer.analyze(vague_prompt)
        assert result["approved"] is False
        assert "feedback" in result
    
    @pytest.mark.asyncio
    async def test_approves_specific_prompt(self, mock_config):
        mock_client = MockGeminiClient("key", "pro")
        analyzer = PromptQualityAnalyzer(mock_client)
        
        # Mock will return low scores, but we can test structure
        specific_prompt = "Refactor UserAuth class to use async/await with error handling"
        
        result = await analyzer.analyze(specific_prompt)
        assert "specificity" in result
        assert "completeness" in result
        assert "ambiguity" in result


class TestMarionette:
    """Test core Marionette orchestrator."""
    
    @pytest.mark.asyncio
    async def test_processes_user_input(self, mock_config):
        # This would require full Gemini API or more complex mocking
        # Keeping as placeholder for integration tests
        pass
    
    @pytest.mark.asyncio
    async def test_processes_agent_output(self, mock_config):
        # Integration test placeholder
        pass


class TestConfig:
    """Test configuration management."""
    
    def test_config_validation(self):
        config = Config(
            gemini_api_key="test",
            context_drift_threshold=0.5
        )
        config.validate()  # Should not raise
    
    def test_invalid_threshold_raises(self):
        config = Config(
            gemini_api_key="test",
            context_drift_threshold=1.5
        )
        with pytest.raises(ValueError):
            config.validate()
    
    def test_invalid_window_raises(self):
        config = Config(
            gemini_api_key="test",
            debug_loop_window=1
        )
        with pytest.raises(ValueError):
            config.validate()


def test_imports():
    """Test that all modules import correctly."""
    from orchestrator import Marionette, Config, CLI
    from orchestrator.gemini_client import GeminiClient
    from orchestrator.monitors import (
        DebugLoopMonitor,
        ContextDriftMonitor,
        SycophancyDetector,
        PromptQualityAnalyzer
    )
    from orchestrator.interventions import InterventionEngine
    from orchestrator.session import SessionState
    
    assert Marionette is not None
    assert Config is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
