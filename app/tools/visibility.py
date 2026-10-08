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

"""Resolve LumApps visibility groups (feeds) by name. Used by content and directory writes."""

from typing import Any, Dict, List, Optional, Tuple

from app.services.lumapps_client import lumapps_client
from app.services.html_parser import get_localized_value


class VisibilityError(ValueError):
    """Clear validation error: save refused without a visibility group."""


def require_visibility_group(value: Any, *, default: str = "All") -> str:
    """Default to All; refuse empty/whitespace so we never POST a save without a group."""
    if value is None:
        value = default
    if not isinstance(value, str) or not value.strip():
        raise VisibilityError(
            "visibility_group is required (default 'All'). Refusing to save without a visibility group."
        )
    return value.strip()


def require_visibility_groups(value: Any, *, default: Optional[List[str]] = None) -> List[str]:
    if value is None:
        value = list(default or ["All"])
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not value:
        raise VisibilityError(
            "visibility_groups is required (default ['All']). Refusing to save without a visibility group."
        )
    names = [str(v).strip() for v in value if str(v).strip()]
    if not names:
        raise VisibilityError(
            "visibility_groups is required (default ['All']). Refusing to save without a visibility group."
        )
    return names


def _feed_display_name(feed: Dict[str, Any], lang: str = "en") -> str:
    name = feed.get("name")
    if isinstance(name, dict):
        return (get_localized_value(name, lang) or "").strip()
    return str(name or "").strip()


def _feed_uid(feed: Dict[str, Any]) -> Optional[str]:
    uid = feed.get("uid") or feed.get("id")
    return str(uid).strip() if uid else None


async def resolve_feed_ids(
    token: str,
    site_id: str,
    names: List[str],
    lang: str = "en",
) -> Tuple[List[str], List[str], List[str]]:
    """
    Resolve visibility group names to feed uids via feed/list.
    Returns (resolved_uids, missing_names, available_names).
    """
    data = await lumapps_client.list_feeds(token=token, instance=site_id, max_results=100)
    items = data.get("items") or []
    by_name: Dict[str, str] = {}
    available: List[str] = []
    for feed in items:
        if not isinstance(feed, dict):
            continue
        uid = _feed_uid(feed)
        label = _feed_display_name(feed, lang)
        if label:
            available.append(label)
        if uid and label:
            by_name[label.lower()] = uid
        inner = (feed.get("functionalInnerId") or "").strip()
        if uid and inner:
            by_name.setdefault(inner.lower(), uid)

    resolved: List[str] = []
    missing: List[str] = []
    for name in names:
        uid = by_name.get(name.lower())
        if uid:
            resolved.append(uid)
        else:
            missing.append(name)
    return resolved, missing, available
