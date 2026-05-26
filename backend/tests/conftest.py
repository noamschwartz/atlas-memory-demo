"""Pytest configuration and fixtures for backend tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("KIBANA_URL", "https://test.kb.elastic-cloud.com")
    monkeypatch.setenv("ELASTIC_API_KEY", "test-api-key")
    monkeypatch.setenv("AGENT_ID", "test-agent-id")
    monkeypatch.setenv("PORT", "8001")
