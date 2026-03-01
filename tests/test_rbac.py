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

"""RBAC: API-key deny for non-read tools, OIDC role mapping, site resolution, cache."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient

from app.core.rbac import (
    RBACError,
    get_tool_sensitivity,
    resolve_target_site_id,
    authorize_tool_call,
    _user_has_global_admin,
    _user_has_site_role,
    _get_content_site_cache,
)
from app.core.user_context import UserContext


def test_get_tool_sensitivity() -> None:
    assert get_tool_sensitivity("search_content") == "read"
    assert get_tool_sensitivity("search_lumapps") == "read"
    assert get_tool_sensitivity("inspect_lumapps_element") == "content"
    assert get_tool_sensitivity("update_global_css") == "structural"
    assert get_tool_sensitivity("update_site_global_settings") == "structural"
    assert get_tool_sensitivity("update_widget_style") == "content"
    assert get_tool_sensitivity("unknown_tool") == "read"


def test_structural_tool_with_api_key_denied(client: TestClient) -> None:
    """Structural tools with API key only (no OIDC) are denied when RBAC_DENY_API_KEY_FOR_NON_READ is true."""
    r = client.post(
        "/mcp",
        headers={"X-API-Key": "test-mcp-api-key"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "update_global_css",
                "arguments": {
                    "site_id": "site-123",
                    "new_css": "/* test */ body {}",
                    "user_email": "dev@example.com",
                },
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "error" in data
    assert data["error"]["message"]
    assert "OIDC" in data["error"]["message"] or "authenticated user" in data["error"]["message"].lower()


def test_read_tool_with_api_key_allowed(client: TestClient) -> None:
    """Read-only MCP methods (e.g. tools/list) succeed with API key."""
    r = client.post(
        "/mcp",
        headers={"X-API-Key": "test-mcp-api-key"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "result" in data
    assert "tools" in data["result"]


def test_authorize_structural_denied_without_user_context() -> None:
    """When get_user_context() is None and RBAC denies API key, authorize_tool_call raises RBACError."""
    mock_settings = MagicMock()
    mock_settings.RBAC_ENABLED = True
    mock_settings.RBAC_DENY_API_KEY_FOR_NON_READ = True
    with patch("app.core.rbac.get_user_context", return_value=None):
        with patch("app.core.rbac.settings", mock_settings):
            with pytest.raises(RBACError) as exc_info:
                asyncio.run(authorize_tool_call("update_global_css", {"site_id": "s1", "user_email": "u@x.com"}))
            assert "OIDC" in exc_info.value.message or "authenticated user" in exc_info.value.message.lower()


def test_authorize_structural_denied_contributor_only() -> None:
    """User with contributor claim for site but not admin is denied for structural tool."""
    ctx = UserContext(
        sub="sub1",
        email="u@example.com",
        upn="u@example.com",
        issuer="https://issuer",
        audience="aud",
        scopes=[],
        raw_claims={"groups": ["lumapps:site:site-abc:contributor"]},
    )
    mock_settings = MagicMock()
    mock_settings.RBAC_ENABLED = True
    mock_settings.RBAC_ADMIN_PATTERNS = "lumapps:site:{site_id}:admin"
    mock_settings.RBAC_GLOBAL_ADMIN_PATTERNS = "lumapps:site:*:admin,lumapps:global:admin"
    mock_settings.RBAC_ROLE_CLAIM = "groups"
    with patch("app.core.rbac.get_user_context", return_value=ctx):
        with patch("app.core.rbac.settings", mock_settings):
            with pytest.raises(RBACError) as exc_info:
                asyncio.run(authorize_tool_call("update_global_css", {"site_id": "site-abc", "user_email": "u@example.com"}))
            assert "Site Administrator" in exc_info.value.message or "design" in exc_info.value.message.lower()


def test_authorize_content_allowed_contributor() -> None:
    """User with contributor (no admin) claim is allowed for content tools (update_widget_style, inspect_lumapps_element)."""
    ctx = UserContext(
        sub="sub1",
        email="contrib@example.com",
        upn="contrib@example.com",
        issuer="https://issuer",
        audience="aud",
        scopes=[],
        raw_claims={"groups": ["lumapps:site:site-abc:contributor"]},
    )
    mock_settings = MagicMock()
    mock_settings.RBAC_ENABLED = True
    mock_settings.RBAC_ADMIN_PATTERNS = "lumapps:site:{site_id}:admin"
    mock_settings.RBAC_CONTRIBUTOR_PATTERNS = "lumapps:site:{site_id}:contributor,lumapps:site:{site_id}:admin"
    mock_settings.RBAC_GLOBAL_ADMIN_PATTERNS = "lumapps:site:*:admin"
    mock_settings.RBAC_ROLE_CLAIM = "groups"
    with patch("app.core.rbac.get_user_context", return_value=ctx):
        with patch("app.core.rbac.settings", mock_settings):
            asyncio.run(authorize_tool_call(
                "update_widget_style",
                {"site_id": "site-abc", "user_email": "contrib@example.com"},
            ))
            asyncio.run(authorize_tool_call(
                "inspect_lumapps_element",
                {"site_id": "site-abc", "user_email": "contrib@example.com"},
            ))


def test_authorize_structural_allowed_site_admin() -> None:
    """User with site-scoped admin claim is allowed for structural tool."""
    ctx = UserContext(
        sub="sub1",
        email="u@example.com",
        upn="u@example.com",
        issuer="https://issuer",
        audience="aud",
        scopes=[],
        raw_claims={"groups": ["lumapps:site:site-xyz:admin"]},
    )
    mock_settings = MagicMock()
    mock_settings.RBAC_ENABLED = True
    mock_settings.RBAC_ADMIN_PATTERNS = "lumapps:site:{site_id}:admin"
    mock_settings.RBAC_GLOBAL_ADMIN_PATTERNS = "lumapps:site:*:admin"
    mock_settings.RBAC_ROLE_CLAIM = "groups"
    with patch("app.core.rbac.get_user_context", return_value=ctx):
        with patch("app.core.rbac.settings", mock_settings):
            asyncio.run(authorize_tool_call("update_global_css", {"site_id": "site-xyz", "user_email": "u@example.com"}))


def test_authorize_structural_allowed_global_admin() -> None:
    """User with global admin claim (lumapps:site:*:admin) is allowed for any site."""
    ctx = UserContext(
        sub="sub1",
        email="admin@example.com",
        upn="admin@example.com",
        issuer="https://issuer",
        audience="aud",
        scopes=[],
        raw_claims={"groups": ["lumapps:site:*:admin"]},
    )
    mock_settings = MagicMock()
    mock_settings.RBAC_ENABLED = True
    mock_settings.RBAC_ADMIN_PATTERNS = "lumapps:site:{site_id}:admin"
    mock_settings.RBAC_GLOBAL_ADMIN_PATTERNS = "lumapps:site:*:admin,lumapps:global:admin"
    mock_settings.RBAC_ROLE_CLAIM = "groups"
    with patch("app.core.rbac.get_user_context", return_value=ctx):
        with patch("app.core.rbac.settings", mock_settings):
            asyncio.run(authorize_tool_call("update_global_css", {"site_id": "any-site", "user_email": "admin@example.com"}))


def test_user_has_global_admin() -> None:
    """Global admin is true when groups contain literal global admin pattern."""
    assert _user_has_global_admin({"groups": ["lumapps:site:*:admin"]}) is True
    assert _user_has_global_admin({"groups": ["lumapps:global:admin"]}) is True
    assert _user_has_global_admin({"groups": ["lumapps:site:site1:admin"]}) is False
    assert _user_has_global_admin({"groups": []}) is False


def test_user_has_site_role() -> None:
    """Site-scoped admin/contributor match after {site_id} substitution."""
    with patch("app.core.rbac.settings") as s:
        s.RBAC_ROLE_CLAIM = "groups"
        s.RBAC_ADMIN_PATTERNS = "lumapps:site:{site_id}:admin"
        s.RBAC_CONTRIBUTOR_PATTERNS = "lumapps:site:{site_id}:contributor,lumapps:site:{site_id}:admin"
        assert _user_has_site_role({"groups": ["lumapps:site:site-1:admin"]}, "site-1", "admin") is True
        assert _user_has_site_role({"groups": ["lumapps:site:site-1:contributor"]}, "site-1", "contributor") is True
        assert _user_has_site_role({"groups": ["lumapps:site:site-1:admin"]}, "site-1", "contributor") is True
        assert _user_has_site_role({"groups": ["lumapps:site:site-1:contributor"]}, "site-1", "admin") is False


def test_resolve_target_site_id_from_args() -> None:
    """resolve_target_site_id returns site_id from arguments when present."""
    out = asyncio.run(resolve_target_site_id("update_global_css", {"site_id": "my-site-uid"}, token=None))
    assert out == "my-site-uid"
    out = asyncio.run(resolve_target_site_id("update_site_global_settings", {"siteId": "other-site"}, token=None))
    assert out == "other-site"


def test_resolve_target_site_id_from_content_id_via_api() -> None:
    """update_widget_style: content_id -> site_id uses get_content when token provided."""
    from app.services.lumapps_client import lumapps_client
    with patch.object(lumapps_client, "get_content", new_callable=AsyncMock, return_value={"instance": "resolved-site-456"}):
        out = asyncio.run(resolve_target_site_id(
            "update_widget_style",
            {"content_id": "content-xyz"},
            token="fake-token",
        ))
    assert out == "resolved-site-456"


def test_content_site_cache_hit() -> None:
    """Cache returns site_id on second resolution for same content_id."""
    async def _run() -> None:
        cache = _get_content_site_cache()
        await cache.set("c1", "site-1")
        assert await cache.get("c1") == "site-1"
        assert await cache.get("c2") is None
        await cache.set("c2", "site-2")
        assert await cache.get("c2") == "site-2"
    asyncio.run(_run())
