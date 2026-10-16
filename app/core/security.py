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

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Request, Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.oauth_metadata import www_authenticate_header
from app.core.oidc import validate_oidc_token
from app.core.user_context import UserContext, set_user_context

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)

# Query names that used to authenticate. They are rejected so a key cannot
# bypass OAuth by riding in the URL, proxy logs, or access logs.
_QUERY_CREDENTIAL_NAMES = ("apiKey", "token")


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


def _query_credential_present(request: Request) -> bool:
    return any(name in request.query_params for name in _QUERY_CREDENTIAL_NAMES)


def _unauthorized(request: Request, detail: str) -> HTTPException:
    headers = {}
    challenge = www_authenticate_header(request)
    if challenge:
        headers["WWW-Authenticate"] = challenge
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=headers or None,
    )


async def validate_api_key_header_or_query(
    request: Request,
    api_key_header_val: str = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> AuthResult:
    """
    Dual-mode auth: OIDC preferred (Bearer JWT), API key header fallback when allowed.
    Sets request-scoped user context when OIDC succeeds.
    Query-string credentials (apiKey, token) are rejected.
    """
    if _query_credential_present(request):
        logger.warning("Rejected API key supplied in the query string")
        raise _unauthorized(
            request,
            "API keys in the query string are not accepted. Use the X-API-Key header or Authorization: Bearer.",
        )

    bearer_key = _get_bearer_key(bearer)
    allow_fallback = settings.AUTH_ALLOW_API_KEY_FALLBACK and settings.MCP_API_KEY

    if settings.AUTH_MODE == "api_key_only":
        api_key = api_key_header_val or bearer_key
        if not api_key:
            raise _unauthorized(
                request,
                "Missing API Key (use the X-API-Key header or Authorization: Bearer)",
            )
        if api_key != settings.MCP_API_KEY:
            raise _unauthorized(request, "Invalid API Key")
        set_user_context(None)
        return AuthResult(api_key=api_key, user_context=None)

    # oidc_preferred: try Bearer as OIDC first
    if bearer_key and settings.effective_oidc_issuer():
        user_ctx = await validate_oidc_token(bearer_key)
        if user_ctx is not None:
            set_user_context(user_ctx)
            return AuthResult(api_key=None, user_context=user_ctx)

    # Fallback: API key from the X-API-Key header, or Bearer when it is the static key
    if allow_fallback:
        api_key = None
        if api_key_header_val and settings.MCP_API_KEY and api_key_header_val == settings.MCP_API_KEY:
            api_key = api_key_header_val
        elif bearer_key and settings.MCP_API_KEY and bearer_key == settings.MCP_API_KEY:
            api_key = bearer_key
        if api_key:
            set_user_context(None)
            return AuthResult(api_key=api_key, user_context=None)

    raise _unauthorized(
        request,
        "Unauthorized: provide a valid Bearer (OIDC) token or X-API-Key header",
    )
