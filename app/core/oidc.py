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

"""Provider-agnostic OIDC: discovery, JWKS, JWT validation, UserContext normalization."""

import asyncio
import logging
import threading
from typing import Any, Dict, List, Optional

import httpx
import jwt
from jwt import PyJWKClient, PyJWKClientError

from app.core.config import settings
from app.core.oauth_metadata import (
    audience_values,
    entra_configured,
    issuer_matches,
    tenant_claim_matches,
)
from app.core.user_context import UserContext

logger = logging.getLogger(__name__)

# In-memory cache: discovery doc and JWKS client (per issuer)
_discovery_cache: Dict[str, Dict[str, Any]] = {}
_jwks_clients: Dict[str, PyJWKClient] = {}
_cache_lock = asyncio.Lock()
_jwks_lock = threading.Lock()


def _discovery_url() -> Optional[str]:
    if settings.OIDC_DISCOVERY_URL:
        return settings.OIDC_DISCOVERY_URL.strip().rstrip("/")
    issuer = settings.effective_oidc_issuer()
    if issuer:
        return f"{issuer}/.well-known/openid-configuration"
    return None


async def _fetch_discovery() -> Optional[Dict[str, Any]]:
    url = _discovery_url()
    if not url:
        return None
    async with _cache_lock:
        if url in _discovery_cache:
            return _discovery_cache[url]
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            async with _cache_lock:
                _discovery_cache[url] = data
            return data
        except Exception as e:
            logger.warning("OIDC discovery fetch failed: %s", e)
            return None


def _get_jwks_client(jwks_uri: str) -> PyJWKClient:
    with _jwks_lock:
        if jwks_uri not in _jwks_clients:
            _jwks_clients[jwks_uri] = PyJWKClient(jwks_uri)
        return _jwks_clients[jwks_uri]


def _build_audience_options() -> Optional[List[str]]:
    return audience_values()


def _claims_to_user_context(claims: Dict[str, Any], issuer: str) -> UserContext:
    email_claim = settings.OIDC_EMAIL_CLAIM or "email"
    username_claim = settings.OIDC_USERNAME_CLAIM or "preferred_username"
    sub = claims.get("sub") or ""
    email = claims.get(email_claim)
    if isinstance(email, list):
        email = email[0] if email else None
    upn = claims.get("upn") or claims.get(username_claim) or claims.get("unique_name")
    if isinstance(upn, list):
        upn = upn[0] if upn else None
    aud = claims.get("aud")
    if isinstance(aud, list):
        audience = aud[0] if aud else None
    else:
        audience = aud
    scopes: List[str] = []
    for scope_key in ("scope", "scp"):
        scope_value = claims.get(scope_key)
        if isinstance(scope_value, str):
            scopes.extend(part.strip() for part in scope_value.split() if part.strip())
        elif isinstance(scope_value, list):
            scopes.extend(str(part).strip() for part in scope_value if str(part).strip())
    deduped: List[str] = []
    for scope in scopes:
        if scope not in deduped:
            deduped.append(scope)
    scopes = deduped
    return UserContext(
        sub=sub,
        email=email,
        upn=upn,
        issuer=issuer,
        audience=audience,
        scopes=scopes,
        raw_claims=dict(claims),
    )


async def validate_oidc_token(token: str) -> Optional[UserContext]:
    """
    Validate Bearer token as OIDC JWT: signature (JWKS), issuer, audience, expiry.
    Returns UserContext if valid, None otherwise.
    """
    issuer = settings.effective_oidc_issuer()
    if not issuer:
        return None
    audience = _build_audience_options()
    if entra_configured() and not audience:
        logger.warning(
            "OIDC token rejected: set OIDC_AUDIENCE to the Entra API application ID URI or app id"
        )
        return None
    try:
        unverified = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
        )
    except Exception as e:
        logger.debug("JWT decode (unverified) failed: %s", e)
        return None
    token_issuer = (unverified.get("iss") or "").strip().rstrip("/")
    if not issuer_matches(token_issuer):
        logger.warning("OIDC token rejected: issuer %s is not allowed", token_issuer or "<empty>")
        return None
    if not tenant_claim_matches(unverified):
        logger.warning("OIDC token rejected: tid claim does not match ENTRA_TENANT_ID")
        return None
    discovery = await _fetch_discovery()
    if not discovery:
        logger.debug("No OIDC discovery available")
        return None
    jwks_uri = discovery.get("jwks_uri")
    if not jwks_uri:
        logger.warning("Discovery document has no jwks_uri")
        return None
    jwks_client = _get_jwks_client(jwks_uri)

    def _verify_and_decode() -> Optional[Dict[str, Any]]:
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
        except PyJWKClientError:
            return None
        try:
            # Issuer is checked against the Entra v1 and v2 forms after the
            # signature check. PyJWT accepts a single issuer string.
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                audience=audience,
                options={
                    "verify_aud": bool(audience),
                    "verify_iss": False,
                    "verify_exp": True,
                    "verify_iat": True,
                },
                leeway=settings.OIDC_CLOCK_SKEW_SECONDS,
            )
        except jwt.ExpiredSignatureError:
            logger.warning("OIDC token rejected: expired")
            return None
        except jwt.InvalidAudienceError:
            logger.warning("OIDC token rejected: audience does not match the configured API audience")
            return None
        except jwt.PyJWTError:
            return None

    claims = await asyncio.to_thread(_verify_and_decode)
    if not claims:
        return None
    verified_issuer = (claims.get("iss") or "").strip().rstrip("/")
    if not issuer_matches(verified_issuer):
        logger.warning("OIDC token rejected: issuer %s is not allowed", verified_issuer or "<empty>")
        return None
    if not tenant_claim_matches(claims):
        logger.warning("OIDC token rejected: tid claim does not match ENTRA_TENANT_ID")
        return None
    return _claims_to_user_context(claims, verified_issuer or issuer)
