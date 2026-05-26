"""FastAPI Backend for Atlas Memory Demo.

Proxy between the frontend and Elasticsearch / Elastic Inference Service.
Exposes the Atlas memory layer and an MCP server for external agent integration.

Architecture:
Frontend (Vite/React) <-> Backend (FastAPI) <-> Elastic Stack (ES + Kibana + EIS)
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .atlas.routes.chat import router as atlas_router
from .atlas.routes.mcp import router as atlas_mcp_router
from .atlas.routes.memory import router as memory_router
from .config import settings
from .otel import init_otel

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Atlas Memory Demo",
    description="Agent memory layer backed by Elasticsearch",
    version="1.0.0",
)

try:
    settings.validate()
except ValueError as e:
    logger.warning(f"Configuration warning: {e}")

init_otel(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(memory_router)
app.include_router(atlas_router)
app.include_router(atlas_mcp_router)


@app.get("/")
async def root():
    return {"name": "Atlas Memory Demo", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health():
    checks = {"status": "ok"}

    config_ok = bool(settings.ELASTICSEARCH_URL and settings.ELASTIC_API_KEY)
    checks["config"] = "ok" if config_ok else "missing"

    if config_ok:
        try:
            from elasticsearch import Elasticsearch

            es = Elasticsearch(
                settings.ELASTICSEARCH_URL,
                api_key=settings.ELASTIC_API_KEY,
                request_timeout=3,
            )
            es.info()
            checks["elasticsearch"] = "ok"
        except Exception:
            checks["elasticsearch"] = "unreachable"

    if all(v == "ok" for v in checks.values()):
        checks["status"] = "ok"
    else:
        checks["status"] = "degraded"

    return checks


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
