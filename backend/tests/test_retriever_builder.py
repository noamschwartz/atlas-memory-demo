"""Regression Tests for RetrieverBuilder

These tests verify the structure of generated Elasticsearch queries.
Run BEFORE and AFTER refactoring to ensure no regressions.

Test Strategy:
- Unit tests that verify output structure (no ES connection needed)
- Cover all optional parameters individually and in combination
- Test both simple and complex use cases
- Verify hard-coded defaults that will change after refactoring

Usage:
    cd backend
    source venv/bin/activate
    pytest tests/test_retriever_builder.py -v

Or run specific test:
    pytest tests/test_retriever_builder.py::TestSimpleTextSearch -v
"""

import pytest

from app.elasticsearch.retriever_builder import RetrieverBuilder, build_hybrid_retriever

# =============================================================================
# Test Fixtures - Common Configurations
# =============================================================================


@pytest.fixture
def minimal_config():
    """Minimal config - just search fields."""
    return {
        "searchFields": ["title", "description"],
        "facets": [],
        "rangeFilters": [],
    }


@pytest.fixture
def ecommerce_config():
    """Full e-commerce config matching current production."""
    return {
        "index": "products",
        "searchFields": ["title^3", "description", "brand^2", "category^1.5"],
        "facets": [
            {"field": "category", "label": "Category", "size": 20},
            {"field": "brand", "label": "Brand", "size": 20},
        ],
        "rangeFilters": [
            {"field": "price", "label": "Price", "min": 0, "max": 2500},
        ],
        # Configurable rank_feature field mappings
        "rankFeatureFields": {
            "popularity": "rank_features.popularity",
            "margin_score": "rank_features.margin_score",
            "freshness": "rank_features.freshness",
            "conversion_rate": "rank_features.conversion_rate",
            "inventory_priority": "rank_features.inventory_priority",
        },
        # Configurable personalization field mappings
        "personalizationFields": {
            "brand": "brand",
            "category": "category",
        },
    }


# =============================================================================
# 1. SIMPLE TEXT SEARCH - Core Functionality
# =============================================================================


class TestSimpleTextSearch:
    """Test basic text search with minimal parameters."""

    def test_simple_query_returns_retriever_structure(self, minimal_config):
        """Most basic use case: just a query string."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop")

        # Must have retriever at top level
        assert "retriever" in result
        assert "from" in result
        assert "size" in result
        assert "aggs" in result
        assert "highlight" in result

    def test_simple_query_uses_standard_retriever(self, minimal_config):
        """Text-only query should use standard retriever."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop")

        retriever = result["retriever"]
        assert "standard" in retriever
        assert retriever["standard"]["_name"] == "retriever:text"

    def test_query_contains_multi_match(self, minimal_config):
        """Text query should use multi_match with configured fields."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop")

        query = result["retriever"]["standard"]["query"]
        assert "bool" in query
        assert "must" in query["bool"]

        must_clause = query["bool"]["must"][0]
        assert "multi_match" in must_clause
        assert must_clause["multi_match"]["query"] == "laptop"
        assert must_clause["multi_match"]["fields"] == ["title", "description"]

    def test_default_pagination(self, minimal_config):
        """Default pagination should be page 1, size 20."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop")

        assert result["from"] == 0
        assert result["size"] == 20

    def test_custom_pagination(self, minimal_config):
        """Custom pagination should calculate from correctly."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop", page=3, page_size=10)

        assert result["from"] == 20  # (3-1) * 10
        assert result["size"] == 10

    def test_highlight_always_included(self, minimal_config):
        """Highlight config should always be present."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop")

        assert "highlight" in result
        assert result["highlight"]["pre_tags"] == ["<mark>"]
        assert result["highlight"]["post_tags"] == ["</mark>"]


# =============================================================================
# 2. BROWSE MODE - Empty Query Handling
# =============================================================================


class TestBrowseMode:
    """Test behavior when no query is provided."""

    def test_empty_query_uses_match_all(self, minimal_config):
        """Empty query should fall back to match_all."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="")

        retriever = result["retriever"]
        assert "standard" in retriever
        assert "match_all" in retriever["standard"]["query"]

    def test_empty_query_with_feature_weights_uses_browse_retriever(
        self, ecommerce_config
    ):
        """Empty query + feature weights should use browse mode with scoring."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(query="", feature_weights={"popularity": 5.0})

        retriever = result["retriever"]
        assert "standard" in retriever
        assert retriever["standard"]["_name"] == "retriever:browse"

    def test_empty_query_without_config_uses_match_all(self, minimal_config):
        """Empty query + feature weights but no rankFeatureFields config uses match_all."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="",
            feature_weights={"popularity": 5.0},  # This will be skipped without config
        )

        retriever = result["retriever"]
        assert "standard" in retriever
        # Without rankFeatureFields, feature_weights has no effect, so it's browse_all
        assert retriever["standard"]["_name"] == "retriever:browse_all"

    def test_whitespace_only_query_treated_as_empty(self, minimal_config):
        """Whitespace-only query should be treated as empty."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="   ")

        retriever = result["retriever"]
        assert "standard" in retriever
        # Should be browse_all or match_all, not text search
        assert "multi_match" not in str(retriever)


# =============================================================================
# 3. FILTERS - Filter Clause Handling
# =============================================================================


class TestFilters:
    """Test filter clause handling."""

    def test_filters_added_to_bool_filter(self, minimal_config):
        """Filters should be added to bool filter clause."""
        builder = RetrieverBuilder(minimal_config)
        filters = [{"term": {"category": "Electronics"}}]
        result = builder.build(query="laptop", filters=filters)

        query = result["retriever"]["standard"]["query"]
        assert "filter" in query["bool"]
        assert query["bool"]["filter"] == filters

    def test_multiple_filters(self, minimal_config):
        """Multiple filters should all be included."""
        builder = RetrieverBuilder(minimal_config)
        filters = [
            {"term": {"category": "Electronics"}},
            {"range": {"price": {"gte": 100, "lte": 500}}},
        ]
        result = builder.build(query="laptop", filters=filters)

        query = result["retriever"]["standard"]["query"]
        assert len(query["bool"]["filter"]) == 2

    def test_filters_with_empty_query(self, minimal_config):
        """Filters should work with browse mode too."""
        builder = RetrieverBuilder(minimal_config)
        filters = [{"term": {"in_stock": True}}]
        result = builder.build(query="", filters=filters)

        # Should still apply filters - check serialized form
        result_str = str(result)
        assert "in_stock" in result_str
        assert "True" in result_str


# =============================================================================
# 4. SORTING
# =============================================================================


class TestSorting:
    """Test sort clause handling."""

    def test_no_sort_by_default(self, minimal_config):
        """No sort clause when sort_by is None (relevance sort)."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop")

        assert "sort" not in result

    def test_score_sort_no_clause(self, minimal_config):
        """sort_by='_score' should not add sort clause."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop", sort_by="_score")

        assert "sort" not in result

    def test_field_sort_includes_score_tiebreaker(self, minimal_config):
        """Field sort should include _score as secondary sort."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop", sort_by="price", sort_dir="asc")

        assert "sort" in result
        assert result["sort"] == [
            {"price": "asc"},
            {"_score": "desc"},
        ]


# =============================================================================
# 5. AGGREGATIONS
# =============================================================================


class TestAggregations:
    """Test aggregation generation from facets config."""

    def test_facets_generate_terms_aggs(self, ecommerce_config):
        """Facet config should generate terms aggregations."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(query="laptop")

        aggs = result["aggs"]
        assert "category" in aggs
        assert "brand" in aggs
        assert aggs["category"]["terms"]["field"] == "category"
        assert aggs["category"]["terms"]["size"] == 20

    def test_range_filters_generate_stats_aggs(self, ecommerce_config):
        """Range filters should generate stats aggregations."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(query="laptop")

        aggs = result["aggs"]
        assert "price_stats" in aggs
        assert aggs["price_stats"]["stats"]["field"] == "price"

    def test_empty_facets_empty_aggs(self, minimal_config):
        """Empty facets config should produce empty aggs."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop")

        assert result["aggs"] == {}


# =============================================================================
# 6. FEATURE WEIGHTS (Rank Features) - CONFIGURABLE FIELDS
# =============================================================================


class TestFeatureWeights:
    """Test rank_feature boosting with configurable field mappings.

    Rank feature fields are now configured via rankFeatureFields in config.
    Features without a mapping are silently skipped.
    """

    def test_feature_weights_add_should_clauses(self, ecommerce_config):
        """Feature weights should add rank_feature should clauses when field is configured."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(query="laptop", feature_weights={"popularity": 5.0})

        query = result["retriever"]["standard"]["query"]["bool"]
        assert "should" in query

        # Find the rank_feature clause
        should_str = str(query["should"])
        assert "rank_feature" in should_str
        assert "rank_features.popularity" in should_str

    def test_configurable_feature_fields(self, ecommerce_config):
        """Feature field mappings come from config.rankFeatureFields."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(
            query="laptop",
            feature_weights={
                "popularity": 5.0,
                "margin_score": 3.0,
                "freshness": 2.0,
                "conversion_rate": 4.0,
                "inventory_priority": 1.0,
            },
        )

        query_str = str(result)

        # These field mappings come from ecommerce_config.rankFeatureFields
        assert "rank_features.popularity" in query_str
        assert "rank_features.margin_score" in query_str
        assert "rank_features.freshness" in query_str
        assert "rank_features.conversion_rate" in query_str
        assert "rank_features.inventory_priority" in query_str

    def test_custom_rank_feature_fields(self):
        """Custom field mappings should work with any field path."""
        custom_config = {
            "searchFields": ["title"],
            "facets": [],
            "rangeFilters": [],
            "rankFeatureFields": {
                "quality": "signals.quality_score",
                "recency": "doc.freshness",
            },
        }
        builder = RetrieverBuilder(custom_config)
        result = builder.build(
            query="laptop", feature_weights={"quality": 5.0, "recency": 3.0}
        )

        query_str = str(result)
        assert "signals.quality_score" in query_str
        assert "doc.freshness" in query_str

    def test_unknown_features_skipped(self, minimal_config):
        """Features without a field mapping should be silently skipped."""
        builder = RetrieverBuilder(minimal_config)  # No rankFeatureFields
        result = builder.build(query="laptop", feature_weights={"unknown_feature": 5.0})

        query = result["retriever"]["standard"]["query"]["bool"]
        # Should not have should clause because feature was skipped
        assert "should" not in query or len(query.get("should", [])) == 0

    def test_zero_weight_excluded(self, ecommerce_config):
        """Features with weight 0 or None should be excluded."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(
            query="laptop", feature_weights={"popularity": 5.0, "margin_score": 0}
        )

        query_str = str(result)
        assert "rank_features.popularity" in query_str
        # margin_score should NOT be present because weight is 0
        assert "rank_features.margin_score" not in query_str

    def test_feature_weights_have_named_queries(self, ecommerce_config):
        """Feature weight clauses should have _name for score breakdown."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(query="laptop", feature_weights={"popularity": 5.0})

        query_str = str(result)
        assert "signal:popularity" in query_str

    def test_no_rank_features_without_config(self, minimal_config):
        """Without rankFeatureFields config, feature_weights should have no effect."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop", feature_weights={"popularity": 10.0, "freshness": 5.0}
        )

        query_str = str(result)
        # No rank_feature clauses should be generated
        assert "rank_feature" not in query_str


# =============================================================================
# 7. PERSONALIZATION - CONFIGURABLE FIELDS
# =============================================================================


class TestPersonalization:
    """Test personalization clauses with configurable field mappings.

    Personalization fields are now configured via personalizationFields in config.
    If a field mapping is missing, that personalization type is skipped.
    """

    def test_preferred_brands_boost(self, ecommerce_config):
        """Preferred brands should add terms boost clause when field is configured."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(
            query="laptop",
            user_preferences={
                "preferred_brands": ["Apple", "Dell"],
                "brand_boost": 2.5,
            },
        )

        query = result["retriever"]["standard"]["query"]["bool"]
        should_str = str(query.get("should", []))

        # Uses "brand" field from ecommerce_config.personalizationFields
        assert '"brand"' in should_str or "'brand'" in should_str
        assert "Apple" in should_str
        assert "Dell" in should_str

    def test_preferred_categories_boost(self, ecommerce_config):
        """Preferred categories should add terms boost clause when field is configured."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(
            query="laptop",
            user_preferences={
                "preferred_categories": ["Electronics"],
                "category_boost": 1.8,
            },
        )

        query = result["retriever"]["standard"]["query"]["bool"]
        should_str = str(query.get("should", []))

        # Uses "category" field from ecommerce_config.personalizationFields
        assert '"category"' in should_str or "'category'" in should_str
        assert "Electronics" in should_str

    def test_custom_personalization_fields(self):
        """Custom field mappings should work with any field names."""
        custom_config = {
            "searchFields": ["title"],
            "facets": [],
            "rangeFilters": [],
            "personalizationFields": {
                "brand": "manufacturer",
                "category": "product_type",
            },
        }
        builder = RetrieverBuilder(custom_config)
        result = builder.build(
            query="laptop",
            user_preferences={
                "preferred_brands": ["Apple"],
                "preferred_categories": ["Electronics"],
            },
        )

        query_str = str(result)
        # Should use custom field names
        assert "manufacturer" in query_str
        assert "product_type" in query_str
        # Should not use default field names
        assert "'brand'" not in query_str
        assert "'category'" not in query_str

    def test_personalization_skipped_without_config(self, minimal_config):
        """Personalization should be skipped without personalizationFields config."""
        builder = RetrieverBuilder(minimal_config)  # No personalizationFields
        result = builder.build(
            query="laptop",
            user_preferences={
                "preferred_brands": ["Apple"],
                "preferred_categories": ["Electronics"],
            },
        )

        query = result["retriever"]["standard"]["query"]["bool"]
        # Should not have should clause because personalization was skipped
        assert "should" not in query or len(query.get("should", [])) == 0

    def test_excluded_brands_must_not(self, ecommerce_config):
        """Excluded brands should add must_not clause when field is configured."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(
            query="laptop", user_preferences={"excluded_brands": ["BadBrand"]}
        )

        query = result["retriever"]["standard"]["query"]["bool"]
        assert "must_not" in query
        must_not_str = str(query["must_not"])
        assert "BadBrand" in must_not_str

    def test_session_context_recent_categories(self, ecommerce_config):
        """Session context should boost recent categories when field is configured."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(
            query="laptop",
            session_context={
                "recent_categories": ["Tech"],
                "recent_category_boost": 1.5,
            },
        )

        query = result["retriever"]["standard"]["query"]["bool"]
        should_str = str(query.get("should", []))

        assert "Tech" in should_str
        assert "session:recent_category" in should_str

    def test_personalization_named_queries(self, ecommerce_config):
        """Personalization clauses should have _name for tracking."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(
            query="laptop", user_preferences={"preferred_brands": ["Apple"]}
        )

        query_str = str(result)
        assert "personalization:preferred_brand" in query_str


# =============================================================================
# 8. QUERY RULES (Rule Retriever)
# =============================================================================


class TestQueryRules:
    """Test rule retriever wrapping."""

    def test_ruleset_ids_wrap_with_rule_retriever(self, minimal_config):
        """Providing ruleset_ids should wrap inner retriever with rule retriever."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop", ruleset_ids=["merchandising"])

        retriever = result["retriever"]
        assert "rule" in retriever
        assert retriever["rule"]["ruleset_ids"] == ["merchandising"]
        assert retriever["rule"]["_name"] == "retriever:query_rules"

    def test_rule_retriever_match_criteria(self, minimal_config):
        """Rule retriever should have match_criteria with query_string."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop", ruleset_ids=["merchandising"])

        rule = result["retriever"]["rule"]
        assert rule["match_criteria"]["query_string"] == "laptop"

    def test_rule_retriever_wraps_inner(self, minimal_config):
        """Rule retriever should contain inner standard retriever."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop", ruleset_ids=["merchandising"])

        inner = result["retriever"]["rule"]["retriever"]
        assert "standard" in inner

    def test_rule_retriever_rank_window_size(self, minimal_config):
        """Rule retriever rank_window_size should be >= page_size."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop", ruleset_ids=["merchandising"], page_size=50
        )

        rule = result["retriever"]["rule"]
        assert rule["rank_window_size"] >= 50


# =============================================================================
# 9. SEMANTIC SEARCH
# =============================================================================


class TestSemanticSearch:
    """Test semantic search retriever."""

    def test_semantic_config_adds_semantic_retriever(self, minimal_config):
        """Semantic config should add semantic retriever."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop",
            semantic_config={"field": "semantic_text", "query": "laptop"},
        )

        # With both text and semantic, should combine them
        retriever = result["retriever"]
        # Could be linear, rrf, or the semantic retriever
        retriever_str = str(retriever)
        assert "retriever:semantic" in retriever_str

    def test_semantic_empty_query_skipped(self, minimal_config):
        """Semantic search with empty query should be skipped."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop", semantic_config={"field": "semantic_text", "query": ""}
        )

        # Should only have text retriever, not semantic
        retriever_str = str(result["retriever"])
        assert "retriever:text" in retriever_str
        # semantic should NOT be present
        assert "retriever:semantic" not in retriever_str


# =============================================================================
# 10. HYBRID SEARCH (Linear/RRF)
# =============================================================================


class TestHybridSearch:
    """Test hybrid search combining text + semantic."""

    def test_hybrid_uses_linear_by_default(self, minimal_config):
        """Hybrid search should use linear retriever by default."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop",
            semantic_config={"field": "semantic_text", "query": "laptop"},
            hybrid_config={"enabled": True, "semantic_weight": 0.3, "text_weight": 0.7},
        )

        retriever = result["retriever"]
        # Should have linear retriever
        assert "linear" in retriever or "linear" in str(retriever)

    def test_hybrid_rrf_when_requested(self, minimal_config):
        """use_rrf=True should use RRF instead of linear."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop",
            semantic_config={"field": "semantic_text", "query": "laptop"},
            use_rrf=True,
        )

        retriever_str = str(result["retriever"])
        assert "rrf" in retriever_str

    def test_hybrid_weights_configurable(self, minimal_config):
        """Hybrid weights should be configurable."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop",
            semantic_config={"field": "semantic_text", "query": "laptop"},
            hybrid_config={"enabled": True, "semantic_weight": 0.8, "text_weight": 0.2},
        )

        # The weights should appear in the linear retriever config
        retriever_str = str(result["retriever"])
        # Weight values should be present
        assert "0.8" in retriever_str or "0.2" in retriever_str


# =============================================================================
# 11. FIELD COLLAPSE (Diversification)
# =============================================================================


class TestFieldCollapse:
    """Test field collapse for result diversification."""

    def test_collapse_config_adds_collapse(self, minimal_config):
        """Collapse config should add collapse to query body."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop", collapse_config={"field": "brand", "inner_hits_count": 3}
        )

        assert "collapse" in result
        assert result["collapse"]["field"] == "brand"

    def test_collapse_inner_hits(self, minimal_config):
        """Collapse should include inner_hits when count > 0."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop",
            collapse_config={
                "field": "parent_id",
                "inner_hits_count": 3,
                "inner_hits_sort": "price",
                "inner_hits_sort_dir": "asc",
            },
        )

        collapse = result["collapse"]
        assert "inner_hits" in collapse
        assert collapse["inner_hits"]["name"] == "variants"
        assert collapse["inner_hits"]["size"] == 3

    def test_collapse_no_inner_hits_when_zero(self, minimal_config):
        """inner_hits_count=0 should not add inner_hits."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop", collapse_config={"field": "brand", "inner_hits_count": 0}
        )

        collapse = result["collapse"]
        assert "inner_hits" not in collapse

    def test_collapse_requires_field(self, minimal_config):
        """Collapse requires field - no defaults."""
        builder = RetrieverBuilder(minimal_config)

        import pytest

        with pytest.raises(ValueError, match="requires 'field'"):
            builder.build(
                query="laptop",
                collapse_config={"inner_hits_count": 3},  # No field
            )


# =============================================================================
# 12. MMR DIVERSIFICATION
# =============================================================================


class TestMMRDiversification:
    """Test MMR diversify retriever."""

    def test_mmr_config_wraps_with_diversify(self, minimal_config):
        """MMR config should wrap with diversify retriever when properly configured."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop",
            mmr_config={
                "enabled": True,
                "field": "embedding",
                "inference_id": ".my-embeddings",
                "lambda_": 0.7,
                "rank_window_size": 100,
            },
        )

        retriever_str = str(result["retriever"])
        assert "diversify" in retriever_str
        assert "retriever:diversify_mmr" in retriever_str

    def test_mmr_disabled_no_diversify(self, minimal_config):
        """MMR with enabled=False should not add diversify."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="laptop", mmr_config={"enabled": False})

        retriever_str = str(result["retriever"])
        assert "diversify" not in retriever_str

    def test_mmr_requires_field_and_inference_id(self, minimal_config):
        """MMR requires both field and inference_id - no defaults."""
        builder = RetrieverBuilder(minimal_config)

        # Missing inference_id should raise
        import pytest

        with pytest.raises(ValueError, match="requires 'inference_id'"):
            builder.build(
                query="laptop", mmr_config={"enabled": True, "field": "embedding"}
            )

        # Missing field should raise
        with pytest.raises(ValueError, match="requires 'field'"):
            builder.build(
                query="laptop",
                mmr_config={"enabled": True, "inference_id": ".my-embeddings"},
            )


# =============================================================================
# 13. LTR RESCORING
# =============================================================================


class TestLTRRescoring:
    """Test Learning to Rank rescoring."""

    def test_ltr_config_wraps_with_rescorer(self, minimal_config):
        """LTR config should wrap with rescorer retriever."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop", ltr_config={"model_id": "my-ltr-model", "window_size": 50}
        )

        retriever = result["retriever"]
        assert "rescorer" in retriever
        assert retriever["rescorer"]["_name"] == "retriever:ltr_rescorer"

    def test_ltr_model_id_configurable(self, minimal_config):
        """LTR model_id should be configurable."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop", ltr_config={"model_id": "custom-model", "window_size": 100}
        )

        rescore = result["retriever"]["rescorer"]["rescore"]
        assert rescore["learning_to_rank"]["model_id"] == "custom-model"

    def test_ltr_requires_query(self, minimal_config):
        """LTR should not be applied without a query."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="",  # Empty query
            ltr_config={"model_id": "my-model", "window_size": 50},
        )

        # Should NOT have rescorer when query is empty
        retriever_str = str(result["retriever"])
        assert "rescorer" not in retriever_str

    def test_ltr_requires_model_id(self, minimal_config):
        """LTR requires model_id - no defaults."""
        builder = RetrieverBuilder(minimal_config)

        import pytest

        with pytest.raises(ValueError, match="requires 'model_id'"):
            builder.build(
                query="laptop",
                ltr_config={"window_size": 50},  # No model_id
            )


# =============================================================================
# 14. RERANKER
# =============================================================================


class TestReranker:
    """Test text similarity reranker."""

    def test_reranker_config_wraps_retriever(self, minimal_config):
        """Reranker config should wrap with text_similarity_reranker."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop",
            reranker_config={
                "field": "description",
                "model_id": ".rerank-1",
                "window_size": 100,
            },
        )

        retriever_str = str(result["retriever"])
        assert "text_similarity_reranker" in retriever_str

    def test_reranker_requires_field_and_model_id(self, minimal_config):
        """Reranker requires both field and model_id - no defaults."""
        builder = RetrieverBuilder(minimal_config)

        import pytest

        # Missing field should raise
        with pytest.raises(ValueError, match="requires 'field'"):
            builder.build(query="laptop", reranker_config={"model_id": ".rerank-1"})

        # Missing model_id should raise
        with pytest.raises(ValueError, match="requires 'model_id'"):
            builder.build(query="laptop", reranker_config={"field": "description"})


# =============================================================================
# 15. RETRIEVER WRAPPING ORDER
# =============================================================================


class TestRetrieverWrappingOrder:
    """Test that retrievers are wrapped in the correct order.

    Order should be (innermost to outermost):
    1. standard (text/semantic)
    2. linear/rrf (hybrid combination)
    3. text_similarity_reranker
    4. diversify (MMR)
    5. rule (MUST be outermost)
    6. rescorer (LTR) - wraps the whole thing
    """

    def test_rule_retriever_is_outermost(self, minimal_config):
        """Rule retriever should wrap everything else."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop",
            ruleset_ids=["merchandising"],
            feature_weights={"popularity": 5.0},
        )

        # Top level should be rule
        retriever = result["retriever"]
        assert "rule" in retriever

        # Inner should be standard
        inner = retriever["rule"]["retriever"]
        assert "standard" in inner

    def test_ltr_wraps_rule_retriever(self, minimal_config):
        """LTR rescorer should wrap rule retriever (outermost)."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop",
            ruleset_ids=["merchandising"],
            ltr_config={"model_id": "test-model", "window_size": 50},
        )

        # Top level should be rescorer (LTR)
        retriever = result["retriever"]
        assert "rescorer" in retriever

        # Inner should be rule
        inner = retriever["rescorer"]["retriever"]
        assert "rule" in inner

    def test_mmr_before_rule(self, minimal_config):
        """MMR diversify should be inside rule retriever."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(
            query="laptop",
            ruleset_ids=["merchandising"],
            mmr_config={
                "enabled": True,
                "field": "embedding",
                "inference_id": ".my-embeddings",
                "lambda_": 0.5,
            },
        )

        # Top level should be rule
        retriever = result["retriever"]
        assert "rule" in retriever

        # Inside rule should be diversify
        inner = retriever["rule"]["retriever"]
        assert "diversify" in inner


# =============================================================================
# 16. DEFAULT SEARCH FIELDS - CONFIGURABLE
# =============================================================================


class TestDefaultSearchFields:
    """Test default search field behavior.

    Default fields are generic (title, description).
    Configure searchFields in config for domain-specific boosting.
    """

    def test_default_search_fields_from_config(self, ecommerce_config):
        """Search fields should come from config."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(query="laptop")

        query = result["retriever"]["standard"]["query"]["bool"]["must"][0]
        fields = query["multi_match"]["fields"]

        assert "title^3" in fields
        assert "brand^2" in fields

    def test_fallback_search_fields(self):
        """Fallback when no searchFields in config uses generic defaults."""
        builder = RetrieverBuilder({})  # Empty config

        # Generic defaults (not e-commerce specific)
        assert builder.search_fields == ["title", "description"]


# =============================================================================
# 17. CONVENIENCE FUNCTION: build_hybrid_retriever
# =============================================================================


class TestBuildHybridRetriever:
    """Test the standalone build_hybrid_retriever function."""

    def test_builds_hybrid_structure(self):
        """Should build hybrid text + semantic retriever."""
        result = build_hybrid_retriever(
            query="laptop",
            text_fields=["title", "description"],
            semantic_field="semantic_text",
        )

        # Should have linear by default
        assert "linear" in result

    def test_rrf_option(self):
        """use_linear=False should use RRF."""
        result = build_hybrid_retriever(
            query="laptop",
            text_fields=["title"],
            semantic_field="semantic_text",
            use_linear=False,
        )

        assert "rrf" in result

    def test_rule_retriever_wrapping(self):
        """Should wrap with rule retriever if ruleset_ids provided."""
        result = build_hybrid_retriever(
            query="laptop",
            text_fields=["title"],
            semantic_field="semantic_text",
            ruleset_ids=["merchandising"],
        )

        assert "rule" in result


# =============================================================================
# 18. COMBINED SCENARIOS - Integration Tests
# =============================================================================


class TestCombinedScenarios:
    """Test realistic combined scenarios."""

    def test_full_ecommerce_search(self, ecommerce_config):
        """Full e-commerce search with all features."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(
            query="wireless headphones",
            filters=[{"term": {"in_stock": True}}],
            page=1,
            page_size=12,
            ruleset_ids=["merchandising"],
            feature_weights={
                "popularity": 7.0,
                "conversion_rate": 5.0,
            },
            user_preferences={
                "preferred_brands": ["Sony", "Bose"],
                "brand_boost": 2.0,
            },
        )

        # Should have complete structure
        assert "retriever" in result
        assert "aggs" in result
        assert "highlight" in result

        # Rule retriever should be outermost
        assert "rule" in result["retriever"]

        # Should have personalization and feature weights
        retriever_str = str(result)
        assert "Sony" in retriever_str
        assert "rank_features.popularity" in retriever_str

    def test_simple_search_minimal_config(self, minimal_config):
        """Simple search should work with minimal config."""
        builder = RetrieverBuilder(minimal_config)
        result = builder.build(query="test")

        # Should work without errors
        assert "retriever" in result
        assert "standard" in result["retriever"]

    def test_browse_with_personalization(self, ecommerce_config):
        """Browse mode with personalization should work."""
        builder = RetrieverBuilder(ecommerce_config)
        result = builder.build(
            query="",
            user_preferences={
                "preferred_categories": ["Electronics"],
                "category_boost": 2.0,
            },
        )

        # Should have browse retriever with personalization
        retriever = result["retriever"]
        assert "standard" in retriever

        retriever_str = str(retriever)
        assert "Electronics" in retriever_str


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
