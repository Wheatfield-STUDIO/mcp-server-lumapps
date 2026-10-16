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

"""Copilot Studio OAuth discovery and Entra bearer-token tests."""

import asyncio
import time
from typing import Any, Dict

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.oidc import validate_oidc_token
from app.tools import TOOLS

TENANT = "11111111-2222-3333-4444-555555555555"
API_APP = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
API_AUDIENCE = f"api://{API_APP}"
SCOPE = f"{API_AUDIENCE}/access_as_user"
ISSUER_V2 = f"https://login.microsoftonline.com/{TENANT}/v2.0"
PUBLIC = "https://mcp.example.com"

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {},
}


def _enable_entra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc_preferred")
    monkeypatch.setattr(settings, "ENTRA_TENANT_ID", TENANT)
    monkeypatch.setattr(settings, "OIDC_ISSUER_URL", ISSUER_V2)
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", API_AUDIENCE)
    monkeypatch.setattr(settings, "OIDC_CLIENT_ID", None)
    monkeypatch.setattr(settings, "OIDC_SCOPES", SCOPE)
    monkeypatch.setattr(settings, "OIDC_DISCOVERY_URL", None)
    monkeypatch.setattr(settings, "MCP_PUBLIC_URL", PUBLIC)
    monkeypatch.setattr(settings, "AUTH_ALLOW_API_KEY_FALLBACK", True)


def _rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _sign(private_key, **claims: Any) -> str:
    now = int(time.time())
    body = {"iat": now, "nbf": now, "exp": now + 600}
    body.update(claims)
    return jwt.encode(body, private_key, algorithm="RS256")


def _install_jwks(monkeypatch: pytest.MonkeyPatch, private_key) -> None:
    public_key = private_key.public_key()

    class _SigningKey:
        def __init__(self, key):
            self.key = key

    class _Jwks:
        def get_signing_key_from_jwt(self, token: str):
            return _SigningKey(public_key)

    async def _discovery():
        return {"jwks_uri": f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys"}

    monkeypatch.setattr("app.core.oidc._fetch_discovery", _discovery)
    monkeypatch.setattr("app.core.oidc._get_jwks_client", lambda _uri: _Jwks())


def _stub_search(monkeypatch: pytest.MonkeyPatch, captured: Dict[str, Any]) -> None:
    schema, _handler = TOOLS["search_content"]

    async def _handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
        captured["arguments"] = dict(arguments)
        return {"content": [{"type": "text", "text": "ok"}]}

    monkeypatch.setitem(TOOLS, "search_content", (schema, _handle))


def test_discovery_absent_without_tenant(client: TestClient) -> None:
    assert client.get("/.well-known/oauth-protected-resource").status_code == 404
    assert client.get("/.well-known/oauth-protected-resource/mcp").status_code == 404
    assert client.get("/.well-known/oauth-authorization-server").status_code == 404


def test_discovery_json(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_entra(monkeypatch)
    protected = client.get("/.well-known/oauth-protected-resource")
    protected_mcp = client.get("/.well-known/oauth-protected-resource/mcp")
    server = client.get("/.well-known/oauth-authorization-server")
    assert protected.status_code == 200
    assert protected_mcp.status_code == 200
    assert server.status_code == 200
    assert protected.headers["cache-control"] == "public, max-age=300"

    resource = protected.json()
    assert resource == protected_mcp.json()
    assert resource["resource"] == f"{PUBLIC}/mcp"
    assert resource["authorization_servers"] == [ISSUER_V2]
    assert resource["bearer_methods_supported"] == ["header"]
    assert resource["scopes_supported"] == [SCOPE]
    assert "registration_endpoint" not in resource

    metadata = server.json()
    token_url = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"
    assert metadata["issuer"] == ISSUER_V2
    assert metadata["authorization_endpoint"] == (
        f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize"
    )
    assert metadata["token_endpoint"] == token_url
    assert metadata["jwks_uri"] == (
        f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys"
    )
    assert "refresh_token" in metadata["grant_types_supported"]
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert metadata["scopes_supported"] == [SCOPE]
    assert "registration_endpoint" not in metadata

    unauthorized = client.post("/mcp", json=_INITIALIZE)
    assert unauthorized.status_code == 401
    challenge = unauthorized.headers["www-authenticate"]
    assert f'resource_metadata="{PUBLIC}/.well-known/oauth-protected-resource/mcp"' in challenge
    assert f'scope="{SCOPE}"' in challenge


def test_discovery_hidden_for_api_key_only(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_entra(monkeypatch)
    monkeypatch.setattr(settings, "AUTH_MODE", "api_key_only")
    assert client.get("/.well-known/oauth-protected-resource/mcp").status_code == 404


def test_query_api_key_rejected(client: TestClient) -> None:
    response = client.post("/mcp?apiKey=test-mcp-api-key", json=_INITIALIZE)
    assert response.status_code == 401


def test_query_token_rejected(client: TestClient) -> None:
    response = client.post("/mcp?token=test-mcp-api-key", json=_INITIALIZE)
    assert response.status_code == 401


def test_query_key_rejected_even_with_valid_header(client: TestClient) -> None:
    response = client.post(
        "/mcp?apiKey=test-mcp-api-key",
        headers={"X-API-Key": "test-mcp-api-key"},
        json=_INITIALIZE,
    )
    assert response.status_code == 401


def test_bearer_token_sets_email_and_rejects_mismatch(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = _rsa_key()
    _enable_entra(monkeypatch)
    _install_jwks(monkeypatch, private)
    captured: Dict[str, Any] = {}
    _stub_search(monkeypatch, captured)
    token = _sign(
        private,
        iss=f"{ISSUER_V2}",
        aud=API_APP,
        tid=TENANT,
        sub="user-1",
        preferred_username="ada@contoso.example",
        scp="access_as_user",
    )
    headers = {"Authorization": f"Bearer {token}"}
    call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search_content",
            "arguments": {"query": "handbook"},
        },
    }
    ok = client.post("/mcp", headers=headers, json=call)
    assert ok.status_code == 200
    body = ok.json()
    assert "error" not in body
    assert captured["arguments"]["user_email"] == "ada@contoso.example"

    mismatch = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_content",
                "arguments": {"query": "handbook", "user_email": "other@contoso.example"},
            },
        },
    )
    assert mismatch.status_code == 200
    assert "does not match authenticated identity" in mismatch.json()["error"]["message"]


def test_entra_v1_issuer_and_unique_name(monkeypatch: pytest.MonkeyPatch) -> None:
    private = _rsa_key()
    _enable_entra(monkeypatch)
    _install_jwks(monkeypatch, private)
    token = _sign(
        private,
        iss=f"https://sts.windows.net/{TENANT}/",
        aud=API_AUDIENCE,
        tid=TENANT,
        sub="user-2",
        unique_name="ada@contoso.example",
        ver="1.0",
    )
    user = asyncio.run(validate_oidc_token(token))
    assert user is not None
    assert user.resolved_email() == "ada@contoso.example"
    assert user.issuer == f"https://sts.windows.net/{TENANT}"


def test_entra_rejects_bad_audience_expiry_and_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    private = _rsa_key()
    _enable_entra(monkeypatch)
    _install_jwks(monkeypatch, private)
    wrong_aud = _sign(private, iss=ISSUER_V2, aud="api://someone-else", tid=TENANT, email="ada@contoso.example")
    assert asyncio.run(validate_oidc_token(wrong_aud)) is None

    expired = _sign(
        private,
        iss=ISSUER_V2,
        aud=API_AUDIENCE,
        tid=TENANT,
        email="ada@contoso.example",
        exp=int(time.time()) - 3600,
    )
    assert asyncio.run(validate_oidc_token(expired)) is None

    other_tenant = _sign(
        private,
        iss=ISSUER_V2,
        aud=API_AUDIENCE,
        tid="99999999-9999-9999-9999-999999999999",
        email="ada@contoso.example",
    )
    assert asyncio.run(validate_oidc_token(other_tenant)) is None
