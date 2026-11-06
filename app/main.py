# Copyright 2026 Joffrey TREBOT (Wheatfield Studio)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import tools  # noqa: F401
from app.core.config import settings
from app.core.http_guard import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.logging import setup_logging
from app.routers import oauth_metadata, streamable_http

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.LUMAPPS_ACCESS_TOKEN:
        logger.warning(
            "LUMAPPS_ACCESS_TOKEN is set. Every LumApps call uses that one token, "
            "including writes. Unset it so each call uses the signed-in user."
        )
    yield


_docs = settings.EXPOSE_API_DOCS
app = FastAPI(
    title="LumApps MCP Server",
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
    lifespan=lifespan,
)

_origins = [
    "http://localhost:6274",
    "http://127.0.0.1:6274",
]
if extra := os.getenv("CORS_ORIGINS", "").strip():
    _origins.extend(o.strip() for o in extra.split(",") if o.strip())

# Last add_middleware is the outermost wrapper.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-API-Key",
        "Mcp-Session-Id",
        "Mcp-Protocol-Version",
        "Last-Event-ID",
    ],
)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(oauth_metadata.router)
app.include_router(streamable_http.router)


@app.get("/health")
async def health_check():
    """Liveness probe: process is running."""
    return {"status": "ok"}


@app.get("/ready")
async def readiness_check():
    """Readiness probe: app is configured and ready to accept traffic."""
    return {"status": "ready"}


@app.get("/")
async def root_get():
    """Informational: no auth required. MCP is Streamable HTTP at /mcp."""
    return {
        "message": "LumApps MCP Server is running",
        "endpoints": {"mcp": "/mcp"},
    }
