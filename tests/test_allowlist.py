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

"""Fail-closed MCP_ALLOWED_USER_EMAILS and no query-string API keys."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.allowlist import (
    AllowlistError,
    is_user_email_allowed,
    parse_allowed_user_emails,
    require_allowed_user_email,
)
from app.core.user_context import UserContext


def test_parse_allowed_user_emails_empty_fail_closed() -> None:
    assert parse_allowed_user_emails(None) == set()
    assert parse_allowed_user_emails("") == set()
    assert parse_allowed_user_emails("  ,  ") == set()
    assert is_user_email_allowed("anyone@example.com", set()) is False
    assert is_user_email_allowed(None, {"dev@example.com"}) is False


def _require_with(raw: str, email: str = "dev@example.com") -> str:
    with patch("app.core.allowlist.settings") as s:
        s.MCP_ALLOWED_USER_EMAILS = raw
        return require_allowed_user_email(email)


def test_require_empty_allowlist_denies() -> None:
    with pytest.raises(AllowlistError, match="MCP_ALLOWED_USER_EMAILS is empty"):
        _require_with("")
    with pytest.raises(AllowlistError, match="MCP_ALLOWED_USER_EMAILS is empty"):
        _require_with(None)  # type: ignore[arg-type]


def test_allowlist_case_insensitive_and_unknown_denied() -> None:
    assert is_user_email_allowed("Joffrey@Example.COM", {"joffrey@example.com"}) is True
    assert is_user_email_allowed("other@example.com", {"joffrey@example.com"}) is False
    assert is_user_email_allowed("", {"joffrey@example.com"}) is False
    assert is_user_email_allowed(None, {"joffrey@example.com"}) is False
    with pytest.raises(AllowlistError, match="not permitted"):
        _require_with("joffrey@example.com", "intruder@example.com")
    assert _require_with("joffrey@example.com, other@x.com", "JOFFREY@EXAMPLE.COM") == "JOFFREY@EXAMPLE.COM"


def _tool_call(client: TestClient, email: str, extra_headers=None, url: str = "/mcp"):
    headers = {"X-API-Key": "test-mcp-api-key"}
    if extra_headers:
        headers.update(extra_headers)
    return client.post(
        url,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_site",
                "arguments": {"user_email": email},
            },
        },
    )


def test_http_empty_allowlist_denies_read_tool(client: TestClient) -> None:
    with patch("app.core.allowlist.settings") as s:
        s.MCP_ALLOWED_USER_EMAILS = ""
        r = _tool_call(client, "dev@example.com")
    assert r.status_code == 200
    err = r.json().get("error") or {}
    assert "MCP_ALLOWED_USER_EMAILS" in (err.get("message") or "")


def test_http_unknown_email_denied_even_for_reads(client: TestClient) -> None:
    r = _tool_call(client, "not-allowed@example.com")
    assert r.status_code == 200
    err = r.json().get("error") or {}
    assert "not permitted" in (err.get("message") or "").lower()


def test_http_missing_user_email_denied(client: TestClient) -> None:
    r = client.post(
        "/mcp",
        headers={"X-API-Key": "test-mcp-api-key"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "search_site", "arguments": {}},
        },
    )
    assert r.status_code == 200
    err = r.json().get("error") or {}
    assert "not permitted" in (err.get("message") or "").lower()


def test_http_unknown_email_denied_for_write_tool(client: TestClient) -> None:
    r = client.post(
        "/mcp",
        headers={"X-API-Key": "test-mcp-api-key"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "update_widget_style",
                "arguments": {
                    "user_email": "intruder@example.com",
                    "content_id": "c1",
                    "widget_id": "w1",
                    "style_updates": "{}",
                },
            },
        },
    )
    assert r.status_code == 200
    err = r.json().get("error") or {}
    assert "not permitted" in (err.get("message") or "").lower()


def test_http_allowed_email_passes_allowlist(client: TestClient) -> None:
    """Allowlist accepts the mailbox; call may still fail later (LumApps token)."""
    r = _tool_call(client, "DEV@example.com")
    assert r.status_code == 200
    data = r.json()
    msg = (data.get("error") or {}).get("message") or ""
    assert "not permitted" not in msg.lower()
    assert "MCP_ALLOWED_USER_EMAILS" not in msg


def test_oidc_email_must_be_on_allowlist(client: TestClient) -> None:
    ctx = UserContext(
        sub="sub1",
        email="oidc-user@example.com",
        upn="oidc-user@example.com",
        issuer="https://issuer",
        audience="aud",
        scopes=[],
        raw_claims={},
    )
    with patch("app.tools.get_user_context", return_value=ctx):
        r = _tool_call(client, "oidc-user@example.com")
    assert r.status_code == 200
    err = r.json().get("error") or {}
    assert "not permitted" in (err.get("message") or "").lower()


def test_oidc_email_on_allowlist_passes_gate(client: TestClient) -> None:
    ctx = UserContext(
        sub="sub1",
        email="dev@example.com",
        upn="dev@example.com",
        issuer="https://issuer",
        audience="aud",
        scopes=[],
        raw_claims={},
    )
    with patch("app.tools.get_user_context", return_value=ctx):
        r = _tool_call(client, "dev@example.com")
    assert r.status_code == 200
    msg = (r.json().get("error") or {}).get("message") or ""
    assert "not permitted" not in msg.lower()
    assert "MCP_ALLOWED_USER_EMAILS" not in msg


def test_query_string_apikey_rejected(client: TestClient) -> None:
    r = client.post(
        "/mcp?apiKey=test-mcp-api-key",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert r.status_code == 401
    assert "query string" in (r.json().get("detail") or "").lower()


def test_query_string_apikey_case_insensitive_rejected(client: TestClient) -> None:
    r = client.post(
        "/mcp?APIKEY=test-mcp-api-key",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert r.status_code == 401
    assert "query string" in (r.json().get("detail") or "").lower()


def test_query_string_token_rejected(client: TestClient) -> None:
    r = client.post(
        "/mcp?token=test-mcp-api-key",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert r.status_code == 401
    assert "query string" in (r.json().get("detail") or "").lower()


def test_query_string_rejected_even_with_valid_header(client: TestClient) -> None:
    r = client.post(
        "/mcp?apiKey=test-mcp-api-key",
        headers={"X-API-Key": "test-mcp-api-key"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert r.status_code == 401
    assert "query string" in (r.json().get("detail") or "").lower()


def test_tools_list_still_works_with_header_key(client: TestClient) -> None:
    r = client.post(
        "/mcp",
        headers={"X-API-Key": "test-mcp-api-key"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert r.status_code == 200
    assert "tools" in r.json()["result"]
