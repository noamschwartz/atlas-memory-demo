"""Retriever Builder - Composable Elasticsearch Retriever Queries

Builds Elasticsearch queries using the Retriever API (8.17+/Serverless).
The retriever approach provides better composability for:
- Query rules (rule retriever as outermost wrapper)
- Hybrid search (RRF retriever)
- Semantic reranking (text_similarity_reranker)

Key Architecture:
- Rule retriever MUST be outermost to apply correctly
- Standard retriever wraps traditional queries
- RRF combines multiple retrievers with reciprocal rank fusion

References:
- https://www.elastic.co/search-labs/blog/semantic-search-query-rules
- https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/rule-retriever
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RetrieverBuilder:
    """Builds Elasticsearch retriever-based queries.

    Provides composable query building where:
    1. Core queries become `standard` retrievers
    2. Multiple search types combine via `rrf` retriever
    3. Query rules wrap everything via `rule` retriever (outermost)

    Usage:
        builder = RetrieverBuilder(config)
        body = builder.build(
            query="laptop",
            filters=[{"term": {"category": "Electronics"}}],
            ruleset_ids=["merchandising"],
        )
        # Returns {"retriever": {...}, "aggs": {...}, "from": 0, "size": 20}
    """

    def __init__(self, config: dict):
        """Initialize with search configuration.

        Args:
            config: Dict containing:
                - index: Elasticsearch index name
                - searchFields: List of fields to search (with optional boosts, e.g., "title^3")
                - facets: List of facet configs for aggregations
                - rangeFilters: List of range filter configs
                - rankFeatureFields: Dict mapping feature names to field paths (optional)
                  E.g., {"popularity": "rank_features.popularity", "freshness": "rank_features.freshness"}
                - personalizationFields: Dict mapping personalization types to field names (optional)
                  E.g., {"brand": "brand", "category": "category"}
        """
        self.config = config
        self.search_fields = config.get("searchFields", ["title", "description"])

        # Configurable rank_feature field mappings
        # Default to empty - no hard-coded e-commerce fields
        self.rank_feature_fields = config.get("rankFeatureFields", {})

        # Configurable personalization field mappings
        # Maps preference types (brand, category) to actual field names
        # Default to empty - no hard-coded assumptions about field names
        self.personalization_fields = config.get("personalizationFields", {})

    def build(
        self,
        query: str,
        filters: list | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "desc",
        ruleset_ids: list[str] | None = None,
        feature_weights: dict | None = None,
        user_preferences: dict | None = None,
        session_context: dict | None = None,
        use_rrf: bool = False,
        knn_config: dict | None = None,
        semantic_config: dict | None = None,
        reranker_config: dict | None = None,
        collapse_config: dict | None = None,
        ltr_config: dict | None = None,
        mmr_config: dict | None = None,
        hybrid_config: dict | None = None,
    ) -> dict:
        """Build a complete retriever-based search query.

        Args:
            query: Search query string
            filters: List of filter clauses (ES bool filter format)
            page: Page number (1-indexed)
            page_size: Results per page
            sort_by: Sort field (None = relevance)
            sort_dir: Sort direction ('asc' or 'desc')
            ruleset_ids: Query rule ruleset IDs to apply
            feature_weights: Dict of rank_feature weights (normalized 0-10)
            user_preferences: Dict with preferred_brands, preferred_categories, brand_boost, etc.
            session_context: Dict with recent_categories, recent_category_boost, etc.
            use_rrf: Force RRF even with single retriever (deprecated, use hybrid_config)
            knn_config: kNN retriever config for vector search
            semantic_config: Semantic query config {field, query}
            reranker_config: Text similarity reranker config
            collapse_config: Field collapse config for diversification:
                {field: str, inner_hits_count: int, inner_hits_sort: str, inner_hits_sort_dir: str}
            ltr_config: Learning to Rank rescore config:
                {model_id: str, window_size: int} - requires query for feature extraction
            mmr_config: MMR diversify retriever config (ES 9.0+):
                {field: str, lambda_: float, rank_window_size: int, inference_id: str}
            hybrid_config: Hybrid search config for linear retriever (ES 8.18+):
                {enabled: bool, semantic_weight: float (0-1), text_weight: float (0-1),
                 semantic_field: str, use_linear: bool (default True)}

        Returns:
            Complete Elasticsearch query body with retriever structure
        """
        filters = filters or []

        # Step 1: Build the innermost retriever(s)
        retrievers = []

        # Text search retriever (standard)
        if query and query.strip():
            text_retriever = self._build_text_retriever(
                query, filters, feature_weights, user_preferences, session_context
            )
            retrievers.append(text_retriever)

        # Semantic search retriever (if configured)
        # NOTE: Semantic search requires a non-empty query for inference
        if semantic_config and semantic_config.get("query", "").strip():
            semantic_retriever = self._build_semantic_retriever(
                query=semantic_config.get("query", query),
                field=semantic_config.get("field", "semantic_text"),
                filters=filters,
            )
            retrievers.append(semantic_retriever)

        # kNN retriever (if configured)
        if knn_config:
            knn_retriever = {"knn": knn_config}
            retrievers.append(knn_retriever)

        # If no retrievers (empty query), build a browse-mode retriever
        if not retrievers:
            # Build should clauses for scoring in browse mode
            should_clauses = []
            must_not_clauses = []

            # Add rank_feature clauses if weights provided
            if feature_weights:
                should_clauses.extend(self._build_rank_feature_clauses(feature_weights))

            # Add personalization clauses
            personalization_clauses, exclusion_clauses = (
                self._build_personalization_clauses(user_preferences, session_context)
            )
            should_clauses.extend(personalization_clauses)
            must_not_clauses.extend(exclusion_clauses)

            # Build the browse query
            if should_clauses or must_not_clauses:
                browse_query: dict = {
                    "bool": {
                        "must": [{"match_all": {}}],
                    }
                }

                if should_clauses:
                    browse_query["bool"]["should"] = should_clauses

                if must_not_clauses:
                    browse_query["bool"]["must_not"] = must_not_clauses

                if filters:
                    browse_query["bool"]["filter"] = filters

                retrievers.append(
                    {"standard": {"_name": "retriever:browse", "query": browse_query}}
                )

                # Log what's active
                active_features = []
                if feature_weights:
                    active_features.append(
                        f"rank_features: {list(feature_weights.keys())}"
                    )
                if user_preferences:
                    if user_preferences.get("preferred_brands"):
                        active_features.append(
                            f"brands: {user_preferences['preferred_brands']}"
                        )
                    if user_preferences.get("preferred_categories"):
                        active_features.append(
                            f"categories: {user_preferences['preferred_categories']}"
                        )
                if session_context and session_context.get("recent_categories"):
                    active_features.append(
                        f"recent: {session_context['recent_categories']}"
                    )

                logger.info(
                    f"Browse mode with: {', '.join(active_features) if active_features else 'no scoring'}"
                )
            else:
                # No scoring signals - simple match_all
                retrievers.append(
                    {
                        "standard": {
                            "_name": "retriever:browse_all",
                            "query": {"match_all": {}},
                            "filter": {"bool": {"filter": filters}}
                            if filters
                            else None,
                        }
                    }
                )
                logger.info(
                    "Browse mode with no scoring signals (all scores will be 1.0)"
                )

            # Clean up None filter
            if (
                "filter" in retrievers[0].get("standard", {})
                and retrievers[0]["standard"]["filter"] is None
            ):
                del retrievers[0]["standard"]["filter"]

        # Step 2: Combine multiple retrievers (linear preferred over RRF)
        if len(retrievers) > 1:
            # Check if we should use linear retriever (default for hybrid)
            use_linear = True
            if hybrid_config:
                use_linear = hybrid_config.get("use_linear", True)
            elif use_rrf:
                use_linear = False  # Legacy: explicit RRF requested

            if use_linear:
                # Linear retriever with configurable weights and MinMax normalization
                # This preserves actual scores and allows fine-tuned control
                semantic_weight = 0.5
                text_weight = 0.5
                if hybrid_config:
                    semantic_weight = hybrid_config.get("semantic_weight", 0.5)
                    text_weight = hybrid_config.get(
                        "text_weight", 1.0 - semantic_weight
                    )

                # Build weighted retrievers for linear combination
                weighted_retrievers = []
                for i, retriever in enumerate(retrievers):
                    # First retriever is text, second is semantic (by convention)
                    weight = text_weight if i == 0 else semantic_weight
                    weighted_retrievers.append(
                        {"retriever": retriever, "weight": weight}
                    )

                # rank_window_size must be >= size for linear retriever
                linear_window_size = max(100, page_size)
                inner_retriever = {
                    "linear": {
                        "_name": "retriever:linear_hybrid",
                        "retrievers": weighted_retrievers,
                        "normalizer": "minmax",
                        "rank_window_size": linear_window_size,
                    }
                }
                logger.info(
                    f"Using Linear retriever: text={text_weight:.2f}, semantic={semantic_weight:.2f}"
                )
            else:
                # Legacy RRF for backward compatibility
                inner_retriever = {
                    "rrf": {
                        "_name": "retriever:rrf",
                        "retrievers": retrievers,
                        "rank_window_size": 100,
                        "rank_constant": 60,
                    }
                }
                logger.info(f"Using RRF to combine {len(retrievers)} retrievers")
        elif use_rrf and len(retrievers) == 1:
            # Force RRF with single retriever (edge case)
            inner_retriever = {
                "rrf": {
                    "_name": "retriever:rrf",
                    "retrievers": retrievers,
                    "rank_window_size": 100,
                    "rank_constant": 60,
                }
            }
            logger.info("Using RRF with single retriever (forced)")
        else:
            inner_retriever = retrievers[0]

        # Step 3: Wrap with reranker if configured
        if reranker_config:
            inner_retriever = self._wrap_with_reranker(inner_retriever, reranker_config)

        # Step 3b: Wrap with MMR diversify retriever if configured (before rule retriever)
        if mmr_config and mmr_config.get("enabled"):
            inner_retriever = self._wrap_with_diversify_retriever(
                inner_retriever, mmr_config, query
            )
            logger.info(
                f"MMR diversify enabled: lambda={mmr_config.get('lambda_', 0.5)}, field={mmr_config.get('field', 'embedding')}"
            )

        # Step 4: Wrap with rule retriever if rules configured (MUST be outermost)
        if ruleset_ids:
            # rank_window_size must be >= size for rule retriever
            rule_window_size = max(100, page_size)
            final_retriever = {
                "rule": {
                    "_name": "retriever:query_rules",
                    "match_criteria": {"query_string": query or ""},
                    "ruleset_ids": ruleset_ids,
                    "retriever": inner_retriever,
                    "rank_window_size": rule_window_size,
                }
            }
            logger.info(f"Wrapping with rule retriever: {ruleset_ids}")
        else:
            final_retriever = inner_retriever

        # Step 5: Build complete query body
        body = {
            "retriever": final_retriever,
            "from": (page - 1) * page_size,
            "size": page_size,
        }

        # Add aggregations
        body["aggs"] = self._build_aggregations()

        # Add highlight (works with retrievers)
        body["highlight"] = {
            "fields": {
                "*": {
                    "fragment_size": 150,
                    "number_of_fragments": 2,
                }
            },
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
        }

        # Add sort (if not relevance)
        if sort_by and sort_by != "_score":
            body["sort"] = [
                {sort_by: sort_dir},
                {"_score": "desc"},
            ]

        # Add field collapse for diversification
        if collapse_config:
            body["collapse"] = self._build_collapse(collapse_config)
            logger.info(f"Field collapse enabled on: {collapse_config.get('field')}")

        # Add LTR rescoring - wrap the final retriever with rescorer retriever (ES 9.0+)
        if ltr_config and query and query.strip():
            body["retriever"] = self._wrap_with_ltr_rescorer(
                body["retriever"], ltr_config, query
            )
            logger.info(
                f"LTR rescore enabled: model={ltr_config.get('model_id')}, window={ltr_config.get('window_size')}"
            )

        return body

    def _build_text_retriever(
        self,
        query: str,
        filters: list,
        feature_weights: dict | None = None,
        user_preferences: dict | None = None,
        session_context: dict | None = None,
    ) -> dict:
        """Build a standard retriever for text search with personalization."""
        # Build the main text query with _name for score breakdown
        text_query = {
            "multi_match": {
                "query": query,
                "fields": self.search_fields,
                "type": "best_fields",
                "fuzziness": "AUTO",
                "prefix_length": 2,
                "_name": "text_relevance",
            }
        }

        # Build bool query
        bool_query: dict[str, Any] = {
            "must": [text_query],
        }

        # Add filters if present
        if filters:
            bool_query["filter"] = filters

        # Build should clauses
        should_clauses = []

        # Add rank_feature boosting if weights provided
        if feature_weights:
            should_clauses.extend(self._build_rank_feature_clauses(feature_weights))

        # Add personalization clauses
        personalization_clauses, must_not_clauses = self._build_personalization_clauses(
            user_preferences, session_context
        )
        should_clauses.extend(personalization_clauses)

        if should_clauses:
            bool_query["should"] = should_clauses

        if must_not_clauses:
            bool_query["must_not"] = must_not_clauses

        return {"standard": {"_name": "retriever:text", "query": {"bool": bool_query}}}

    def _build_semantic_retriever(
        self,
        query: str,
        field: str,
        filters: list,
    ) -> dict:
        """Build a standard retriever for semantic search.

        Args:
            query: Search query string (must be non-empty for inference to work)
            field: semantic_text field name
            filters: Filter clauses

        Returns:
            Standard retriever with semantic query

        Raises:
            ValueError: If query is empty (inference requires non-empty input)
        """
        if not query or not query.strip():
            raise ValueError("Semantic search requires a non-empty query for inference")

        semantic_query: dict[str, Any] = {
            "semantic": {
                "field": field,
                "query": query,
            }
        }

        # Wrap in bool with filters if needed
        if filters:
            return {
                "standard": {
                    "_name": "retriever:semantic",
                    "query": {
                        "bool": {
                            "must": [semantic_query],
                            "filter": filters,
                        }
                    },
                }
            }

        return {"standard": {"_name": "retriever:semantic", "query": semantic_query}}

    def _build_rank_feature_clauses(self, weights: dict) -> list:
        """Build rank_feature should clauses for business signal boosting.

        Each clause is wrapped in a bool query with _name for score breakdown.
        This allows include_named_queries_score to report individual signal contributions.

        Uses configurable field mappings from self.rank_feature_fields.
        If no mapping exists for a feature in weights, that feature is skipped.

        Args:
            weights: Dict of feature -> boost value (0-10 scale)
                     Feature names should match keys in config.rankFeatureFields

        Returns:
            List of rank_feature query clauses wrapped with _name

        Example:
            If config contains:
                rankFeatureFields: {"popularity": "signals.popularity", "freshness": "signals.recency"}
            And weights is:
                {"popularity": 5.0, "freshness": 3.0, "unknown": 2.0}
            Then only popularity and freshness clauses are generated (unknown is skipped).
        """
        clauses = []

        for feature, weight in weights.items():
            if not weight or weight <= 0:
                continue

            # Look up the field path from config
            field = self.rank_feature_fields.get(feature)
            if not field:
                logger.debug(
                    f"Skipping unknown rank_feature: {feature} (not in rankFeatureFields config)"
                )
                continue

            # Wrap rank_feature in bool to support _name
            clauses.append(
                {
                    "bool": {
                        "should": [
                            {
                                "rank_feature": {
                                    "field": field,
                                    "boost": weight,
                                    "saturation": {},
                                }
                            }
                        ],
                        "_name": f"signal:{feature}",
                    }
                }
            )

        return clauses

    def _build_personalization_clauses(
        self,
        user_preferences: dict | None,
        session_context: dict | None,
    ) -> tuple[list, list]:
        """Build personalization should and must_not clauses with _name for score breakdown.

        Personalization works by adding 'terms' queries to the 'should' clause
        with boost values. When a document matches (e.g., brand = "Nike"),
        the boost is added to its relevance score.

        Uses configurable field mappings from self.personalization_fields.
        If a field mapping is missing, that personalization type is skipped.

        Each clause includes _name for use with include_named_queries_score.

        Args:
            user_preferences: Dict with preferred_brands, preferred_categories,
                              brand_boost, category_boost, excluded_brands
            session_context: Dict with recent_categories, recent_category_boost

        Returns:
            Tuple of (should_clauses, must_not_clauses)

        Example:
            If config contains:
                personalizationFields: {"brand": "manufacturer", "category": "product_type"}
            Then preferred_brands will use the "manufacturer" field instead of "brand".
        """
        should_clauses = []
        must_not_clauses = []

        # Get field names from config (skip if not configured)
        brand_field = self.personalization_fields.get("brand")
        category_field = self.personalization_fields.get("category")

        if user_preferences:
            # Boost preferred brands (if brand field is configured)
            preferred_brands = user_preferences.get("preferred_brands", [])
            brand_boost = user_preferences.get("brand_boost", 2.0)
            if preferred_brands and brand_field:
                should_clauses.append(
                    {
                        "terms": {
                            brand_field: preferred_brands,
                            "boost": brand_boost,
                            "_name": "personalization:preferred_brand",
                        }
                    }
                )
                logger.debug(
                    f"Personalization: boosting {brand_field}={preferred_brands} by {brand_boost}x"
                )
            elif preferred_brands and not brand_field:
                logger.debug(
                    "Skipping preferred_brands: no 'brand' in personalizationFields config"
                )

            # Boost preferred categories (if category field is configured)
            preferred_categories = user_preferences.get("preferred_categories", [])
            category_boost = user_preferences.get("category_boost", 1.5)
            if preferred_categories and category_field:
                should_clauses.append(
                    {
                        "terms": {
                            category_field: preferred_categories,
                            "boost": category_boost,
                            "_name": "personalization:preferred_category",
                        }
                    }
                )
                logger.debug(
                    f"Personalization: boosting {category_field}={preferred_categories} by {category_boost}x"
                )
            elif preferred_categories and not category_field:
                logger.debug(
                    "Skipping preferred_categories: no 'category' in personalizationFields config"
                )

            # Exclude brands the user doesn't want (if brand field is configured)
            excluded_brands = user_preferences.get("excluded_brands", [])
            if excluded_brands and brand_field:
                must_not_clauses.append(
                    {
                        "terms": {
                            brand_field: excluded_brands,
                            "_name": "filter:excluded_brand",
                        }
                    }
                )
                logger.debug(
                    f"Personalization: excluding {brand_field}={excluded_brands}"
                )
            elif excluded_brands and not brand_field:
                logger.debug(
                    "Skipping excluded_brands: no 'brand' in personalizationFields config"
                )

        if session_context:
            # Boost recently engaged categories (if category field is configured)
            recent_categories = session_context.get("recent_categories", [])
            recent_boost = session_context.get("recent_category_boost", 1.3)
            if recent_categories and category_field:
                should_clauses.append(
                    {
                        "terms": {
                            category_field: recent_categories,
                            "boost": recent_boost,
                            "_name": "session:recent_category",
                        }
                    }
                )
                logger.debug(
                    f"Session: boosting {category_field}={recent_categories} by {recent_boost}x"
                )
            elif recent_categories and not category_field:
                logger.debug(
                    "Skipping recent_categories: no 'category' in personalizationFields config"
                )

        return should_clauses, must_not_clauses

    def _wrap_with_reranker(self, retriever: dict, config: dict) -> dict:
        """Wrap a retriever with text_similarity_reranker.

        Args:
            retriever: The retriever to wrap
            config: Reranker config with:
                - field: Required. Text field to rerank on (e.g., "description", "content")
                - model_id: Required. Inference endpoint ID (e.g., ".rerank-1", "my-cohere-reranker")
                - model_text: Optional. Query text for reranking (defaults to search query)
                - window_size: Optional. Number of results to rerank (default: 100)

        Returns:
            Wrapped retriever with reranking

        Raises:
            ValueError: If required config fields are missing
        """
        field = config.get("field")
        model_id = config.get("model_id")

        if not field:
            raise ValueError(
                "Reranker config requires 'field' - the text field to rerank on"
            )
        if not model_id:
            raise ValueError(
                "Reranker config requires 'model_id' - the inference endpoint ID"
            )

        return {
            "text_similarity_reranker": {
                "_name": "retriever:reranker",
                "retriever": retriever,
                "field": field,
                "inference_id": model_id,
                "inference_text": config.get("model_text"),
                "rank_window_size": config.get("window_size", 100),
            }
        }

    def _build_collapse(self, config: dict) -> dict:
        """Build field collapse configuration for result diversification.

        Field collapse groups results by a field value, returning only the
        top-scoring document per group. inner_hits fetches additional docs
        from each group.

        Args:
            config: Dict with:
                - field: Required. Field to collapse on (e.g., parent_id, category, brand)
                - inner_hits_count: Number of variants per group (default: 3, 0 = none)
                - inner_hits_sort: Sort field for inner hits (default: _score)
                - inner_hits_sort_dir: Sort direction (default: desc for relevance)

        Returns:
            Collapse configuration for Elasticsearch

        Raises:
            ValueError: If required 'field' is not specified
        """
        collapse_field = config.get("field")
        if not collapse_field:
            raise ValueError(
                "Collapse config requires 'field' - the field to group results by"
            )

        inner_hits_count = config.get("inner_hits_count", 3)
        inner_hits_sort = config.get("inner_hits_sort", "_score")
        inner_hits_sort_dir = config.get("inner_hits_sort_dir", "desc")

        collapse: dict[str, Any] = {
            "field": collapse_field,
        }

        # Add inner_hits to fetch variants within each group
        if inner_hits_count > 0:
            collapse["inner_hits"] = {
                "name": "variants",
                "size": inner_hits_count,
                "sort": [{inner_hits_sort: inner_hits_sort_dir}],
            }
            # Limit concurrent group searches to avoid overloading ES
            collapse["max_concurrent_group_searches"] = 4

        return collapse

    def _wrap_with_diversify_retriever(
        self, retriever: dict, config: dict, query: str
    ) -> dict:
        """Wrap a retriever with the diversify retriever for MMR (ES 9.0+).

        Maximum Marginal Relevance (MMR) reduces redundancy by selecting documents
        that are relevant to the query while also being different from already
        selected documents.

        Args:
            retriever: The inner retriever to wrap
            config: Dict with:
                - field: Required. Dense vector field name (e.g., 'embedding')
                - inference_id: Required. Model for query vector generation
                - lambda_: Relevance vs diversity tradeoff (0.0-1.0, default: 0.5)
                  1.0 = pure relevance, 0.0 = maximum diversity
                - rank_window_size: Number of candidates to consider (default: 100)
            query: Search query for query_vector_builder

        Returns:
            Diversify retriever wrapping the inner retriever

        Raises:
            ValueError: If required config fields are missing

        Reference:
            https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/diversify-retriever
        """
        field = config.get("field")
        inference_id = config.get("inference_id")

        if not field:
            raise ValueError(
                "MMR config requires 'field' - the dense vector field name"
            )
        if not inference_id:
            raise ValueError(
                "MMR config requires 'inference_id' - the embedding model ID"
            )

        lambda_val = config.get("lambda_", 0.5)
        rank_window_size = config.get("rank_window_size", 100)

        diversify: dict[str, Any] = {
            "diversify": {
                "_name": "retriever:diversify_mmr",
                "type": "mmr",
                "field": field,
                "lambda": lambda_val,
                "rank_window_size": rank_window_size,
                "retriever": retriever,
            }
        }

        # Add query_vector_builder for generating query embedding
        if query and query.strip():
            diversify["diversify"]["query_vector_builder"] = {
                "text_embedding": {"model_id": inference_id, "model_text": query}
            }

        return diversify

    def _wrap_with_ltr_rescorer(
        self, retriever: dict, config: dict, query: str
    ) -> dict:
        """Wrap a retriever with the rescorer retriever for LTR (ES 9.0+).

        LTR rescoring uses a trained model to re-rank the top N results
        from the initial query based on learned feature combinations.

        Args:
            retriever: The inner retriever to wrap
            config: Dict with:
                - model_id: Required. Trained LTR model ID
                - window_size: Number of top results to rescore (default: 50)
            query: The user's search query (needed for feature extraction)

        Returns:
            Rescorer retriever wrapping the inner retriever

        Raises:
            ValueError: If required 'model_id' is not specified

        Reference:
            https://www.elastic.co/docs/solutions/search/ranking/learning-to-rank-search-usage
            https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/rescorer-retriever
        """
        model_id = config.get("model_id")
        if not model_id:
            raise ValueError(
                "LTR config requires 'model_id' - the trained LTR model ID"
            )

        window_size = config.get("window_size", 50)

        # Use rescorer retriever (ES 9.0+) with learning_to_rank rescore
        # The params must match what was defined in the feature extractors during training
        return {
            "rescorer": {
                "_name": "retriever:ltr_rescorer",
                "rescore": {
                    "window_size": window_size,
                    "learning_to_rank": {
                        "model_id": model_id,
                        "params": {"query": query},
                    },
                },
                "retriever": retriever,
            }
        }

    def _build_aggregations(self) -> dict:
        """Build aggregations from config facets."""
        aggs = {}

        for facet in self.config.get("facets", []):
            field = facet["field"]
            size = facet.get("size", 20)
            aggs[field] = {
                "terms": {
                    "field": field,
                    "size": size,
                }
            }

        # Add stats for range filters
        for range_filter in self.config.get("rangeFilters", []):
            field = range_filter["field"]
            aggs[f"{field}_stats"] = {"stats": {"field": field}}

        return aggs


def build_hybrid_retriever(
    query: str,
    text_fields: list[str],
    semantic_field: str,
    filters: list | None = None,
    ruleset_ids: list[str] | None = None,
    text_weight: float = 0.5,
    semantic_weight: float = 0.5,
    use_linear: bool = True,
) -> dict:
    """Convenience function to build a hybrid text + semantic retriever.

    Uses the LINEAR retriever (ES 8.18+/9.0+) by default for better control
    over result ranking. Falls back to RRF if use_linear=False.

    Linear retriever advantages over RRF:
    - Preserves actual scores (RRF only uses ranks)
    - Allows precise weight tuning via frontend slider
    - MinMax normalization ensures consistent score scaling

    Args:
        query: Search query string
        text_fields: Fields for text matching (with boosts, e.g., ["title^3", "description"])
        semantic_field: Field for semantic search (semantic_text type with inference)
        filters: Filter clauses to apply to both retrievers
        ruleset_ids: Query rule ruleset IDs
        text_weight: Weight for text results (0-1, default 0.5)
        semantic_weight: Weight for semantic results (0-1, default 0.5)
        use_linear: Use linear retriever (True) or RRF (False)

    Returns:
        Complete retriever structure

    Reference:
        https://www.elastic.co/search-labs/blog/linear-retriever-hybrid-search
    """
    filters = filters or []

    # Text retriever
    text_retriever = {
        "standard": {
            "_name": "retriever:text",
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": text_fields,
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                                "_name": "text_relevance",
                            }
                        }
                    ],
                    "filter": filters if filters else [],
                }
            },
        }
    }

    # Semantic retriever (using semantic query for semantic_text field)
    semantic_retriever = {
        "standard": {
            "_name": "retriever:semantic",
            "query": {
                "bool": {
                    "must": [
                        {
                            "semantic": {
                                "field": semantic_field,
                                "query": query,
                            }
                        }
                    ],
                    "filter": filters if filters else [],
                }
            },
        }
    }

    # Combine retrievers
    if use_linear:
        # Linear retriever with weighted combination and MinMax normalization
        combined_retriever = {
            "linear": {
                "_name": "retriever:linear_hybrid",
                "retrievers": [
                    {"retriever": text_retriever, "weight": text_weight},
                    {"retriever": semantic_retriever, "weight": semantic_weight},
                ],
                "normalizer": "minmax",
            }
        }
    else:
        # Legacy RRF for backward compatibility
        combined_retriever = {
            "rrf": {
                "_name": "retriever:rrf",
                "retrievers": [text_retriever, semantic_retriever],
                "rank_window_size": 100,
                "rank_constant": 60,
            }
        }

    # Wrap with rule retriever if needed
    if ruleset_ids:
        return {
            "rule": {
                "_name": "retriever:query_rules",
                "match_criteria": {"query_string": query},
                "ruleset_ids": ruleset_ids,
                "retriever": combined_retriever,
                "rank_window_size": 100,
            }
        }

    return combined_retriever
