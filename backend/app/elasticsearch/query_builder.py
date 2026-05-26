"""Query Builder with Template Support

Builds Elasticsearch queries from templates and configuration.
Supports simple variable substitution and extensibility via modifiers.

Templates are JSON files in templates/queries/ with {{variable}} placeholders.
Variables can have defaults: {{field:default_value}}
"""

import copy
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "templates" / "queries"


def build_filter_clauses(filters: dict) -> list:
    """Convert a filter dict to a list of Elasticsearch filter clauses.

    This is a shared utility used by both QueryBuilder and RetrieverBuilder.

    Handles:
    - field_min/field_max → range queries
    - bool values → term queries
    - list values → terms queries
    - other values → term queries

    Args:
        filters: Dict of field -> value filters

    Returns:
        List of ES filter clause dicts
    """
    clauses = []

    for field, value in filters.items():
        if value is None:
            continue

        if field.endswith("_min"):
            # Range filter: min
            actual_field = field[:-4]
            clauses.append({"range": {actual_field: {"gte": value}}})
        elif field.endswith("_max"):
            # Range filter: max
            actual_field = field[:-4]
            clauses.append({"range": {actual_field: {"lte": value}}})
        elif isinstance(value, bool):
            clauses.append({"term": {field: value}})
        elif isinstance(value, list):
            clauses.append({"terms": {field: value}})
        else:
            clauses.append({"term": {field: value}})

    return clauses


def load_template(template_name: str) -> dict:
    """Load a query template by name.

    Args:
        template_name: Template name (e.g., "simple") or path to JSON file

    Returns:
        Template dict with {{placeholders}}
    """
    # Check if it's a file path
    if template_name.endswith(".json"):
        template_path = Path(template_name)
    else:
        template_path = TEMPLATES_DIR / f"{template_name}.json"

    if not template_path.exists():
        logger.warning(f"Template {template_name} not found, using simple")
        template_path = TEMPLATES_DIR / "simple.json"

    with open(template_path) as f:
        template = json.load(f)

    # Remove metadata fields
    template.pop("_name", None)
    template.pop("_description", None)

    return template


def get_nested_value(variables: dict, path: str) -> Any:
    """Get a nested value from variables dict using dot notation.

    Args:
        variables: Dict to search
        path: Dot-separated path like 'feature_weights.popularity'

    Returns:
        Value at path, or None if not found
    """
    parts = path.split(".")
    current = variables
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def substitute_variables(obj: Any, variables: dict) -> Any:
    """Recursively substitute {{variable}} placeholders in a template.

    Supports:
    - {{variable}} - replaced with value from variables dict
    - {{variable:default}} - uses default if variable not in dict
    - {{parent.child}} - nested dot notation access
    - {{parent.child:default}} - nested with default
    - String values are substituted
    - "{{variable}}" as entire value is replaced with actual type (list, dict, etc.)
    """
    if isinstance(obj, str):
        # Check if entire string is a placeholder (supports dot notation)
        match = re.fullmatch(r"\{\{([\w.]+)(?::([^}]*))?\}\}", obj)
        if match:
            var_path = match.group(1)
            default = match.group(2)
            value = get_nested_value(variables, var_path)
            if value is not None:
                return value
            elif default is not None:
                # Try to parse default as number if appropriate
                try:
                    if "." in default:
                        return float(default)
                    return int(default)
                except ValueError:
                    return default
            else:
                return obj  # Leave as-is if no value and no default

        # Partial substitution for embedded placeholders
        def replace_match(m):
            var_path = m.group(1)
            default = m.group(2)
            value = get_nested_value(variables, var_path)
            if value is not None:
                return str(value) if not isinstance(value, str) else value
            elif default is not None:
                return default
            return m.group(0)

        return re.sub(r"\{\{([\w.]+)(?::([^}]*))?\}\}", replace_match, obj)

    elif isinstance(obj, dict):
        # Remove _comment fields (used for documentation in templates)
        return {
            k: substitute_variables(v, variables)
            for k, v in obj.items()
            if not k.startswith("_")
        }

    elif isinstance(obj, list):
        # Filter out comment-only objects and substitute remaining items
        result = []
        for item in obj:
            substituted = substitute_variables(item, variables)
            # Skip objects that only have _comment keys (they're documentation)
            if isinstance(substituted, dict):
                non_comment_keys = [
                    k for k in substituted.keys() if not k.startswith("_")
                ]
                if not non_comment_keys:
                    continue  # Skip this item entirely
            result.append(substituted)
        return result

    else:
        return obj


class QueryBuilder:
    """Builds Elasticsearch queries from config and templates.

    Usage:
        builder = QueryBuilder(config)
        query = builder.build(
            query="laptop",
            filters={"category": "Electronics"},
            page=1,
            page_size=20
        )
    """

    def __init__(self, config: dict):
        """Initialize with search configuration.

        Args:
            config: Dict with index, queryTemplate, searchFields, facets, etc.
        """
        self.config = config
        self.template = load_template(config.get("queryTemplate", "simple"))
        self.template_vars = config.get("templateVars", {})

    def build(
        self,
        query: str,
        filters: dict | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "desc",
        feature_weights: dict | None = None,
        user_preferences: dict | None = None,
        session_context: dict | None = None,
    ) -> dict:
        """Build the complete Elasticsearch query.

        Args:
            query: Search query string
            filters: Dict of field -> value filters
            page: Page number (1-indexed)
            page_size: Results per page
            sort_by: Field to sort by (None = relevance)
            sort_dir: Sort direction ('asc' or 'desc')
            feature_weights: Dict of rank_feature weights (0-100 for each signal)
                e.g., {"popularity": 50, "margin_score": 30, ...}
            user_preferences: Dict of user personalization preferences
                e.g., {"preferred_brands": ["Nike"], "brand_boost": 2.0}
            session_context: Dict of session context for ranking
                e.g., {"recent_categories": ["Electronics"], "recent_category_boost": 1.3}

        Returns:
            Complete Elasticsearch query dict
        """
        # Build filter clauses
        filter_clauses = self._build_filters(filters or {})

        # Build aggregations
        aggregations = self._build_aggregations()

        # Build sort
        sort = self._build_sort(sort_by, sort_dir)

        # Normalize feature weights (convert 0-100 scale to boost values)
        normalized_weights = {}
        if feature_weights:
            for feature, weight in feature_weights.items():
                # Convert 0-100 scale to 0-10 boost scale
                # 0 = disabled, 50 = normal (1.0), 100 = max boost (10)
                if weight == 0:
                    normalized_weights[feature] = 0.001  # Near-zero but valid
                else:
                    normalized_weights[feature] = weight / 10.0

        # Build user preferences with defaults
        user_prefs = {
            "preferred_brands": [],
            "excluded_brands": [],
            "preferred_categories": [],
            "brand_boost": 2.0,
            "category_boost": 1.5,
        }
        if user_preferences:
            user_prefs.update(
                {k: v for k, v in user_preferences.items() if v is not None}
            )

        # Build session context with defaults
        session_ctx = {
            "recent_categories": [],
            "recent_brands": [],
            "recent_category_boost": 1.3,
        }
        if session_context:
            session_ctx.update(
                {k: v for k, v in session_context.items() if v is not None}
            )

        # Prepare variables for template
        variables = {
            **self.template_vars,
            "query": query or "*",
            "search_fields": self.config.get("searchFields", ["*"]),
            "filters": filter_clauses,
            "aggregations": aggregations,
            "from": (page - 1) * page_size,
            "size": page_size,
            "sort": sort,
            "feature_weights": normalized_weights,
            "user_preferences": user_prefs,
            "session_context": session_ctx,
        }

        # Determine which template to use
        has_personalization = (
            user_prefs.get("preferred_brands")
            or user_prefs.get("preferred_categories")
            or session_ctx.get("recent_categories")
        )

        # Use match_all template if no query AND no feature weights AND no personalization
        if not query or query.strip() == "":
            if normalized_weights or has_personalization:
                # Lab Mode or Personalized: use rank_features_browse template
                template = load_template("rank_features_browse")
            else:
                template = load_template("match_all")
        elif has_personalization and normalized_weights:
            # Both personalization and feature weights: use personalized_named template
            template = load_template("personalized_named")
        else:
            template = copy.deepcopy(self.template)

        # Substitute variables
        result = substitute_variables(template, variables)

        return result

    def _build_filters(self, filters: dict) -> list:
        """Build filter clauses from filter dict."""
        return build_filter_clauses(filters)

    def _build_aggregations(self) -> dict:
        """Build aggregations from config facets."""
        aggs = {}

        for facet in self.config.get("facets", []):
            field = facet["field"]
            size = facet.get("size", 20)
            aggs[field] = {"terms": {"field": field, "size": size}}

        # Add stats for range filters
        for range_filter in self.config.get("rangeFilters", []):
            field = range_filter["field"]
            aggs[f"{field}_stats"] = {"stats": {"field": field}}

        return aggs

    def _build_sort(self, sort_by: str | None, sort_dir: str) -> list:
        """Build sort clause."""
        if not sort_by or sort_by == "_score":
            return [{"_score": "desc"}]

        return [
            {sort_by: sort_dir},
            {"_score": "desc"},  # Secondary sort by relevance
        ]


def get_index_fields(es_client, index: str) -> dict:
    """Introspect an index to get its field mappings.

    Useful for LLM agents to discover available fields.

    Returns:
        Dict with field info: {field_name: {type, searchable, aggregatable}}
    """
    mapping = es_client.indices.get_mapping(index=index)

    fields = {}

    def extract_fields(properties: dict, prefix: str = ""):
        for field_name, field_def in properties.items():
            full_name = f"{prefix}{field_name}" if prefix else field_name
            field_type = field_def.get("type", "object")

            fields[full_name] = {
                "type": field_type,
                "searchable": field_type in ["text", "keyword", "search_as_you_type"],
                "aggregatable": field_type
                in ["keyword", "integer", "long", "float", "double", "date", "boolean"],
                "sortable": field_type not in ["text", "object", "nested"],
            }

            # Recurse into nested/object fields
            if "properties" in field_def:
                extract_fields(field_def["properties"], f"{full_name}.")

            # Note keyword subfield
            if "fields" in field_def and "keyword" in field_def["fields"]:
                fields[f"{full_name}.keyword"] = {
                    "type": "keyword",
                    "searchable": True,
                    "aggregatable": True,
                    "sortable": True,
                }

    # Get properties from first index in response
    index_name = list(mapping.keys())[0]
    properties = mapping[index_name]["mappings"].get("properties", {})
    extract_fields(properties)

    return fields
