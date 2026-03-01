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

from fastapi import APIRouter, Depends, Request
from sse_starlette import EventSourceResponse
from app.core.security import AuthResult, validate_api_key_header_or_query
from app.core.config import settings
import asyncio
import logging
import json
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)

sse_queues = {}

@router.get("/sse")
async def sse_endpoint(request: Request, auth_result: AuthResult = Depends(validate_api_key_header_or_query)):
    session_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    sse_queues[session_id] = queue

    if settings.MCP_PUBLIC_URL:
        base_url = settings.MCP_PUBLIC_URL.rstrip("/")
    else:
        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_host:
            scheme = (forwarded_proto or "https").split(",")[0].strip().lower()
            base_url = f"{scheme}://{forwarded_host.split(',')[0].strip()}".rstrip("/")
        else:
            base_url = str(request.base_url).rstrip("/")
    message_endpoint_url = f"{base_url}/messages?mcp-session-id={session_id}"
    logger.info(f"New SSE connection, session_id={session_id}, endpoint={message_endpoint_url}")

    async def event_generator():
        try:
            yield {
                "event": "endpoint",
                "data": message_endpoint_url,
            }
            while True:
                if await request.is_disconnected():
                    logger.info(f"SSE session {session_id} disconnected")
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield {
                        "event": "message",
                        "data": message if isinstance(message, str) else json.dumps(message),
                    }
                except asyncio.TimeoutError:
                    continue
        finally:
            sse_queues.pop(session_id, None)

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
