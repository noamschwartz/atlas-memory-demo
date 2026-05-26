#!/usr/bin/env python3
"""Development server runner.

Usage:
    python run.py

Or with uvicorn directly:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import uvicorn

from app.config import settings


def main() -> None:
    print(f"Starting Elastic Agent API on http://{settings.HOST}:{settings.PORT}")
    print(f"API Docs available at http://localhost:{settings.PORT}/docs")

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )


if __name__ == "__main__":
    main()
