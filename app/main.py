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

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routers import sse, messages, streamable_http
from app.core.logging import setup_logging
from app.core.security import AuthResult, validate_api_key_header_or_query
from app import tools  # noqa: F401
import logging
import os

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="LumApps MCP Server")

_origins = [
    "http://localhost:6274",
    "http://127.0.0.1:6274",
]
if extra := os.getenv("CORS_ORIGINS", "").strip():
    _origins.extend(o.strip() for o in extra.split(",") if o.strip())
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(streamable_http.router)
app.include_router(sse.router)
app.include_router(messages.router)

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
    """Informational: no auth required. Use /mcp or /messages for MCP JSON-RPC."""
    return {
        "message": "LumApps MCP Server is running",
        "docs": "/docs",
        "endpoints": {
            "mcp": "/mcp",
            "sse": "/sse",
            "messages": "/messages",
        },
    }


@app.post("/")
async def root_post(
    request: Request,
    auth_result: AuthResult = Depends(validate_api_key_header_or_query),
):
    """
    Authenticated JSON-RPC at root. Prefer /mcp (streamable HTTP) or /messages for MCP.
    Same auth as /mcp: Bearer (OIDC) or API key when fallback enabled.
    """
    try:
        body = await request.json()
        if (isinstance(body, dict) and body.get("jsonrpc") == "2.0") or (
            isinstance(body, list)
            and len(body) > 0
            and isinstance(body[0], dict)
            and body[0].get("jsonrpc") == "2.0"
        ):
            from app.jsonrpc.models import JSONRPCRequest
            from app.jsonrpc.dispatcher import dispatcher

            method = body.get("method") if isinstance(body, dict) else "batch"
            logger.info("Handling JSON-RPC request at root URL: %s", method)
            if isinstance(body, list):
                results = []
                for item in body:
                    rpc_req = JSONRPCRequest(**item)
                    results.append(await dispatcher.dispatch(rpc_req))
                return results
            rpc_req = JSONRPCRequest(**body)
            return await dispatcher.dispatch(rpc_req)
    except Exception as e:
        logger.debug("Root POST: not JSON-RPC or error: %s", e)
    return {
        "message": "LumApps MCP Server is running",
        "docs": "/docs",
        "endpoints": {"mcp": "/mcp", "sse": "/sse", "messages": "/messages"},
    }
