"""Elasticsearch utilities and client management.

Provides:
- Client connection management
- Query building utilities
- RetrieverBuilder for configurable search
- Search execution helpers
"""

from .client import close_es_client, es_client, get_es_client
from .query_builder import QueryBuilder, build_filter_clauses, get_index_fields
from .retriever_builder import RetrieverBuilder
from .search import search_products

__all__ = [
    "QueryBuilder",
    "RetrieverBuilder",
    "build_filter_clauses",
    "close_es_client",
    "es_client",
    "get_es_client",
    "get_index_fields",
    "search_products",
]
