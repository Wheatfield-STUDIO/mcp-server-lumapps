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

"""Update a widget's style (padding, margin, border, etc.) on a LumApps page via content/save."""

import json
import logging
from typing import Any, Dict, List, Tuple

from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client

logger = logging.getLogger(__name__)

TOOL_NAME = "update_widget_style"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": "Update a widget's style or content on a LumApps page (e.g. reduce title padding, change margin). Loads the page layout to find the widget, then saves via content/save by updating content.template. IMPORTANT: Always perform an inspect_lumapps_element first. Before calling this tool, you MUST present the modification you intend to apply to the user and wait for their explicit 'Yes' or 'Confirm' in the chat. Never apply changes silently.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "description": "LumApps content/page ID (e.g. homepage)."},
            "widget_id": {"type": "string", "description": "Widget ID (widgetId from the layout)."},
            "style_updates": {"type": "string", "description": "JSON object: body.style (paddingTop, paddingBottom, marginTop...), style (border, margin...). Example: {\"body\": {\"style\": {\"paddingTop\": 8}}}."},
            "user_email": {"type": "string", "description": "User email for LumApps API token."},
        },
        "required": ["content_id", "widget_id", "style_updates", "user_email"],
    },
}


def _deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> None:
    """Merge updates into base in place."""
    for k, v in updates.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def _collect_template_widgets(components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect all widgets from template.components in depth-first order (row → cells → components)."""
    out: List[Dict[str, Any]] = []

    def walk(items: List[Dict[str, Any]]) -> None:
        for c in items or []:
            if (c.get("type") or "").lower() == "widget":
                out.append(c)
            for key in ("cells", "components"):
                walk(c.get(key) or [])

    walk(components)
    return out


def _layout_style_updates_to_template(layout_style_updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map layout-format style (body.style, style) to content.template widget format.
    template uses properties.style.content (padding, margin) and properties.style.main (border, margin).
    """
    template_update: Dict[str, Any] = {}
    body_style = (layout_style_updates.get("body") or {}).get("style")
    top_style = layout_style_updates.get("style")
    if body_style or top_style:
        style: Dict[str, Any] = {}
        if body_style:
            style.setdefault("content", {}).update(body_style)
        if top_style:
            style.setdefault("main", {}).update(top_style)
        if style:
            template_update["properties"] = {"style": style}
    return template_update


async def _save_via_content(
    content_id: str,
    widget_id: str,
    style_updates: Dict[str, Any],
    token: str,
    layout: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Find widget in layout, match to content.template by type+index, apply style, save_content.
    Returns (success, message).
    """
    widgets_layout = layout.get("widgets") or []
    idx = None
    w_type = None
    for i, item in enumerate(widgets_layout):
        w = item.get("widget") or item
        if (w.get("widgetId") or w.get("id")) == widget_id:
            idx = i
            w_type = (w.get("widgetType") or w.get("body", {}).get("type") or "").strip()
            break
    if idx is None or not w_type:
        return False, f"Widget {widget_id!r} not found in layout."

    same_type_indices = [i for i, item in enumerate(widgets_layout) if (item.get("widget") or item).get("widgetType") == w_type]
    try:
        type_index = same_type_indices.index(idx)
    except ValueError:
        type_index = 0

    content = await lumapps_client.get_content(content_id, token=token)
    template = content.get("template") or {}
    components = template.get("components") or []
    template_widgets = _collect_template_widgets(components)
    by_type = [tw for tw in template_widgets if (tw.get("widgetType") or "").strip() == w_type]
    if type_index >= len(by_type):
        return False, f"Widget type {w_type!r} at index {type_index} not found in content.template (found {len(by_type)})."

    target = by_type[type_index]
    template_delta = _layout_style_updates_to_template(style_updates)
    if template_delta:
        _deep_merge(target, template_delta)

    await lumapps_client.save_content(token=token, data=content, send_notifications=False)
    return True, "Content saved."


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    content_id = arguments.get("content_id")
    widget_id = arguments.get("widget_id")
    style_updates_raw = arguments.get("style_updates")
    user_email = arguments.get("user_email")

    if not content_id or not widget_id or not user_email:
        return {
            "content": [{"type": "text", "text": "Missing required argument: content_id, widget_id, or user_email."}]
        }
    if not style_updates_raw:
        return {"content": [{"type": "text", "text": "Missing style_updates (JSON object)."}]}

    try:
        style_updates = json.loads(style_updates_raw) if isinstance(style_updates_raw, str) else dict(style_updates_raw)
    except json.JSONDecodeError as e:
        return {"content": [{"type": "text", "text": f"Invalid style_updates JSON: {e}"}]}
    if not isinstance(style_updates, dict):
        return {"content": [{"type": "text", "text": "style_updates must be a JSON object."}]}

    logger.info(f"Executing update_widget_style content_id={content_id!r}, widget_id={widget_id!r}")

    try:
        token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
        layout = await lumapps_client.get_content_layout(content_id, token=token)
    except Exception as e:
        logger.exception("get_content_layout failed")
        return {"content": [{"type": "text", "text": f"Failed to load layout: {e}"}]}

    try:
        ok, msg = await _save_via_content(content_id, widget_id, style_updates, token, layout)
    except Exception as e:
        logger.exception("save via content failed")
        return {"content": [{"type": "text", "text": f"Save failed: {e}"}]}

    if not ok:
        return {"content": [{"type": "text", "text": msg}]}

    return {
        "content": [
            {"type": "text", "text": f"Widget {widget_id!r} updated and page saved via content/save. Applied: {json.dumps(style_updates)}"}
        ]
    }
