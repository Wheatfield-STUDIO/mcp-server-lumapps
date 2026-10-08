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

"""Update or insert a LumApps navigation item (content/menu/save + content/save for item fields)."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
from app.tools.api_error_utils import format_api_error, is_permission_denied, PERMISSION_DENIED_MESSAGE
from app.tools.inspect_navigation import collect_menu_items, hide_title_of, parse_item_properties
from app.tools.widget_template import deep_merge

logger = logging.getLogger(__name__)

TOOL_NAME = "update_navigation_item"

# Fields persisted by content/menu/save per discovery description.
_MENU_SAVE_FIELDS = ("parent", "hidden", "hideChildren", "isNavItem", "menuTitle", "children")

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Update (or append) a navigation item. GET content/menu/get, deep-merge, POST content/menu/save "
        "(lumsites.content.menu.save). Discovery states this endpoint only persists parent, hidden, "
        "hideChildren, isNavItem, menuTitle, and children. Other fields (icon, type, link, newTab, "
        "hideTitle-in-properties) are written on the linked content via content/get + content/save "
        "when item_id / content_id is a content uid. "
        "hideTitle is stored on ContentMenuListItem.properties (not a first-class discovery field). "
        "IMPORTANT: Always run inspect_navigation first. Before calling this tool, you MUST present "
        "the modification to the user and wait for their explicit 'Yes' or 'Confirm'. Never apply changes silently."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "LumApps site/instance ID."},
            "user_email": {"type": "string", "description": "User email for LumApps API token."},
            "item_id": {"type": "string", "description": "Existing menu item id/uid/uuid to patch."},
            "path": {"type": "string", "description": "Optional 0-based path, e.g. '0' or '0.2' into the tree."},
            "label": {"type": "string", "description": "menuTitle / content title."},
            "icon": {"type": "string", "description": "ContentMenuListItem.icon (e.g. home)."},
            "hideTitle": {"type": "boolean", "description": "Stored in item.properties.hideTitle."},
            "content_id": {"type": "string", "description": "Linked content uid (type=content)."},
            "type": {"type": "string", "description": "content | section (maps to ContentMenuListItem.type)."},
            "parent_id": {"type": "string", "description": "New parent item id (menu/save parent)."},
            "order": {"type": "integer", "description": "sortOrder / position among siblings."},
            "hidden": {"type": "boolean", "description": "ContentMenuListItem.hidden."},
            "openInNewTab": {"type": "boolean", "description": "ContentMenuListItem.newTab."},
            "lang": {"type": "string", "description": "Menu language. Default en."},
        },
        "required": ["site_id", "user_email"],
    },
}


def _item_ids(item: Dict[str, Any]) -> List[str]:
    return [str(item[k]) for k in ("uid", "id", "uuid") if item.get(k) is not None]


def find_item(
    items: List[Dict[str, Any]],
    *,
    item_id: Optional[str] = None,
    path: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[int]]:
    """Return (item, sibling_list, index). Nested children only when they are dicts."""
    if path:
        parts = [p for p in str(path).split(".") if p != ""]
        cursor = items
        node = None
        idx = None
        parent = items
        for raw in parts:
            try:
                i = int(raw)
            except ValueError:
                return None, None, None
            if i < 0 or i >= len(cursor):
                return None, None, None
            node = cursor[i]
            idx = i
            parent = cursor
            children = node.get("children") if isinstance(node, dict) else None
            cursor = children if isinstance(children, list) and children and isinstance(children[0], dict) else []
        return node if isinstance(node, dict) else None, parent, idx

    if not item_id:
        return None, None, None

    def walk(nodes: List[Any]) -> Tuple[Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[int]]:
        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            if item_id in _item_ids(node):
                return node, nodes, i
            children = node.get("children")
            if isinstance(children, list) and children and isinstance(children[0], dict):
                found = walk(children)
                if found[0] is not None:
                    return found
        return None, None, None

    return walk(items)


def apply_menu_patch(item: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge user fields onto a ContentMenuListItem (discovery keys only)."""
    patch: Dict[str, Any] = {}
    if updates.get("label") is not None:
        patch["menuTitle"] = updates["label"]
        patch["title"] = updates["label"]
    if updates.get("icon") is not None:
        patch["icon"] = updates["icon"]
    if updates.get("type") is not None:
        patch["type"] = updates["type"]
    if updates.get("content_id") is not None:
        patch["uid"] = updates["content_id"]
        patch["id"] = updates["content_id"]
    if updates.get("hidden") is not None:
        patch["hidden"] = bool(updates["hidden"])
    if updates.get("openInNewTab") is not None:
        patch["newTab"] = bool(updates["openInNewTab"])
    if updates.get("parent_id") is not None:
        patch["parentId"] = updates["parent_id"]
        patch["parent"] = updates["parent_id"]
    if updates.get("order") is not None:
        patch["sortOrder"] = int(updates["order"])
    if updates.get("hideTitle") is not None:
        props = parse_item_properties(item)
        props["hideTitle"] = bool(updates["hideTitle"])
        patch["properties"] = props
    deep_merge(item, patch)
    return item


def _menu_save_wrapper(menu: Dict[str, Any], items: List[Dict[str, Any]], lang: str) -> List[Dict[str, Any]]:
    """content/menu/save items[] is ContentMenuList[] per discovery."""
    return [
        {
            "lang": menu.get("lang") or lang,
            "items": items,
            "deleted": menu.get("deleted") or [],
        }
    ]


async def _patch_linked_content(
    token: str,
    content_id: str,
    updates: Dict[str, Any],
    lang: str,
) -> Optional[str]:
    """Write icon / hideTitle / title on the Content object (fields menu/save does not persist)."""
    needs = any(updates.get(k) is not None for k in ("icon", "hideTitle", "label", "type", "openInNewTab"))
    if not needs:
        return None
    content = await lumapps_client.get_content(content_id, token=token)
    if updates.get("label") is not None:
        title = content.get("title")
        if isinstance(title, dict):
            title = dict(title)
            title[lang] = updates["label"]
            content["title"] = title
        else:
            content["title"] = {lang: updates["label"]}
    if updates.get("type") is not None and updates["type"] in ("page", "news", "directory"):
        content["type"] = updates["type"]
    if updates.get("icon") is not None:
        content["icon"] = updates["icon"]
    nav = content.get("navigation")
    if not isinstance(nav, list):
        nav = []
    nav_item = dict(nav[0]) if nav and isinstance(nav[0], dict) else {}
    if updates.get("openInNewTab") is not None:
        nav_item["newTab"] = bool(updates["openInNewTab"])
    if updates.get("hideTitle") is not None:
        props = nav_item.get("properties")
        if isinstance(props, str) and props.strip():
            try:
                props = json.loads(props)
            except json.JSONDecodeError:
                props = {}
        if not isinstance(props, dict):
            props = {}
        props["hideTitle"] = bool(updates["hideTitle"])
        nav_item["properties"] = props
    if nav_item:
        content["navigation"] = [nav_item] + (nav[1:] if nav else [])
    content["isNavItem"] = True
    await lumapps_client.save_content(token=token, data=content, send_notifications=False)
    return content.get("uid") or content.get("id") or content_id


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    site_id = arguments.get("site_id")
    user_email = arguments.get("user_email")
    lang = (arguments.get("lang") or "en").strip() or "en"
    item_id = (arguments.get("item_id") or "").strip() or None
    path = (arguments.get("path") or "").strip() or None
    if not site_id:
        raise ValueError("Missing 'site_id' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    updates = {
        "label": arguments.get("label"),
        "icon": arguments.get("icon"),
        "hideTitle": arguments.get("hideTitle"),
        "content_id": (arguments.get("content_id") or "").strip() or None,
        "type": (arguments.get("type") or "").strip() or None,
        "parent_id": (arguments.get("parent_id") or "").strip() or None,
        "order": arguments.get("order"),
        "hidden": arguments.get("hidden"),
        "openInNewTab": arguments.get("openInNewTab"),
    }
    if all(v is None for v in updates.values()) and not item_id and not path:
        return {
            "content": [
                {"type": "text", "text": "Provide item_id or path, and at least one field to change (label, icon, hideTitle, ...)."}
            ]
        }

    logger.info("Executing update_navigation_item site_id=%s item_id=%s path=%s", site_id, item_id, path)

    try:
        token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
        menu = await lumapps_client.get_content_menu(site_id, token=token, lang=lang)
    except Exception as e:
        logger.exception("update_navigation_item get menu failed")
        return {"content": [{"type": "text", "text": f"content/menu/get failed: {format_api_error(e)}."}]}

    items = collect_menu_items(menu)
    target, siblings, idx = find_item(items, item_id=item_id, path=path)
    created = False
    if target is None:
        if item_id or path:
            return {
                "content": [
                    {"type": "text", "text": f"Navigation item not found (item_id={item_id!r} path={path!r}). Inspect first."}
                ]
            }
        target = {"isNavItem": True, "type": updates.get("type") or "content"}
        if updates.get("content_id"):
            target["uid"] = updates["content_id"]
            target["id"] = updates["content_id"]
        items.append(target)
        siblings = items
        idx = len(items) - 1
        created = True

    apply_menu_patch(target, updates)

    if updates.get("parent_id") and siblings is not None and idx is not None:
        parent, _, _ = find_item(items, item_id=updates["parent_id"])
        if parent is not None and siblings[idx] is target:
            siblings.pop(idx)
            children = parent.get("children")
            if not isinstance(children, list):
                children = []
            if children and isinstance(children[0], dict):
                children.append(target)
                parent["children"] = children
            else:
                child_ids = [str(c) for c in children]
                child_ids.append(str(target.get("uid") or target.get("id") or ""))
                parent["children"] = [c for c in child_ids if c]
                items.append(target)

    content_notes = ""
    linked_id = updates.get("content_id") or (target.get("uid") if isinstance(target.get("uid"), str) else None)
    if linked_id:
        try:
            await _patch_linked_content(token, linked_id, updates, lang)
            content_notes = f" Linked content {linked_id} patched (icon/hideTitle/title)."
        except Exception as e:
            logger.warning("update_navigation_item content/save skipped: %s", e)
            content_notes = f" Menu saved; content/save for {linked_id} failed: {format_api_error(e)}."

    try:
        saved = await lumapps_client.save_content_menu(
            token=token,
            customer_id=lumapps_client.org_id,
            instance_id=site_id,
            items=_menu_save_wrapper(menu, items, lang),
            deleted=menu.get("deleted") or [],
        )
    except Exception as e:
        logger.exception("update_navigation_item menu/save failed")
        text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"content/menu/save failed: {format_api_error(e)}"
        return {"content": [{"type": "text", "text": text}]}

    base = (settings.SITE_BASE_URL or "").rstrip("/")
    action = "created" if created else "updated"
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Navigation item {action}. id={target.get('uid') or target.get('id') or '—'} "
                    f"label={target.get('menuTitle') or target.get('title')!r} icon={target.get('icon')!r} "
                    f"hideTitle={hide_title_of(target)} type={target.get('type')}. "
                    f"menu/save persisted {_MENU_SAVE_FIELDS}. "
                    f"{content_notes} Verify at {base}. Re-run inspect_navigation."
                    f" API response keys: {sorted(saved.keys()) if isinstance(saved, dict) else type(saved).__name__}."
                ),
            }
        ]
    }
