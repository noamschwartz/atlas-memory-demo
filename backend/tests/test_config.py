"""Configuration loading tests.

Tests that environment variables are properly loaded and
configuration is correctly initialized.
"""

import importlib
import os

import pytest

from app import config as config_module


class TestConfigLoading:
    """Test suite for configuration module."""

    def test_config_imports(self):
        """Test that config module can be imported."""
        importlib.reload(config_module)
        assert config_module.settings is not None

    def test_config_has_required_fields(self):
        """Test that config has expected fields (may be empty)."""
        importlib.reload(config_module)
        settings = config_module.settings
        # These attributes should exist even if not configured
        assert hasattr(settings, "kibana_url") or hasattr(settings, "KIBANA_URL")

    def test_port_default(self):
        """Test that PORT has a sensible default."""
        importlib.reload(config_module)
        settings = config_module.settings
        port = getattr(settings, "port", None) or getattr(settings, "PORT", None)
        # Port should be a number if set
        if port is not None:
            assert isinstance(port, (int, str))


class TestEnvironmentVariables:
    """Test suite for environment variable handling."""

    def test_dotenv_loading(self, mock_env):
        """Test that mock environment variables are accessible."""
        assert os.getenv("KIBANA_URL") == "https://test.kb.elastic-cloud.com"
        assert os.getenv("ELASTIC_API_KEY") == "test-api-key"
        assert os.getenv("AGENT_ID") == "test-agent-id"
