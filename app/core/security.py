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

from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.oidc import validate_oidc_token
from app.core.user_context import UserContext, set_user_context

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="apiKey", auto_error=False)
api_key_query_token = APIKeyQuery(name="token", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthResult:
    """Result of MCP auth: either API key (legacy/fallback) or verified OIDC user."""

    api_key: Optional[str] = None
    user_context: Optional[UserContext] = None


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


def _try_api_key(
    api_key_header_val: str,
    api_key_query_val: str,
    token_query_val: str,
) -> Optional[str]:
    raw = api_key_header_val or api_key_query_val or token_query_val
    if not raw or not settings.MCP_API_KEY or raw != settings.MCP_API_KEY:
        return None
    return raw


async def validate_api_key_header_or_query(
    api_key_header_val: str = Security(api_key_header),
    api_key_query_val: str = Security(api_key_query),
    token_query_val: str = Security(api_key_query_token),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> AuthResult:
    """
    Dual-mode auth: OIDC preferred (Bearer JWT), API key fallback when allowed.
    Sets request-scoped user context when OIDC succeeds.
    """
    bearer_key = _get_bearer_key(bearer)
    allow_fallback = settings.AUTH_ALLOW_API_KEY_FALLBACK and settings.MCP_API_KEY

    if settings.AUTH_MODE == "api_key_only":
        api_key = api_key_header_val or api_key_query_val or token_query_val or bearer_key
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API Key (use X-API-Key, Authorization: Bearer, or ?apiKey= or ?token=)",
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

    # Fallback: API key from header, query, or Bearer
    if allow_fallback:
        api_key = _try_api_key(api_key_header_val, api_key_query_val, token_query_val)
        if not api_key and bearer_key:
            api_key = bearer_key if (settings.MCP_API_KEY and bearer_key == settings.MCP_API_KEY) else None
        if api_key:
            set_user_context(None)
            return AuthResult(api_key=api_key, user_context=None)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: provide a valid Bearer (OIDC) token or API key",
    )
