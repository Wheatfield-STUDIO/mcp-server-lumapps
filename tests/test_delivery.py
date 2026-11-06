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

"""Delivery hardening: closed transports, request limits, error sanitization."""

import httpx
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.http_guard import reset_rate_limits
from app.core.rbac import CONTENT_TOOLS, READ_TOOLS, STRUCTURAL_TOOLS, get_tool_sensitivity
from app.tools import (
    find_person,
    get_content_body,
    get_useful_links,
    inspect_lumapps_element,
    search_content,
    search_site,
    update_global_css,
    update_site_global_settings,
    update_widget_style,
)
from app.tools.api_error_utils import format_api_error


def test_legacy_transports_are_gone(client: TestClient) -> None:
    assert client.get("/sse").status_code == 404
    assert client.post("/messages").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_security_headers(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_body_size_limit(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "MCP_MAX_BODY_BYTES", 32)
    response = client.post(
        "/mcp",
        headers={"X-API-Key": "test-mcp-api-key"},
        content=b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"pad":"' + b"x" * 80 + b'"}}',
    )
    assert response.status_code == 413


def test_rate_limit(client: TestClient, monkeypatch) -> None:
    reset_rate_limits()
    monkeypatch.setattr(settings, "MCP_RATE_LIMIT_PER_MINUTE", 2)
    headers = {"X-API-Key": "test-mcp-api-key"}
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    try:
        assert client.post("/mcp", headers=headers, json=body).status_code == 200
        assert client.post("/mcp", headers=headers, json=body).status_code == 200
        blocked = client.post("/mcp", headers=headers, json=body)
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"
    finally:
        reset_rate_limits()


def test_api_key_cannot_call_tools(client: TestClient) -> None:
    response = client.post(
        "/mcp",
        headers={"X-API-Key": "test-mcp-api-key"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_content",
                "arguments": {"query": "handbook", "user_email": "someone@example.com"},
            },
        },
    )
    assert response.status_code == 200
    message = response.json()["error"]["message"]
    assert "authenticated user" in message
    assert "someone@example.com" not in message


def test_format_api_error_omits_body() -> None:
    request = httpx.Request("GET", "https://lumapps.example/secret")
    response = httpx.Response(403, request=request, text='{"token":"super-secret"}')
    error = httpx.HTTPStatusError("boom", request=request, response=response)
    text = format_api_error(error)
    assert text == "The LumApps request failed (HTTP 403)."
    assert "super-secret" not in text
    assert format_api_error(RuntimeError("raw traceback detail")) == "The LumApps request failed."


def test_tool_sensitivity_matches_rbac() -> None:
    modules = {
        search_content: "read",
        get_content_body: "read",
        find_person: "read",
        get_useful_links: "read",
        search_site: "read",
        inspect_lumapps_element: "content",
        update_widget_style: "content",
        update_global_css: "structural",
        update_site_global_settings: "structural",
    }
    for module, sensitivity in modules.items():
        assert module.TOOL_SENSITIVITY == sensitivity
        assert get_tool_sensitivity(module.TOOL_NAME) == sensitivity
    assert get_tool_sensitivity("search_lumapps") == "read"
    assert get_tool_sensitivity("unknown_tool") == "read"
    classified = READ_TOOLS | CONTENT_TOOLS | STRUCTURAL_TOOLS
    assert classified == {module.TOOL_NAME for module in modules} | {"search_lumapps"}
