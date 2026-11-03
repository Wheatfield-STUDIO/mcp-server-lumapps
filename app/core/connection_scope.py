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

"""Per-connection site and page filters from the /mcp query string.

Copilot Studio's connection form has no field for these filters. The maker
puts them in the server URL. The model cannot change that URL. A missing
parameter does not filter. A parameter that is present but empty allows nothing.
"""

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set
from urllib.parse import parse_qsl

OUT_OF_SCOPE = "This connection is not allowed to use that site or page."


class ConnectionScopeError(ValueError):
    """The /mcp URL does not allow this site or page. The message does not list ids."""

    def __init__(self) -> None:
        super().__init__(OUT_OF_SCOPE)

_SCOPE: ContextVar[Optional["ConnectionScope"]] = ContextVar("mcp_connection_scope", default=None)

_SITE_KEYS = ("instanceId", "instance_id", "siteId", "site_id", "customerInstanceId")
_CONTENT_KEYS = ("id", "uid", "contentId", "content_id")


@dataclass(frozen=True)
class ConnectionScope:
    """Allow-lists for this MCP connection.

    ``None`` means the query parameter was absent (no filter).
    An empty frozenset means the parameter was present but named nothing.
    """

    sites: Optional[frozenset]
    pages: Optional[frozenset]

    def site_allowed(self, site_id: Optional[str]) -> bool:
        if self.sites is None:
            return True
        if not site_id:
            return False
        return site_id in self.sites

    def page_allowed(self, content_id: Optional[str], site_id: Optional[str]) -> bool:
        """A page passes ``pages`` when that param is set, and ``sites`` when that param is set."""
        if self.pages is not None and (not content_id or content_id not in self.pages):
            return False
        if self.sites is not None and (not site_id or site_id not in self.sites):
            return False
        return True

    def blocks_all_pages(self) -> bool:
        if self.pages is not None and not self.pages:
            return True
        if self.sites is not None and not self.sites:
            return True
        return False

    def blocks_all_sites(self) -> bool:
        return self.sites is not None and not self.sites


def get_connection_scope() -> ConnectionScope:
    current = _SCOPE.get()
    if current is None:
        return ConnectionScope(sites=None, pages=None)
    return current


def set_connection_scope(scope: ConnectionScope) -> Token:
    return _SCOPE.set(scope)


def reset_connection_scope(token: Token) -> None:
    _SCOPE.reset(token)


def _ids_from_values(values: Iterable[str]) -> frozenset:
    found = []
    for value in values:
        for part in str(value).split(","):
            item = part.strip()
            if item:
                found.append(item)
    return frozenset(found)


def scope_from_query(params: Mapping[str, str]) -> ConnectionScope:
    """Build a scope from a query string. Does not log the ids."""
    if hasattr(params, "getlist"):
        sites_values = params.getlist("sites") if "sites" in params else None
        pages_values = params.getlist("pages") if "pages" in params else None
    else:
        grouped: Dict[str, List[str]] = {}
        if isinstance(params, str):
            pairs = parse_qsl(params, keep_blank_values=True)
        else:
            pairs = list(params.items())
        for key, value in pairs:
            grouped.setdefault(key, []).append(value)
        sites_values = grouped.get("sites")
        pages_values = grouped.get("pages")
    return ConnectionScope(
        sites=None if sites_values is None else _ids_from_values(sites_values),
        pages=None if pages_values is None else _ids_from_values(pages_values),
    )


def extract_site_id(item: Any) -> Optional[str]:
    """Site/instance id from a LumApps content or search hit, when one is present."""
    if isinstance(item, str) and item.strip():
        return item.strip()
    if not isinstance(item, dict):
        return None
    for key in _SITE_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    instance = item.get("instance")
    if isinstance(instance, str) and instance.strip():
        return instance.strip()
    if isinstance(instance, dict):
        for key in ("uid", "id"):
            value = instance.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("content", "customerContent", "directoryEntry"):
        nested = item.get(key)
        if isinstance(nested, dict):
            found = extract_site_id(nested)
            if found:
                return found
    return None


def extract_content_ids(item: Mapping[str, Any]) -> Set[str]:
    found: Set[str] = set()
    for key in _CONTENT_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            found.add(value.strip())
    directory_entry = item.get("directoryEntry")
    if isinstance(directory_entry, dict):
        for key in _CONTENT_KEYS:
            value = directory_entry.get(key)
            if isinstance(value, str) and value.strip():
                found.add(value.strip())
    return found


def page_item_allowed(item: Mapping[str, Any]) -> bool:
    scope = get_connection_scope()
    if scope.sites is None and scope.pages is None:
        return True
    content_ids = extract_content_ids(item)
    content_id = next(iter(content_ids), None)
    if scope.pages is not None:
        if not content_ids.intersection(scope.pages):
            return False
        content_id = next(iter(content_ids.intersection(scope.pages)))
    return scope.page_allowed(content_id, extract_site_id(item))


def filter_page_items(items: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    return [item for item in items if isinstance(item, dict) and page_item_allowed(item)]


def filter_site_items(items: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    scope = get_connection_scope()
    if scope.sites is None:
        return [item for item in items if isinstance(item, dict)]
    kept = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_uid = item.get("uid")
        raw_id = item.get("id")
        if isinstance(raw_uid, str) and raw_uid.strip():
            site_id = raw_uid.strip()
        elif isinstance(raw_id, str) and raw_id.strip():
            site_id = raw_id.strip()
        else:
            site_id = None
        if scope.site_allowed(site_id):
            kept.append(item)
    return kept


def ensure_site_in_scope(site_id: Optional[str]) -> None:
    if not get_connection_scope().site_allowed(site_id if isinstance(site_id, str) else None):
        raise ConnectionScopeError()


async def ensure_page_in_scope(content_id: Optional[str], token: Optional[str]) -> None:
    """Reject a page before its body or a write is returned. Does not log ids."""
    scope = get_connection_scope()
    page_id = content_id.strip() if isinstance(content_id, str) else None
    if scope.pages is not None and (not page_id or page_id not in scope.pages):
        raise ConnectionScopeError()
    if scope.sites is None:
        return
    if not scope.sites:
        raise ConnectionScopeError()
    if not token or not page_id:
        raise ConnectionScopeError()
    from app.services.lumapps_client import lumapps_client

    probe = await lumapps_client.get_content(page_id, token=token, fields="instance")
    if not scope.site_allowed(extract_site_id(probe)):
        raise ConnectionScopeError()
