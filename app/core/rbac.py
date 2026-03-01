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

"""
User-level RBAC: tool sensitivity, OIDC role mapping (including Global Admin),
site resolution with content_id -> site_id cache, and pre-execution authorization.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from app.core.config import settings
from app.core.user_context import UserContext, get_user_context

logger = logging.getLogger(__name__)

ToolSensitivity = Literal["read", "content", "structural"]

# Tools that require site Admin (CSS, layout, global settings)
STRUCTURAL_TOOLS: Set[str] = {
    "update_global_css",
    "update_site_global_settings",
}
# Tools that allow Contributor or Admin (editing page content, widget style, or inspecting layout/CSS)
CONTENT_TOOLS: Set[str] = {
    "update_widget_style",
    "inspect_lumapps_element",
}
# All other tools are read-only
READ_TOOLS: Set[str] = {
    "search_content",
    "search_lumapps",
    "get_content_body",
    "find_person",
    "get_useful_links",
    "search_site",
}


def get_tool_sensitivity(tool_name: str) -> ToolSensitivity:
    if tool_name in STRUCTURAL_TOOLS:
        return "structural"
    if tool_name in CONTENT_TOOLS:
        return "content"
    return "read"


class RBACError(Exception):
    """Raised when a user is not allowed to run a tool. message is safe for end users."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _claim_values_to_strings(claim_value: Any) -> List[str]:
    """Normalize OIDC claim (list or string) to list of non-empty strings."""
    if claim_value is None:
        return []
    if isinstance(claim_value, str):
        return [claim_value.strip()] if claim_value.strip() else []
    if isinstance(claim_value, list):
        out: List[str] = []
        for x in claim_value:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
        return out
    return []


def _parse_pattern_list(csv: str) -> List[str]:
    return [p.strip() for p in (csv or "").split(",") if p.strip()]


def _user_has_global_admin(claims: Dict[str, Any]) -> bool:
    """
    Check global admin patterns first (priority over site-scoped).
    Global admin patterns are matched literally so one token value (e.g. lumapps:site:*:admin
    or lumapps:global:admin) grants admin on all sites without listing 500 site IDs.
    """
    patterns_csv = getattr(settings, "RBAC_GLOBAL_ADMIN_PATTERNS", "") or ""
    patterns = _parse_pattern_list(patterns_csv)
    claim_name = getattr(settings, "RBAC_ROLE_CLAIM", "groups") or "groups"
    values = _claim_values_to_strings(claims.get(claim_name))
    for v in values:
        for p in patterns:
            if v == p:
                return True
    return False


def _user_has_site_role(
    claims: Dict[str, Any],
    site_id: str,
    required: Literal["admin", "contributor"],
) -> bool:
    """
    Check if user has required role for site_id (after global admin check).
    Admin implies contributor. Uses {site_id} substitution in configured patterns.
    """
    claim_name = getattr(settings, "RBAC_ROLE_CLAIM", "groups") or "groups"
    values = _claim_values_to_strings(claims.get(claim_name))
    if not site_id:
        return False

    if required == "admin":
        patterns_csv = getattr(settings, "RBAC_ADMIN_PATTERNS", "") or ""
    else:
        patterns_csv = getattr(settings, "RBAC_CONTRIBUTOR_PATTERNS", "") or ""
    patterns = _parse_pattern_list(patterns_csv)

    for pattern in patterns:
        concrete = pattern.replace("{site_id}", site_id)
        if concrete in values:
            return True
    return False


def _user_is_admin_for_site(ctx: UserContext, site_id: str) -> bool:
    """True if user has global admin or site-scoped admin for site_id."""
    if _user_has_global_admin(ctx.raw_claims):
        return True
    return _user_has_site_role(ctx.raw_claims, site_id, "admin")


def _user_is_contributor_or_admin_for_site(ctx: UserContext, site_id: str) -> bool:
    """True if user has contributor or admin for site_id (or global admin)."""
    if _user_has_global_admin(ctx.raw_claims):
        return True
    if _user_has_site_role(ctx.raw_claims, site_id, "admin"):
        return True
    return _user_has_site_role(ctx.raw_claims, site_id, "contributor")


# ----- Content ID -> Site ID cache (TTL + max size) -----

class _ContentSiteCache:
    def __init__(self, ttl_seconds: int = 300, max_size: int = 500):
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._order: List[str] = []
        self._lock = asyncio.Lock()

    async def get(self, content_id: str) -> Optional[str]:
        async with self._lock:
            entry = self._cache.get(content_id)
            if entry is None:
                return None
            site_id, expires_at = entry
            if time.monotonic() > expires_at:
                self._cache.pop(content_id, None)
                if content_id in self._order:
                    self._order.remove(content_id)
                return None
            return site_id

    async def set(self, content_id: str, site_id: str) -> None:
        async with self._lock:
            while len(self._cache) >= self._max_size and self._order:
                evict = self._order.pop(0)
                self._cache.pop(evict, None)
            expires_at = time.monotonic() + self._ttl
            self._cache[content_id] = (site_id, expires_at)
            if content_id in self._order:
                self._order.remove(content_id)
            self._order.append(content_id)


_content_site_cache: Optional[_ContentSiteCache] = None


def _get_content_site_cache() -> _ContentSiteCache:
    global _content_site_cache
    if _content_site_cache is None:
        ttl = getattr(settings, "RBAC_CONTENT_SITE_CACHE_TTL_SECONDS", 300) or 300
        max_size = getattr(settings, "RBAC_CONTENT_SITE_CACHE_MAX_SIZE", 500) or 500
        _content_site_cache = _ContentSiteCache(ttl_seconds=ttl, max_size=max_size)
    return _content_site_cache


async def resolve_target_site_id(
    tool_name: str,
    arguments: Dict[str, Any],
    token: Optional[str] = None,
) -> Optional[str]:
    """
    Resolve the target site_id for the tool. Uses arguments['site_id'] when present.
    For update_widget_style, resolves content_id -> site_id via get_content (with cache).
    """
    site_id = arguments.get("site_id") or arguments.get("siteId")
    if isinstance(site_id, str) and site_id.strip():
        return site_id.strip()

    if tool_name in ("update_widget_style", "inspect_lumapps_element"):
        content_id = arguments.get("content_id")
        if not content_id or not isinstance(content_id, str) or not content_id.strip():
            return None
        content_id = content_id.strip()
        cache = _get_content_site_cache()
        cached = await cache.get(content_id)
        if cached is not None:
            return cached
        if token:
            from app.services.lumapps_client import lumapps_client
            try:
                content = await lumapps_client.get_content(content_id, token=token)
            except Exception as e:
                logger.warning("resolve_target_site_id get_content failed: %s", e)
                return None
            instance = content.get("instance")
            if isinstance(instance, dict):
                resolved = (instance.get("uid") or instance.get("id")) if instance else None
            else:
                resolved = instance
            if isinstance(resolved, str) and resolved.strip():
                await cache.set(content_id, resolved.strip())
                return resolved.strip()
        return None
    return None


async def authorize_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    *,
    token: Optional[str] = None,
) -> None:
    """
    Enforce user-level RBAC. Raises RBACError with a secure message if not allowed.
    When RBAC is disabled, returns without raising.
    token: optional read token for content_id -> site_id resolution (e.g. update_widget_style).
    """
    if not getattr(settings, "RBAC_ENABLED", True):
        return

    sensitivity = get_tool_sensitivity(tool_name)
    if sensitivity == "read":
        return

    ctx = get_user_context()
    deny_api_key = getattr(settings, "RBAC_DENY_API_KEY_FOR_NON_READ", True)

    if ctx is None:
        if deny_api_key:
            raise RBACError(
                "This action requires an authenticated user identity (OIDC SSO). "
                "API key alone cannot perform content or design changes."
            )
        return

    # CONTENT and STRUCTURAL require a resolvable site for role check
    if sensitivity == "structural":
        site_id = await resolve_target_site_id(tool_name, arguments, token=token)
        if not site_id:
            raise RBACError(
                "Could not determine the target site for this action. "
                "Provide site_id (or content_id for widget updates) and try again."
            )
        if not _user_is_admin_for_site(ctx, site_id):
            raise RBACError(
                "You have rights to edit content, but global design and architecture changes "
                "require Site Administrator privileges for this site."
            )
    else:
        # CONTENT: require contributor or admin for site (e.g. update_widget_style targets a page/site)
        site_id = await resolve_target_site_id(tool_name, arguments, token=token)
        if not site_id:
            raise RBACError(
                "Could not determine the target site for this action. "
                "Provide content_id (and ensure the page exists) so your role can be verified."
            )
        if not _user_is_contributor_or_admin_for_site(ctx, site_id):
            raise RBACError(
                "You do not have Contributor or Administrator rights for this site."
            )
