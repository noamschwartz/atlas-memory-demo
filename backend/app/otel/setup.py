"""OpenTelemetry SDK setup for Search OTel UBI Bridge.

Configures:
- TracerProvider with OTLP exporter to Elastic APM
- Resource attributes (service.name, deployment.environment)
- W3C TraceContext propagator (for distributed tracing via traceparent header)
- FastAPI auto-instrumentation
- Elasticsearch client auto-instrumentation
- Logging instrumentation (correlates logs with traces)

Key Learning: Elastic APM on port 443 expects OTLP/HTTP, not gRPC.
Use OTLPSpanExporter from opentelemetry.exporter.otlp.proto.http.trace_exporter
"""

import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator

# Use HTTP exporter for Elastic APM on port 443
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# Propagators for distributed tracing (extracts traceparent header)
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from ..config import settings

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer: trace.Tracer | None = None


def _parse_otlp_headers(headers_str: str) -> dict:
    """Parse OTEL_EXPORTER_OTLP_HEADERS format: "key1=value1,key2=value2"

    IMPORTANT: Elastic Cloud provides headers with "Bearer" already included:
        Authorization=Bearer <token>

    This function handles both formats:
    - "Authorization=Bearer token" → {"Authorization": "Bearer token"}
    - "Authorization=token" → {"Authorization": "Bearer token"} (adds Bearer)

    See: hive-mind/troubleshooting/OTEL_ENV_VAR_FORMATTING.md
    """
    if not headers_str:
        return {}

    headers = {}
    for pair in headers_str.split(","):
        if "=" in pair:
            key, value = pair.split("=", 1)
            key = key.strip()
            value = value.strip()

            # For Authorization header, ensure Bearer prefix exists
            # but DON'T double it if already present
            if key.lower() == "authorization":
                if not value.lower().startswith("bearer "):
                    value = f"Bearer {value}"
                    logger.debug("Added 'Bearer' prefix to Authorization header")

            headers[key] = value

    return headers


def _parse_resource_attributes(attrs_str: str) -> dict:
    """Parse OTEL_RESOURCE_ATTRIBUTES format: "key1=value1,key2=value2" """
    if not attrs_str:
        return {}

    attrs = {}
    for pair in attrs_str.split(","):
        if "=" in pair:
            key, value = pair.split("=", 1)
            attrs[key.strip()] = value.strip()
    return attrs


def init_otel(app=None) -> bool:
    """Initialize OpenTelemetry SDK with OTLP export to Elastic APM.

    Supports standard OTel environment variables:
    - OTEL_ENABLED: Set to "false" to explicitly disable (default: true if endpoint set)
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint URL
    - OTEL_EXPORTER_OTLP_HEADERS: Headers in "Key=Value,Key2=Value2" format
    - OTEL_RESOURCE_ATTRIBUTES: Resource attrs in "key=value,key2=value2" format

    Also supports Elastic-specific:
    - ELASTIC_APM_ENDPOINT: Alternative to OTEL_EXPORTER_OTLP_ENDPOINT
    - ELASTIC_APM_SECRET_TOKEN: Alternative to headers for auth

    Args:
        app: FastAPI application instance for auto-instrumentation

    Returns:
        True if OTel was initialized, False if skipped (disabled or no endpoint)
    """
    global _tracer

    # Check for explicit disable flag
    otel_enabled = settings.OTEL_ENABLED.lower()
    if otel_enabled == "false":
        logger.info("OpenTelemetry explicitly disabled via OTEL_ENABLED=false")
        return False

    # Get OTLP endpoint from environment
    otlp_endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    elastic_apm_endpoint = settings.ELASTIC_APM_ENDPOINT

    # Use ELASTIC_APM_ENDPOINT if OTLP endpoint not set
    if not otlp_endpoint and elastic_apm_endpoint:
        otlp_endpoint = elastic_apm_endpoint

    if not otlp_endpoint:
        logger.warning(
            "OpenTelemetry disabled: No OTEL_EXPORTER_OTLP_ENDPOINT or "
            "ELASTIC_APM_ENDPOINT configured. Set OTEL_ENABLED=false to suppress this warning."
        )
        return False

    # Parse auth headers from standard env var
    # Format expected: "Authorization=Bearer <token>" (Bearer included in value)
    headers = _parse_otlp_headers(settings.OTEL_EXPORTER_OTLP_HEADERS)

    if headers:
        logger.debug(f"Using OTEL_EXPORTER_OTLP_HEADERS: {list(headers.keys())}")
    else:
        # Fallback to Elastic-specific token if no headers
        # ELASTIC_APM_SECRET_TOKEN is just the token, we add "Bearer"
        apm_secret_token = settings.ELASTIC_APM_SECRET_TOKEN
        if apm_secret_token:
            # Don't double-add Bearer if someone put it in the token value
            if apm_secret_token.lower().startswith("bearer "):
                headers["Authorization"] = apm_secret_token
            else:
                headers["Authorization"] = f"Bearer {apm_secret_token}"
            logger.debug("Using ELASTIC_APM_SECRET_TOKEN for auth")

    # Parse resource attributes from standard env var
    resource_attrs = _parse_resource_attributes(settings.OTEL_RESOURCE_ATTRIBUTES)

    # Apply defaults if not set in OTEL_RESOURCE_ATTRIBUTES
    if "service.name" not in resource_attrs:
        resource_attrs["service.name"] = settings.OTEL_SERVICE_NAME
    if "service.version" not in resource_attrs:
        resource_attrs["service.version"] = settings.OTEL_SERVICE_VERSION
    if "deployment.environment" not in resource_attrs:
        resource_attrs["deployment.environment"] = settings.OTEL_DEPLOYMENT_ENVIRONMENT

    resource_attrs["service.namespace"] = "search-otel-ubi"

    # Configure W3C TraceContext propagator FIRST (before TracerProvider)
    # This enables extraction of traceparent header from incoming requests
    propagator = CompositePropagator(
        [
            TraceContextTextMapPropagator(),  # W3C traceparent/tracestate
            W3CBaggagePropagator(),  # W3C baggage
        ]
    )
    set_global_textmap(propagator)
    logger.info("W3C TraceContext propagator configured for distributed tracing")

    resource = Resource.create(resource_attrs)
    service_name = resource_attrs.get("service.name", "search-api")
    service_version = resource_attrs.get("service.version", "1.0.0")

    # Create TracerProvider
    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter (HTTP for Elastic APM on port 443)
    # Elastic APM OTLP endpoint expects /v1/traces path
    traces_endpoint = otlp_endpoint
    if not traces_endpoint.endswith("/v1/traces"):
        traces_endpoint = f"{otlp_endpoint.rstrip('/')}/v1/traces"

    try:
        exporter = OTLPSpanExporter(
            endpoint=traces_endpoint,
            headers=headers if headers else None,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info(f"OTel OTLP exporter configured: {traces_endpoint}")
        if headers:
            logger.info(f"OTel auth headers: {list(headers.keys())}")
    except Exception as e:
        logger.error(f"Failed to configure OTLP exporter: {e}")
        return False

    # Set global TracerProvider
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("search-api", service_version)

    # Auto-instrument FastAPI
    # NOTE: Must be done AFTER setting TracerProvider and propagator
    if app:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI auto-instrumentation enabled")

    # Auto-instrument Elasticsearch client
    # Note: elasticsearch-py 8.x+ has native OTel support - the instrumentor
    # will detect this and defer to native instrumentation (which is preferred)
    ElasticsearchInstrumentor().instrument()
    logger.info("Elasticsearch client instrumentation configured")

    # Instrument logging (adds trace_id to logs)
    LoggingInstrumentor().instrument(set_logging_format=True)
    logger.info("Logging instrumentation enabled (trace correlation)")

    logger.info(
        f"OpenTelemetry initialized: service={service_name}, "
        f"version={service_version}, env={resource_attrs.get('deployment.environment')}"
    )

    return True


def get_tracer() -> trace.Tracer:
    """Get the configured tracer for creating custom spans.

    Returns a NoOp tracer if OTel is not initialized.

    Usage:
        from app.otel import get_tracer

        tracer = get_tracer()
        with tracer.start_as_current_span("search.execute") as span:
            span.set_attribute("search.user_query", query)
            # ... do work ...
    """
    global _tracer
    if _tracer is None:
        # Return NoOp tracer if not initialized
        return trace.get_tracer("search-api")
    return _tracer


def shutdown_otel():
    """Shutdown OTel SDK, flushing any pending spans.

    Call this at application shutdown.
    """
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()
        logger.info("OpenTelemetry shutdown complete")
