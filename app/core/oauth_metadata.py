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

"""OAuth discovery documents for Microsoft Entra ID.

Copilot Studio's dynamic-discovery fetch reads protected-resource metadata
from this host (RFC 9728), including the path form used for the ``/mcp``
resource. Authorization-server metadata is also published here because
Entra does not serve ``/.well-known/oauth-authorization-server``. The
authorize, token, and refresh URLs in that document are Entra's v2
endpoints. This process is not an authorization server: there is no
registration endpoint and no password login.
"""

import re
from typing import Any, Dict, List, Optional

from fastapi import Request

from app.core.config import settings

_TENANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,127}$")
_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_V2_ISSUER_RE = re.compile(r"^https://login\.microsoftonline\.com/([^/]+)/v2\.0$")
_V1_ISSUER_RE = re.compile(r"^https://sts\.windows\.net/([^/]+)$")


def _clean_tenant(value: Optional[str]) -> Optional[str]:
    tenant = (value or "").strip()
    if tenant and _TENANT_RE.fullmatch(tenant):
        return tenant
    return None


def resolve_tenant() -> Optional[str]:
    """Entra tenant id or domain from env, or parsed from an Entra issuer URL."""
    configured = _clean_tenant(settings.ENTRA_TENANT_ID)
    if configured:
        return configured
    issuer = (settings.OIDC_ISSUER_URL or "").strip().rstrip("/")
    match = _V2_ISSUER_RE.fullmatch(issuer) or _V1_ISSUER_RE.fullmatch(issuer)
    if not match:
        return None
    return _clean_tenant(match.group(1))


def entra_configured() -> bool:
    return resolve_tenant() is not None


def discovery_enabled() -> bool:
    """Publish Copilot discovery only when this process will accept Entra tokens."""
    return settings.AUTH_MODE != "api_key_only" and entra_configured()


def entra_issuer(tenant: Optional[str] = None) -> Optional[str]:
    tid = tenant or resolve_tenant()
    if not tid:
        return None
    return f"https://login.microsoftonline.com/{tid}/v2.0"


def entra_authorize_url(tenant: Optional[str] = None) -> Optional[str]:
    tid = tenant or resolve_tenant()
    if not tid:
        return None
    return f"https://login.microsoftonline.com/{tid}/oauth2/v2.0/authorize"


def entra_token_url(tenant: Optional[str] = None) -> Optional[str]:
    tid = tenant or resolve_tenant()
    if not tid:
        return None
    return f"https://login.microsoftonline.com/{tid}/oauth2/v2.0/token"


def entra_jwks_url(tenant: Optional[str] = None) -> Optional[str]:
    tid = tenant or resolve_tenant()
    if not tid:
        return None
    return f"https://login.microsoftonline.com/{tid}/discovery/v2.0/keys"


def configured_scopes() -> List[str]:
    raw = settings.OIDC_SCOPES or ""
    return [part.strip() for part in raw.split() if part.strip()]


def allowed_issuers() -> List[str]:
    """Issuers accepted for the configured IdP.

    Entra v2 access tokens use ``https://login.microsoftonline.com/{tid}/v2.0``.
    When the API app still issues v1 tokens, ``iss`` is
    ``https://sts.windows.net/{tid}/``. Both are accepted for the same tenant.
    """
    primary = settings.effective_oidc_issuer()
    if not primary:
        return []
    primary = primary.rstrip("/")
    found = [primary]
    v2 = _V2_ISSUER_RE.fullmatch(primary)
    if v2:
        found.append(f"https://sts.windows.net/{v2.group(1)}")
    v1 = _V1_ISSUER_RE.fullmatch(primary)
    if v1:
        found.append(f"https://login.microsoftonline.com/{v1.group(1)}/v2.0")
    return found


def issuer_matches(token_issuer: str) -> bool:
    got = (token_issuer or "").strip().rstrip("/")
    return bool(got) and got in allowed_issuers()


def tenant_claim_matches(claims: Dict[str, Any]) -> bool:
    """When both the configured tenant and the ``tid`` claim are GUIDs, they must match."""
    tid = claims.get("tid")
    if not isinstance(tid, str) or not tid.strip():
        return True
    tenant = resolve_tenant()
    if not tenant or not _GUID_RE.fullmatch(tenant):
        return True
    return tid.strip().lower() == tenant.lower()


def expand_audience(value: str) -> List[str]:
    """Accept the Application ID URI and the app id GUID for one Entra API.

    v2 access tokens usually put ``api://{app-id}`` in ``aud``. v1 tokens, and
    some v2 tokens, put the app id GUID. A configured value of either form
    accepts both.
    """
    raw = value.strip().rstrip("/")
    if not raw:
        return []
    found = [raw]
    body = raw[6:] if raw.lower().startswith("api://") else raw
    app_id = body.split("/")[0]
    if _GUID_RE.fullmatch(app_id):
        for candidate in (app_id, f"api://{app_id}"):
            if candidate not in found:
                found.append(candidate)
    return found


def audience_values() -> Optional[List[str]]:
    raw: List[str] = []
    if settings.OIDC_AUDIENCE and settings.OIDC_AUDIENCE.strip():
        raw.append(settings.OIDC_AUDIENCE.strip())
    if settings.OIDC_CLIENT_ID and settings.OIDC_CLIENT_ID.strip():
        client_id = settings.OIDC_CLIENT_ID.strip()
        if client_id not in raw:
            raw.append(client_id)
    expanded: List[str] = []
    for value in raw:
        for item in expand_audience(value):
            if item not in expanded:
                expanded.append(item)
    return expanded or None


def public_origin(request: Request) -> str:
    """Public origin for the ``resource`` identifier and metadata URLs."""
    configured = (settings.MCP_PUBLIC_URL or "").strip().rstrip("/")
    if configured.endswith("/mcp"):
        configured = configured[: -len("/mcp")].rstrip("/")
    if configured:
        return configured
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        proto = (request.headers.get("x-forwarded-proto") or "https").split(",")[0].strip().lower()
        host = forwarded_host.split(",")[0].strip()
        return f"{proto}://{host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def resource_url(request: Request) -> str:
    return f"{public_origin(request)}/mcp"


def protected_resource_metadata(request: Request) -> Optional[Dict[str, Any]]:
    if not discovery_enabled():
        return None
    issuer = entra_issuer()
    if not issuer:
        return None
    document: Dict[str, Any] = {
        "resource": resource_url(request),
        "authorization_servers": [issuer],
        "bearer_methods_supported": ["header"],
    }
    scopes = configured_scopes()
    if scopes:
        document["scopes_supported"] = scopes
    return document


def authorization_server_metadata() -> Optional[Dict[str, Any]]:
    """RFC 8414 document whose authorize and token URLs are Entra's.

    Refresh uses the same token endpoint (``grant_type=refresh_token``).
    There is no ``registration_endpoint``: Entra does not implement dynamic
    client registration, and this server does not invent one.
    """
    if not discovery_enabled():
        return None
    issuer = entra_issuer()
    authorize = entra_authorize_url()
    token = entra_token_url()
    jwks = entra_jwks_url()
    if not issuer or not authorize or not token or not jwks:
        return None
    document: Dict[str, Any] = {
        "issuer": issuer,
        "authorization_endpoint": authorize,
        "token_endpoint": token,
        "jwks_uri": jwks,
        "response_types_supported": ["code"],
        "response_modes_supported": ["query", "form_post"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_basic",
            "client_secret_post",
        ],
        "code_challenge_methods_supported": ["S256"],
    }
    scopes = configured_scopes()
    if scopes:
        document["scopes_supported"] = scopes
    return document


def www_authenticate_header(request: Request) -> Optional[str]:
    """RFC 9728 challenge so a 401 points at protected-resource metadata."""
    if not discovery_enabled():
        return None
    metadata = f"{public_origin(request)}/.well-known/oauth-protected-resource/mcp"
    parts = ['Bearer realm="mcp"']
    scopes = configured_scopes()
    if scopes:
        parts.append(f'scope="{" ".join(scopes)}"')
    parts.append(f'resource_metadata="{metadata}"')
    return ", ".join(parts)
