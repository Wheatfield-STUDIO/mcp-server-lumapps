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

"""Auth and OIDC/API-key regression tests."""

import pytest
from fastapi.testclient import TestClient


def test_get_root_unauthenticated(client: TestClient) -> None:
    """GET / is informational and does not require auth."""
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    assert "endpoints" in data
    assert data["endpoints"]["mcp"] == "/mcp"


def test_health_ready_unauthenticated(client: TestClient) -> None:
    """Health and readiness probes do not require auth."""
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_post_mcp_without_auth_returns_401(client: TestClient) -> None:
    """POST /mcp without any auth returns 401."""
    r = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
    )
    assert r.status_code == 401


def test_post_mcp_with_api_key_succeeds(client: TestClient) -> None:
    """POST /mcp with valid API key (header) returns 200 and protocol response."""
    r = client.post(
        "/mcp",
        headers={"X-API-Key": "test-mcp-api-key"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "result" in data
    assert data["result"].get("protocolVersion") == "2025-06-18"


def test_post_mcp_with_bearer_api_key_succeeds(client: TestClient) -> None:
    """POST /mcp with Authorization: Bearer <api_key> (fallback) succeeds."""
    r = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-mcp-api-key"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
    )
    assert r.status_code == 200
    assert "result" in r.json()


def test_post_root_without_auth_returns_401(client: TestClient) -> None:
    """POST / with JSON-RPC body but no auth returns 401."""
    r = client.post(
        "/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
    )
    assert r.status_code == 401


def test_post_root_with_api_key_succeeds(client: TestClient) -> None:
    """POST / with valid API key accepts JSON-RPC (same auth as /mcp)."""
    r = client.post(
        "/",
        headers={"X-API-Key": "test-mcp-api-key"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
    )
    assert r.status_code == 200
    assert r.json().get("result", {}).get("protocolVersion") == "2025-06-18"


def test_invalid_api_key_returns_401(client: TestClient) -> None:
    """Invalid or wrong API key returns 401."""
    r = client.post(
        "/mcp",
        headers={"X-API-Key": "wrong-key"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
    )
    assert r.status_code == 401
