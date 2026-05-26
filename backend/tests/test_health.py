"""Health check endpoint tests.

These tests verify basic API functionality without requiring
external services (Elastic Agent Builder, etc.).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_root_endpoint(self):
        """Test that root endpoint returns API info."""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data or "version" in data or "message" in data

    def test_docs_endpoint(self):
        """Test that OpenAPI docs are accessible."""
        response = self.client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema(self):
        """Test that OpenAPI schema is generated."""
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
