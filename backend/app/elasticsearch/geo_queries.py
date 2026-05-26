"""Reusable Elasticsearch geo query builders.

Provides functions to build geo_distance, geo_bounding_box, geo_shape,
distance sort, and geo aggregation clauses for Elasticsearch queries.
"""

from typing import Any


def build_geo_distance_filter(
    field: str, lat: float, lon: float, distance: str
) -> dict[str, Any]:
    """Build a geo_distance filter.

    Args:
        field: Geo-point field name (e.g. "location").
        lat: Latitude of the centre point.
        lon: Longitude of the centre point.
        distance: Distance string (e.g. "10km", "5mi").

    Returns:
        Elasticsearch geo_distance filter clause.
    """
    return {
        "geo_distance": {
            "distance": distance,
            field: {"lat": lat, "lon": lon},
        }
    }


def build_geo_bounding_box_filter(
    field: str,
    top_left: dict[str, float],
    bottom_right: dict[str, float],
) -> dict[str, Any]:
    """Build a geo_bounding_box filter.

    Args:
        field: Geo-point field name.
        top_left: Dict with "lat" and "lon" for the top-left corner.
        bottom_right: Dict with "lat" and "lon" for the bottom-right corner.

    Returns:
        Elasticsearch geo_bounding_box filter clause.
    """
    return {
        "geo_bounding_box": {
            field: {
                "top_left": top_left,
                "bottom_right": bottom_right,
            }
        }
    }


def build_geo_distance_sort(
    field: str, lat: float, lon: float, unit: str = "km"
) -> dict[str, Any]:
    """Build a _geo_distance sort clause.

    Args:
        field: Geo-point field name.
        lat: Latitude of the origin.
        lon: Longitude of the origin.
        unit: Distance unit (default "km").

    Returns:
        Elasticsearch sort clause for geo distance.
    """
    return {
        "_geo_distance": {
            field: {"lat": lat, "lon": lon},
            "order": "asc",
            "unit": unit,
            "mode": "min",
            "distance_type": "arc",
        }
    }


def build_geo_aggregation(
    field: str, agg_type: str = "geotile_grid", precision: int = 8
) -> dict[str, Any]:
    """Build a geo grid aggregation.

    Args:
        field: Geo-point field name.
        agg_type: One of "geotile_grid" or "geohash_grid".
        precision: Grid precision level.

    Returns:
        Elasticsearch aggregation clause.
    """
    return {
        agg_type: {
            "field": field,
            "precision": precision,
        }
    }


def build_geo_shape_filter(
    field: str, shape: dict[str, Any], relation: str = "intersects"
) -> dict[str, Any]:
    """Build a geo_shape query filter.

    Args:
        field: Geo-shape field name (e.g. "delivery_zone").
        shape: GeoJSON shape dict (e.g. {"type": "point", "coordinates": [lon, lat]}).
        relation: Spatial relation - "intersects", "within", "contains", "disjoint".

    Returns:
        Elasticsearch geo_shape query clause.
    """
    return {
        "geo_shape": {
            field: {
                "shape": shape,
                "relation": relation,
            }
        }
    }
