"""Search functionality for products index.

Executes search queries against Elasticsearch and formats results.
"""

import logging
from typing import Optional

from elasticsearch import Elasticsearch

from ..config import settings

logger = logging.getLogger(__name__)


def search_products(
    es: Elasticsearch,
    query: str,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    brand: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock_only: bool = False,
    sort_by: str | None = None,
) -> dict:
    """Search products with filters and pagination.

    Args:
        es: Elasticsearch client
        query: Search query string
        page: Page number (1-indexed)
        page_size: Results per page
        category: Filter by category
        brand: Filter by brand
        min_price: Minimum price filter
        max_price: Maximum price filter
        in_stock_only: Only show in-stock items
        sort_by: Sort field (price_asc, price_desc, rating, relevance)

    Returns:
        Dict with hits, total, aggregations, and search metadata
    """
    index = settings.SEARCH_INDEX

    # Build the query
    must_clause = []
    filter_clause = []

    # Main search query
    if query and query.strip():
        must_clause.append(
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "description", "brand^2", "category", "tags"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "prefix_length": 2,
                }
            }
        )
    else:
        must_clause.append({"match_all": {}})

    # Filters
    if category:
        filter_clause.append({"term": {"category": category}})

    if brand:
        filter_clause.append({"term": {"brand": brand}})

    if min_price is not None or max_price is not None:
        price_range = {}
        if min_price is not None:
            price_range["gte"] = min_price
        if max_price is not None:
            price_range["lte"] = max_price
        filter_clause.append({"range": {"price": price_range}})

    if in_stock_only:
        filter_clause.append({"term": {"in_stock": True}})

    # Build search body
    search_body = {
        "query": {"bool": {"must": must_clause, "filter": filter_clause}},
        "highlight": {
            "fields": {
                "title": {},
                "description": {"fragment_size": 150, "number_of_fragments": 2},
            },
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
        },
        "aggs": {
            "categories": {"terms": {"field": "category", "size": 20}},
            "brands": {"terms": {"field": "brand", "size": 20}},
            "price_stats": {"stats": {"field": "price"}},
        },
        "from": (page - 1) * page_size,
        "size": page_size,
    }

    # Sorting
    if sort_by == "price_asc":
        search_body["sort"] = [{"price": "asc"}, "_score"]
    elif sort_by == "price_desc":
        search_body["sort"] = [{"price": "desc"}, "_score"]
    elif sort_by == "rating":
        search_body["sort"] = [{"rating": "desc"}, "_score"]
    # Default is relevance (_score)

    # Execute search
    logger.info(f"Searching '{query}' in {index}, page {page}")
    response = es.search(index=index, body=search_body)

    # Format results
    hits = []
    for hit in response["hits"]["hits"]:
        result = {"id": hit["_id"], "score": hit["_score"], **hit["_source"]}
        if "highlight" in hit:
            result["highlight"] = hit["highlight"]
        hits.append(result)

    total = response["hits"]["total"]["value"]
    took_ms = response["took"]

    # Extract aggregations
    aggs = {}
    if "aggregations" in response:
        if "categories" in response["aggregations"]:
            aggs["categories"] = [
                {"key": b["key"], "count": b["doc_count"]}
                for b in response["aggregations"]["categories"]["buckets"]
            ]
        if "brands" in response["aggregations"]:
            aggs["brands"] = [
                {"key": b["key"], "count": b["doc_count"]}
                for b in response["aggregations"]["brands"]["buckets"]
            ]
        if "price_stats" in response["aggregations"]:
            aggs["price_stats"] = response["aggregations"]["price_stats"]

    return {
        "hits": hits,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "took_ms": took_ms,
        "zero_results": total == 0,
        "query": query,
        "aggregations": aggs,
    }
