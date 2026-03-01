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

"""Inspect a LumApps page layout (widgets, styles) or site global CSS via API. No browser."""

import json
import logging
from typing import Any, Dict, List

from app.tools.api_error_utils import format_api_error
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client

logger = logging.getLogger(__name__)

TOOL_NAME = "inspect_lumapps_element"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": "Inspect a LumApps page layout (widgets, padding, margin, border, title text) or the site global CSS. Use content_id + user_email to get the page layout (e.g. homepage) and see why a widget looks wrong (e.g. title too high). Use site_id + user_email to get the site's global stylesheets. No browser; works via API. Use the result to fix layout via update_global_css or future layout API.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "description": "LumApps content/page ID (e.g. homepage content ID). Use with user_email to get the page layout (widgets and their styles)."},
            "site_id": {"type": "string", "description": "LumApps site/instance ID. Use with user_email to get the site global CSS (stylesheets)."},
            "user_email": {"type": "string", "description": "User email for LumApps API token (required for both layout and style inspection)."},
        },
        "required": [],
    },
}

MAX_CSS_EXCERPT = 8000


def _flatten_style(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively flatten nested style objects (e.g. content.paddingTop) into a simple dict for display."""
    out: Dict[str, Any] = {}
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        if isinstance(v, dict) and v and not any(isinstance(x, (dict, list)) for x in v.values()):
            for k2, v2 in v.items():
                out[f"{k}.{k2}"] = v2
        else:
            out[k] = v
    return out


def _format_widget_entry(widget_id: str, w_type: str, raw: Dict[str, Any]) -> List[str]:
    """Format a single widget from the layout's widgets[] for readable output."""
    lines = [f"  • {w_type!r} (id: {widget_id})"]
    body = raw.get("body") or {}
    style = raw.get("style") or {}
    if body.get("text") is not None:
        lines.append(f"      text: {body.get('text')!r}")
    if body.get("typography"):
        lines.append(f"      typography: {body.get('typography')}")
    if body.get("style"):
        lines.append(f"      body.style: {json.dumps(body['style'])}")
    if body.get("properties", {}).get("style"):
        lines.append(f"      body.properties.style: {json.dumps(body['properties']['style'])}")
    flat_style = _flatten_style(style)
    if flat_style:
        lines.append(f"      style: {json.dumps(flat_style)}")
    return lines


def _format_layout_response(layout: Dict[str, Any]) -> str:
    """Format layout API response for human/AI reading: components tree summary + widgets with styles."""
    lines = [
        "=== Page layout (API) ===",
        f"Layout ID: {layout.get('id', '—')}",
        f"Revision: {layout.get('revisionNumber', '—')}",
        "",
    ]
    widgets = layout.get("widgets") or []
    if not widgets:
        lines.append("No widgets in this layout.")
        return "\n".join(lines)

    lines.append("--- Widgets (type, id, text, style) ---")
    for item in widgets:
        w = item.get("widget") or item
        w_id = w.get("widgetId") or w.get("id") or "—"
        w_type = w.get("widgetType") or w.get("body", {}).get("type") or "—"
        lines.extend(_format_widget_entry(w_id, w_type, w))
        lines.append("")

    components = layout.get("components") or []
    if components:
        lines.append("--- Structure (components tree) ---")
        lines.append(_summary_components(components, indent=0))
    return "\n".join(lines).strip()


def _summary_components(components: List[Dict], indent: int) -> str:
    """One-line summary of component tree (type, widgetType, width)."""
    prefix = "  " * indent
    out = []
    for c in components:
        t = c.get("type") or "?"
        if t == "widget":
            w_type = c.get("widgetType", "?")
            w_id = (c.get("widgetId") or "")[:8]
            out.append(f"{prefix}{t}({w_type}, id={w_id}...)")
        elif t == "row":
            out.append(f"{prefix}row")
            for cell in c.get("cells") or []:
                out.append(_summary_components(cell.get("components") or [], indent + 1))
        elif t == "cell":
            width = c.get("width", "")
            out.append(f"{prefix}cell(width={width})")
            out.append(_summary_components(c.get("components") or [], indent + 1))
        else:
            out.append(f"{prefix}{t}")
    return "\n".join(out)


def _format_style_response(style: Dict[str, Any]) -> str:
    """Format style and stylesheets for text output."""
    lines = [
        "=== LumApps style (API) ===",
        f"Style ID: {style.get('id') or style.get('styleId') or '—'}",
        "",
    ]
    sheets = style.get("stylesheets") or []
    if not sheets:
        lines.append("No stylesheets in this style.")
        return "\n".join(lines)
    for i, s in enumerate(sheets):
        kind = s.get("kind") or "—"
        name = s.get("name") or "—"
        url = s.get("url") or ""
        content = (s.get("content") or "").strip()
        if len(content) > MAX_CSS_EXCERPT:
            content = content[:MAX_CSS_EXCERPT] + "\n... (truncated)"
        lines.append(f"--- Stylesheet {i + 1}: kind={kind}, name={name} ---")
        if url:
            lines.append(f"URL: {url}")
        lines.append("Content:")
        lines.append(content or "(empty)")
        lines.append("")
    return "\n".join(lines).strip()


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    content_id = arguments.get("content_id")
    site_id = arguments.get("site_id")
    user_email = arguments.get("user_email")

    if not user_email:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "user_email is required. Provide content_id + user_email to inspect a page layout, or site_id + user_email to inspect the site global CSS.",
                }
            ]
        }

    if content_id:
        logger.info(f"Executing inspect_lumapps_element (layout) content_id={content_id!r}, user_email={user_email!r}")
        try:
            token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
            layout = await lumapps_client.get_content_layout(content_id, token=token)
            text = _format_layout_response(layout)
            return {"content": [{"type": "text", "text": text}]}
        except Exception as e:
            logger.exception("inspect_lumapps_element layout API failed")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Layout inspection failed: {format_api_error(e)}. Check content_id (e.g. homepage content ID) and API credentials.",
                    }
                ]
            }

    if site_id:
        logger.info(f"Executing inspect_lumapps_element (style) site_id={site_id!r}, user_email={user_email!r}")
        try:
            token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
            data = await lumapps_client.get_style_by_instance(site_id, token=token)
            style = data.get("style")
            if not style:
                return {
                    "content": [{"type": "text", "text": f"No style found for site_id={site_id!r}. Check the site/instance ID."}]
                }
            text = _format_style_response(style)
            return {"content": [{"type": "text", "text": text}]}
        except Exception as e:
            logger.exception("inspect_lumapps_element style API failed")
            detail = format_api_error(e)
            hint = " If 400 Bad Request, the style API may not support this instance on this cell; you can still use update_global_css with this site_id to apply CSS."
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Style inspection failed: {detail}.{hint}",
                    }
                ]
            }

    return {
        "content": [
            {
                "type": "text",
                "text": "Provide content_id + user_email to inspect a page layout (widgets, padding, margin, titles), or site_id + user_email to inspect the site global CSS.",
            }
        ]
    }
