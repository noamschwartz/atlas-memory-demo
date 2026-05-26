"""Configuration management for the backend service.

Loads configuration from environment variables using python-decouple.
All Elastic credentials should be stored in .env file.
Privileged keys (admin, workflows) are loaded from .secrets/ at runtime.
"""

import os
from pathlib import Path

from decouple import AutoConfig
from dotenv import dotenv_values


_config = AutoConfig(search_path=Path(__file__).resolve().parents[1])

_SECRETS_PATH = Path(__file__).resolve().parents[2] / ".secrets" / "ootb-admin.env"
_secrets = dotenv_values(_SECRETS_PATH) if _SECRETS_PATH.exists() else {}


def _secret(key: str) -> str:
    """Load a value from .secrets/ without polluting os.environ."""
    return _secrets.get(key, "")


class Settings:
    """Application settings loaded from environment variables."""

    # Elastic Configuration
    KIBANA_URL: str = _config("KIBANA_URL", default="")
    ELASTICSEARCH_URL: str = _config("ELASTICSEARCH_URL", default="")
    ELASTIC_CLOUD_ID: str = _config("ELASTIC_CLOUD_ID", default="")
    ELASTIC_API_KEY: str = _config("ELASTIC_API_KEY", default="")
    AGENT_ID: str = _config("AGENT_ID", default="")
    CONNECTOR_ID: str = _config("CONNECTOR_ID", default="")

    # Workflows API Key (needs workflowsManagement Kibana privilege).
    # Checked in order: backend/.env -> .secrets/ootb-admin.env (ADMIN_API_KEY)
    WORKFLOWS_API_KEY: str = (
        _config("WORKFLOWS_API_KEY", default="") or _secret("ADMIN_API_KEY")
    )

    # Agent Builder management API Key (needs agentBuilder:manageTools Kibana privilege).
    # For create/update/delete of agents and tools. Falls back to ADMIN_API_KEY from .secrets.
    AGENT_MANAGEMENT_API_KEY: str = (
        _config("AGENT_MANAGEMENT_API_KEY", default="") or _secret("ADMIN_API_KEY")
    )

    # Monitoring Cluster Configuration
    MONITORING_ELASTICSEARCH_URL: str = _config(
        "MONITORING_ELASTICSEARCH_URL", default=""
    )
    MONITORING_ELASTIC_API_KEY: str = _config("MONITORING_ELASTIC_API_KEY", default="")

    # Search Configuration
    SEARCH_INDEX: str = _config("SEARCH_INDEX", default="ootb-products")

    # Visual Search (Jina CLIP v2 for text-to-image / image-to-image kNN)
    VISUAL_SEARCH_INDEX: str = _config("VISUAL_SEARCH_INDEX", default="products")
    JINA_API_KEY: str = _config("JINA_API_KEY", default="")

    # LLM Proxy Configuration (for A2A Multi-Agent)
    LLM_PROXY_URL: str = _config("LLM_PROXY_URL", default="")
    LLM_PROXY_API_KEY: str = _config("LLM_PROXY_API_KEY", default="")
    LLM_PROXY_MODEL: str = _config("LLM_PROXY_MODEL", default="gpt-4")

    # OpenTelemetry Configuration
    OTEL_ENABLED: str = _config("OTEL_ENABLED", default="")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = _config(
        "OTEL_EXPORTER_OTLP_ENDPOINT", default=""
    )
    OTEL_EXPORTER_OTLP_HEADERS: str = _config("OTEL_EXPORTER_OTLP_HEADERS", default="")
    OTEL_RESOURCE_ATTRIBUTES: str = _config("OTEL_RESOURCE_ATTRIBUTES", default="")
    OTEL_SERVICE_NAME: str = _config("OTEL_SERVICE_NAME", default="search-api")
    OTEL_SERVICE_VERSION: str = _config("OTEL_SERVICE_VERSION", default="1.0.0")
    OTEL_DEPLOYMENT_ENVIRONMENT: str = _config(
        "OTEL_DEPLOYMENT_ENVIRONMENT", default="development"
    )
    ELASTIC_APM_ENDPOINT: str = _config("ELASTIC_APM_ENDPOINT", default="")
    ELASTIC_APM_SECRET_TOKEN: str = _config("ELASTIC_APM_SECRET_TOKEN", default="")

    # Server Configuration
    HOST: str = _config("HOST", default="0.0.0.0")
    PORT: int = _config("PORT", default=8001, cast=int)
    FRONTEND_PORT: int = _config("FRONTEND_PORT", default=3000, cast=int)
    # Agno Configuration
    AGNO_LEARNING_ENABLED: bool = _config(
        "AGNO_LEARNING_ENABLED", default="true", cast=lambda v: v.lower() == "true"
    )
    AGNO_MEMORY_DB_PATH: str = _config("AGNO_MEMORY_DB_PATH", default="data/agno_memory.db")

    @property
    def BACKEND_URL(self) -> str:
        """Backend URL, dynamically constructed from HOST and PORT when not explicitly set."""
        explicit = _config("BACKEND_URL", default="")
        if explicit:
            return explicit
        host = "localhost" if self.HOST == "0.0.0.0" else self.HOST
        return f"http://{host}:{self.PORT}"

    # CORS Origins - dynamically include frontend port
    @property
    def CORS_ORIGINS(self) -> list[str]:
        custom = _config("CORS_ORIGINS", default="")
        origins = [
            f"http://localhost:{self.FRONTEND_PORT}",
            f"http://127.0.0.1:{self.FRONTEND_PORT}",
        ]
        if custom:
            origins.extend(
                [origin.strip() for origin in custom.split(",") if origin.strip()]
            )
        return origins

    @property
    def has_monitoring_cluster(self) -> bool:
        return bool(
            self.MONITORING_ELASTICSEARCH_URL and self.MONITORING_ELASTIC_API_KEY
        )

    def validate(self) -> None:
        """Validate required configuration is present.

        `AGENT_ID` is optional: it's only needed by the Agent Builder bridge
        routes (not by the Atlas memory demo), so a clean clone without one
        boots without a warning.
        """
        required = ["KIBANA_URL", "ELASTIC_API_KEY"]
        missing = [key for key in required if not getattr(self, key)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")


# Global settings instance
settings = Settings()
