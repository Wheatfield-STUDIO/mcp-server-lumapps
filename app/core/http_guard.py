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

"""Request limits and response headers for the public MCP endpoint."""

import hashlib
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

_HITS: Dict[str, Deque[float]] = defaultdict(deque)
_SKIP_PREFIXES = ("/health", "/ready", "/.well-known/")


def reset_rate_limits() -> None:
    _HITS.clear()


def _client_key(scope: Scope) -> str:
    headers = {k.lower(): v for k, v in scope.get("headers") or []}
    auth = headers.get(b"authorization") or headers.get(b"x-api-key")
    if auth:
        return hashlib.sha256(auth).hexdigest()[:24]
    client = scope.get("client")
    host = client[0] if client else "unknown"
    return f"ip:{host}"


def _json_response(status: int, detail: str, extra_headers: list[tuple[bytes, bytes]] | None = None):
    body = ('{"detail":"%s"}' % detail).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    return body, headers


class RateLimitMiddleware:
    """Per-credential sliding window. Health and discovery are not counted."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        limit = int(settings.MCP_RATE_LIMIT_PER_MINUTE or 0)
        if limit <= 0 or path.startswith(_SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return
        now = time.monotonic()
        key = _client_key(scope)
        bucket = _HITS[key]
        cutoff = now - 60.0
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            body, headers = _json_response(429, "Too many requests", [(b"retry-after", b"60")])
            await send({"type": "http.response.start", "status": 429, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return
        bucket.append(now)
        await self.app(scope, receive, send)


class BodySizeLimitMiddleware:
    """Reject bodies larger than MCP_MAX_BODY_BYTES before the app reads them."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        max_bytes = int(settings.MCP_MAX_BODY_BYTES or 0)
        if max_bytes <= 0:
            await self.app(scope, receive, send)
            return
        messages: list[Message] = []
        total = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.request":
                total += len(message.get("body") or b"")
                if total > max_bytes:
                    body, headers = _json_response(413, "Request body is too large")
                    await send({"type": "http.response.start", "status": 413, "headers": headers})
                    await send({"type": "http.response.body", "body": body})
                    return
                if not message.get("more_body", False):
                    break
            else:
                break
        index = 0

        async def replay() -> Message:
            nonlocal index
            if index < len(messages):
                message = messages[index]
                index += 1
                return message
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                names = {k.lower() for k, _ in headers}
                extra = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                ]
                if b"cache-control" not in names:
                    extra.append((b"cache-control", b"no-store"))
                headers.extend(extra)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
