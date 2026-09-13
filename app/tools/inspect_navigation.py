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

"""Inspect LumApps site navigation (discovery: content/menu/get → ContentMenuList)."""

import json
import logging
from typing import Any, Dict, List, Optional

from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
from app.tools.api_error_utils import format_api_error

logger = logging.getLogger(__name__)

TOOL_NAME = "inspect_navigation"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Inspect the site navigation tree. Uses GET _ah/api/lumsites/v1/content/menu/get "
        "(lumsites.content.menu.get; customer, instance, lang required). "
        "Items are ContentMenuListItem: id/uid/uuid, title, menuTitle, type, icon, hidden, hideChildren, "
        "isNavItem, link, newTab, children, parentId, sortOrder, properties, slugFull. "
        "hideTitle is not a first-class discovery field; when present it is read from item.properties "
        "(JSON object or string). Use this before update_navigation_item. "
        "IMPORTANT: Structural inspect — still prefer presenting the tree before any write. "
        "This tool itself is read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "LumApps site/instance ID."},
            "user_email": {"type": "string", "description": "User email for LumApps API token."},
            "lang": {"type": "string", "description": "Menu language (required by the API). Default en."},
        },
        "required": ["site_id", "user_email"],
    },
}


def parse_item_properties(item: Dict[str, Any]) -> Dict[str, Any]:
    raw = item.get("properties")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def hide_title_of(item: Dict[str, Any]) -> Optional[bool]:
    props = parse_item_properties(item)
    for key in ("hideTitle", "hide_title", "hidetitle"):
        if key in props:
            return bool(props[key])
    if "hideTitle" in item:
        return bool(item.get("hideTitle"))
    return None


def item_type_label(item: Dict[str, Any]) -> str:
    raw = (item.get("type") or "").strip().lower()
    if raw in ("content", "page", "news", "directory"):
        return "content"
    if raw in ("section", "menu", "parent"):
        return "section"
    if item.get("link") or item.get("uid") or item.get("id"):
        return raw or "content"
    return raw or "section"


def format_nav_item(item: Dict[str, Any], indent: int = 0) -> List[str]:
    prefix = "  " * indent
    uid = item.get("uid") or item.get("id") or item.get("uuid") or "—"
    label = item.get("menuTitle") or item.get("title") or "—"
    hide_title = hide_title_of(item)
    lines = [
        f"{prefix}- {label} (id={uid} type={item_type_label(item)} icon={item.get('icon')!r} "
        f"hideTitle={hide_title} hidden={item.get('hidden')} newTab={item.get('newTab')} "
        f"isNavItem={item.get('isNavItem')} slug={item.get('slugFull') or '—'} "
        f"link={item.get('link') or '—'} sortOrder={item.get('sortOrder')})"
    ]
    props = parse_item_properties(item)
    if props:
        lines.append(f"{prefix}  properties: {json.dumps(props)}")
    children = item.get("children") or []
    if children and isinstance(children, list) and children and isinstance(children[0], dict):
        for child in children:
            lines.extend(format_nav_item(child, indent + 1))
    elif children:
        lines.append(f"{prefix}  children_ids: {json.dumps(children)}")
    return lines


def collect_menu_items(menu: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = menu.get("items") or []
    if items and isinstance(items[0], dict) and "items" in items[0] and isinstance(items[0].get("items"), list):
        # Already a list of ContentMenuList wrappers
        out: List[Dict[str, Any]] = []
        for block in items:
            out.extend(block.get("items") or [])
        return out
    return items


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    site_id = arguments.get("site_id")
    user_email = arguments.get("user_email")
    lang = (arguments.get("lang") or "en").strip() or "en"
    if not site_id:
        raise ValueError("Missing 'site_id' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    logger.info("Executing inspect_navigation site_id=%s lang=%s", site_id, lang)
    try:
        token = await lumapps_auth.get_inspect_token(user_email=user_email)
        menu = await lumapps_client.get_content_menu(site_id, token=token, lang=lang)
    except Exception as e:
        logger.exception("inspect_navigation content/menu/get failed")
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"content/menu/get failed: {format_api_error(e)}. "
                        "Endpoint: GET _ah/api/lumsites/v1/content/menu/get?customer=&instance=&lang="
                    ),
                }
            ]
        }

    items = collect_menu_items(menu)
    lines = [
        "=== Navigation (content/menu/get) ===",
        f"site_id: {site_id}",
        f"lang: {menu.get('lang') or lang}",
        f"items: {len(items)}",
        "",
    ]
    if not items:
        lines.append("No navigation items.")
    else:
        for item in items:
            if isinstance(item, dict):
                lines.extend(format_nav_item(item))
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}
