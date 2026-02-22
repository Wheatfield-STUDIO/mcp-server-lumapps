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

"""
MCP Streamable HTTP transport (spec 2025-06-18).
Single endpoint: GET and POST /mcp.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sse_starlette import EventSourceResponse
from app.core.security import validate_api_key_header_or_query
from app.jsonrpc.models import JSONRPCRequest, JSONRPCResponse
from app.jsonrpc.dispatcher import dispatcher
from app.jsonrpc.errors import JSONRPCCodes
import asyncio
import logging
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


def _is_notification(body: dict) -> bool:
    """JSON-RPC notification has method and no id (or id is null)."""
    return "method" in body and body.get("id") is None


def _is_response(body: dict) -> bool:
    """JSON-RPC response has result or error and no method."""
    return "method" not in body and ("result" in body or "error" in body)


def _is_request(body: dict) -> bool:
    return "method" in body and body.get("id") is not None


@router.get("/mcp")
async def mcp_get(
    request: Request,
    api_key: str = Depends(validate_api_key_header_or_query),
):
    """
    Streamable HTTP: GET opens an SSE stream for server-to-client messages.
    Server may send JSON-RPC requests/notifications on this stream.
    """
    logger.info("MCP GET /mcp: SSE stream opened")

    async def event_stream():
        yield {"event": "open", "data": "{}"}
        while True:
            if await request.is_disconnected():
                break
            yield {"comment": "ping"}
            await asyncio.sleep(15)

    return EventSourceResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/mcp")
async def mcp_post(
    request: Request,
    api_key: str = Depends(validate_api_key_header_or_query),
):
    """
    Streamable HTTP: POST sends one JSON-RPC message (request, notification, or response).
    - Request -> 200 + application/json (single response) or 202 if no body needed.
    - Notification or client response -> 202 Accepted, no body.
    """
    protocol_version = request.headers.get("mcp-protocol-version") or request.headers.get("MCP-Protocol-Version")
    if protocol_version and protocol_version not in SUPPORTED_VERSIONS:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": JSONRPCCodes.INVALID_PARAMS,
                    "message": f"Unsupported MCP-Protocol-Version: {protocol_version}",
                    "data": {"supported": list(SUPPORTED_VERSIONS)},
                },
            },
            headers={"Content-Type": "application/json"},
        )

    try:
        body = await request.json()
        method = body.get("method") if isinstance(body, dict) else None
        req_id = body.get("id") if isinstance(body, dict) else None
        logger.info("MCP POST /mcp: method=%s id=%s", method, req_id)
    except Exception as e:
        logger.warning(f"Invalid JSON body: {e}")
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": JSONRPCCodes.PARSE_ERROR,
                    "message": "Invalid JSON",
                },
            },
            headers={"Content-Type": "application/json"},
        )

    if not isinstance(body, dict):
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": JSONRPCCodes.INVALID_REQUEST,
                    "message": "Body must be a single JSON object",
                },
            },
            headers={"Content-Type": "application/json"},
        )

    if _is_notification(body):
        logger.debug(f"Notification: {body.get('method')}")
        return Response(status_code=202)

    if _is_response(body):
        logger.debug("Client response received")
        return Response(status_code=202)

    if not _is_request(body):
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {
                    "code": JSONRPCCodes.INVALID_REQUEST,
                    "message": "Invalid JSON-RPC: expected request, notification, or response",
                },
            },
            headers={"Content-Type": "application/json"},
        )

    try:
        rpc_request = JSONRPCRequest(**body)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {
                    "code": JSONRPCCodes.INVALID_REQUEST,
                    "message": str(e),
                },
            },
            headers={"Content-Type": "application/json"},
        )

    response = await dispatcher.dispatch(rpc_request)
    payload = {"jsonrpc": "2.0", "id": response.id}
    if response.error is not None:
        payload["error"] = response.error.model_dump()
    else:
        payload["result"] = response.result

    headers = {"Content-Type": "application/json"}
    if rpc_request.method == "initialize" and response.error is None:
        session_id = str(uuid.uuid4())
        headers["Mcp-Session-Id"] = session_id

    return JSONResponse(content=payload, status_code=200, headers=headers)
