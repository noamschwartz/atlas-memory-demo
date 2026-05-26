"""Elasticsearch client initialization and management.

Supports both Elastic Cloud (via Cloud ID) and direct URL connections.
"""

import logging
from typing import Optional

from elasticsearch import AuthenticationException, AuthorizationException, Elasticsearch

from ..config import settings

logger = logging.getLogger(__name__)

# Global client instance (lazy initialized)
_es_client: Elasticsearch | None = None


def get_es_client() -> Elasticsearch:
    """Get or create the Elasticsearch client.

    Uses Cloud ID if available, otherwise falls back to direct URL.
    Authentication is via API key.

    Returns:
        Elasticsearch client instance

    Raises:
        ValueError: If neither Cloud ID nor URL is configured
    """
    global _es_client

    if _es_client is not None:
        return _es_client

    if not settings.ELASTIC_API_KEY:
        raise ValueError("ELASTIC_API_KEY is required")

    if settings.ELASTIC_CLOUD_ID:
        logger.info("Connecting to Elastic Cloud via Cloud ID")
        _es_client = Elasticsearch(
            cloud_id=settings.ELASTIC_CLOUD_ID,
            api_key=settings.ELASTIC_API_KEY,
        )
    elif settings.ELASTICSEARCH_URL:
        logger.info(f"Connecting to Elasticsearch at {settings.ELASTICSEARCH_URL}")
        _es_client = Elasticsearch(
            hosts=[settings.ELASTICSEARCH_URL],
            api_key=settings.ELASTIC_API_KEY,
        )
    else:
        raise ValueError(
            "Either ELASTIC_CLOUD_ID or ELASTICSEARCH_URL must be configured"
        )

    # Verify connection (best-effort; restricted API keys may lack cluster:monitor)
    try:
        info = _es_client.info()
        logger.info(f"Connected to Elasticsearch cluster: {info['cluster_name']}")
    except (AuthenticationException, AuthorizationException) as e:
        logger.warning(f"Could not verify ES connection (key may lack cluster:monitor privilege): {e}")

    return _es_client


def es_client() -> Elasticsearch:
    """Dependency injection helper for FastAPI.

    Usage:
        @app.get("/search")
        def search(es: Elasticsearch = Depends(es_client)):
            ...
    """
    return get_es_client()


def close_es_client() -> None:
    """Close the Elasticsearch client connection."""
    global _es_client
    if _es_client is not None:
        _es_client.close()
        _es_client = None
        logger.info("Elasticsearch client closed")
