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

from dataclasses import dataclass
from typing import Optional

from fastapi import Request, Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.oidc import validate_oidc_token
from app.core.user_context import UserContext, set_user_context

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)

_QUERY_KEY_REJECTED = (
    "API keys in the query string are not allowed. "
    "Use the X-API-Key header or Authorization: Bearer."
)


@dataclass
class AuthResult:
    """Result of MCP auth: either API key (legacy/fallback) or verified OIDC user."""

    api_key: Optional[str] = None
    user_context: Optional[UserContext] = None


def reject_query_string_api_keys(request: Request) -> None:
    """Reject ?apiKey= and ?token= (any case) so keys are not stored in URLs or access logs."""
    names = {key.lower() for key in request.query_params.keys()}
    if "apikey" in names or "token" in names:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_QUERY_KEY_REJECTED,
        )


async def validate_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
        )
    if not settings.MCP_API_KEY or api_key != settings.MCP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key


def _get_bearer_key(credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return None


def _header_api_key(api_key_header_val: Optional[str]) -> Optional[str]:
    if not api_key_header_val or not settings.MCP_API_KEY:
        return None
    if api_key_header_val != settings.MCP_API_KEY:
        return None
    return api_key_header_val


async def validate_api_key_header_or_query(
    request: Request,
    api_key_header_val: str = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> AuthResult:
    """
    Dual-mode auth: OIDC preferred (Bearer JWT), API key fallback when allowed.
    API key is accepted only from X-API-Key or Authorization: Bearer (not query string).
    Sets request-scoped user context when OIDC succeeds.
    """
    reject_query_string_api_keys(request)

    bearer_key = _get_bearer_key(bearer)
    allow_fallback = settings.AUTH_ALLOW_API_KEY_FALLBACK and settings.MCP_API_KEY

    if settings.AUTH_MODE == "api_key_only":
        api_key = api_key_header_val or (
            bearer_key if (settings.MCP_API_KEY and bearer_key == settings.MCP_API_KEY) else None
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API Key (use X-API-Key or Authorization: Bearer)",
            )
        if api_key != settings.MCP_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key",
            )
        set_user_context(None)
        return AuthResult(api_key=api_key, user_context=None)

    # oidc_preferred: try Bearer as OIDC first
    if bearer_key and settings.OIDC_ISSUER_URL:
        user_ctx = await validate_oidc_token(bearer_key)
        if user_ctx is not None:
            set_user_context(user_ctx)
            return AuthResult(api_key=None, user_context=user_ctx)

    # Fallback: API key from X-API-Key or Bearer only
    if allow_fallback:
        api_key = _header_api_key(api_key_header_val)
        if not api_key and bearer_key:
            api_key = bearer_key if (settings.MCP_API_KEY and bearer_key == settings.MCP_API_KEY) else None
        if api_key:
            set_user_context(None)
            return AuthResult(api_key=api_key, user_context=None)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: provide a valid Bearer (OIDC) token or API key",
    )
