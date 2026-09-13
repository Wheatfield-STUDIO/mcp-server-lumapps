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

"""Inspect a LumApps page layout (widgets, settings, Advanced classes) or site theme via API. No browser."""

import json
import logging
from typing import Any, Dict, List, Optional

from app.tools.api_error_utils import format_api_error
from app.tools.widget_template import (
    collect_template_widgets,
    index_widget_parents,
    match_template_widget_for_layout_id,
)
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client

logger = logging.getLogger(__name__)

TOOL_NAME = "inspect_lumapps_element"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Inspect a LumApps page layout (widgets, settings, Advanced classes, padding) or the site theme "
        "(style.properties palette/header/slideshow, instance.head, stylesheets). "
        "Use content_id + user_email for a page (layout v2 + content.template). "
        "Use site_id + user_email for the site theme. "
        "Widget identities are returned in full (layout widgetId and template uuid) — never truncated. "
        "Pass that complete widgetId to update_widget_settings / update_widget_style. "
        "Set full=true to return complete custom CSS (default false truncates at 8000 chars). "
        "No browser; works via API. Use the result to prepare a safe write "
        "(update_widget_settings, update_widget_style, update_site_theme, update_global_css). "
        "This tool is read-only: no Yes/Confirm is required."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "content_id": {
                "type": "string",
                "description": "LumApps content/page ID. Use with user_email to inspect widgets, settings, Advanced classes, footer, and row/cell parents.",
            },
            "site_id": {
                "type": "string",
                "description": "LumApps site/instance ID. Use with user_email to inspect style.properties, instance.head, and stylesheets.",
            },
            "user_email": {
                "type": "string",
                "description": "User email for LumApps API token (required for both layout and style inspection).",
            },
            "full": {
                "type": "boolean",
                "description": "If true, do not truncate custom CSS (default false, 8000-char excerpt).",
            },
        },
        "required": [],
    },
}

MAX_CSS_EXCERPT = 8000

_ADVANCED_CLASS_KEYS = ("widgetClass", "identifier", "classes", "classNames", "class")


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


def _extract_footer(props: Dict[str, Any], settings: Any) -> Optional[Dict[str, Any]]:
    """Return footer {label, href} from template properties/settings when present."""
    candidates: List[Any] = []
    if isinstance(settings, dict):
        candidates.append(settings.get("footer"))
        candidates.append(settings.get("footerLink"))
    candidates.append(props.get("footer"))
    candidates.append(props.get("footerLink"))
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        label = raw.get("label") or raw.get("title") or raw.get("text") or raw.get("name")
        href = raw.get("href") or raw.get("url") or raw.get("link")
        if label is not None or href is not None:
            return {"label": label, "href": href}
    return None


def _nonempty_id(value: Any) -> Optional[str]:
    """Return a stripped ID string, or None. Never truncates."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _widget_identity_fields(node: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Collect full widgetId / uuid / id from a layout or template node."""
    if not isinstance(node, dict):
        return {}
    out: Dict[str, str] = {}
    widget_id = _nonempty_id(node.get("widgetId"))
    uuid = _nonempty_id(node.get("uuid"))
    extra = _nonempty_id(node.get("id"))
    if widget_id:
        out["widgetId"] = widget_id
    if uuid:
        out["uuid"] = uuid
    if extra and extra not in out.values():
        out["id"] = extra
    return out


def _format_widget_identity_label(
    widget_id: str,
    template_widget: Optional[Dict[str, Any]] = None,
    raw: Optional[Dict[str, Any]] = None,
) -> str:
    """Human/AI label with complete IDs (layout widgetId + template uuid)."""
    parts: List[str] = []
    layout_id = _nonempty_id(widget_id)
    if layout_id and layout_id != "—":
        parts.append(f"widgetId: {layout_id}")
    ids = {**_widget_identity_fields(raw), **_widget_identity_fields(template_widget)}
    uuid = ids.get("uuid")
    if uuid:
        parts.append(f"uuid: {uuid}")
    extra = ids.get("id")
    if extra and extra != layout_id and extra != uuid:
        parts.append(f"id: {extra}")
    if not parts:
        parts.append("widgetId: —")
    return ", ".join(parts)


def _format_widget_entry(
    widget_id: str,
    w_type: str,
    raw: Dict[str, Any],
    template_widget: Optional[Dict[str, Any]] = None,
    parent: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Format a widget from layout.widgets[] plus matched content.template node."""
    lines = [f"  • {w_type!r} ({_format_widget_identity_label(widget_id, template_widget, raw)})"]
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

    props: Dict[str, Any] = {}
    if isinstance(template_widget, dict) and isinstance(template_widget.get("properties"), dict):
        props = template_widget["properties"]
    elif isinstance(raw.get("properties"), dict):
        props = raw["properties"]

    if props.get("style") is not None:
        lines.append(f"      properties.style: {json.dumps(props.get('style'))}")

    settings = props.get("settings")
    if settings is not None:
        lines.append(f"      properties.settings: {json.dumps(settings)}")

    for key in _ADVANCED_CLASS_KEYS:
        if props.get(key) is not None:
            lines.append(f"      properties.{key}: {props.get(key)!r}")

    footer = _extract_footer(props, settings)
    if footer:
        lines.append(f"      footer: {json.dumps(footer)}")

    if parent:
        lines.append(
            f"      parent: row={parent.get('row')} cell={parent.get('cell')} width={parent.get('width')}"
        )
    return lines


def _parent_for_widget(
    widget_id: str,
    parents: Dict[str, Dict[str, Any]],
    template_widget: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if widget_id in parents:
        return parents[widget_id]
    if not template_widget:
        return None
    for key in ("uuid", "widgetId", "id"):
        tid = template_widget.get(key)
        if isinstance(tid, str) and tid in parents:
            return parents[tid]
    return None


def _format_layout_response(
    layout: Dict[str, Any],
    content: Optional[Dict[str, Any]] = None,
) -> str:
    """Format layout API + content.template for human/AI reading."""
    lines = [
        "=== Page layout (API) ===",
        f"Layout ID: {layout.get('id', '—')}",
        f"Revision: {layout.get('revisionNumber', '—')}",
        "",
    ]
    if content:
        lines.insert(3, f"Content ID: {content.get('uid') or content.get('id') or '—'}")
        lines.insert(4, f"Content type: {content.get('type') or content.get('customContentType') or '—'}")

    widgets = layout.get("widgets") or []
    template = (content or {}).get("template") or {}
    layout_parents = index_widget_parents(layout.get("components") or [])
    template_parents = index_widget_parents(template.get("components") or [])
    parents = {**template_parents, **layout_parents}

    if not widgets:
        lines.append("No widgets in this layout.")
        return "\n".join(lines)

    lines.append("--- Widgets (type, id, settings, Advanced, style) ---")
    for item in widgets:
        w = item.get("widget") or item
        w_id = _nonempty_id(w.get("widgetId")) or _nonempty_id(w.get("id")) or "—"
        w_type = w.get("widgetType") or w.get("body", {}).get("type") or "—"
        template_widget = None
        if template:
            template_widget = match_template_widget_for_layout_id(layout, template, w_id)
        parent = _parent_for_widget(w_id, parents, template_widget)
        lines.extend(_format_widget_entry(w_id, w_type, w, template_widget, parent))
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
            ids = _widget_identity_fields(c)
            id_bits = [f"{k}={v}" for k, v in ids.items()]
            if not id_bits:
                id_bits = ["widgetId=—"]
            out.append(f"{prefix}{t}({w_type}, {', '.join(id_bits)})")
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


def find_slideshow_paths(properties: Any, prefix: str = "properties") -> List[str]:
    """Return dotted paths of slideshow-related keys in a properties object."""
    found: List[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                child = f"{path}.{k}"
                kl = str(k).lower()
                if "slideshow" in kl or k in (
                    "height",
                    "wrapperHeight",
                    "wrapper",
                    "contentPosition",
                    "autoplay",
                    "interval",
                ):
                    if "slideshow" in kl or "slideshow" in path.lower():
                        found.append(child)
                walk(v, child)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")

    walk(properties, prefix)
    return found


def _format_theme_properties(props: Any) -> List[str]:
    """Dump style.properties keys used for palette / header / slideshow / footer."""
    lines = ["--- Theme properties (style.properties) ---"]
    if not isinstance(props, dict):
        lines.append(f"(properties is {type(props).__name__}, not an object)")
        return lines

    for key in ("primary", "secondary", "accent", "colors"):
        if key in props:
            lines.append(f"{key}: {json.dumps(props.get(key))}")
    for key in ("top", "mainNav", "search", "footer"):
        if key in props:
            lines.append(f"{key}: {json.dumps(props.get(key))}")

    slideshow_paths = find_slideshow_paths(props)
    if "slideshow" in props:
        lines.append(f"slideshow (style.properties.slideshow): {json.dumps(props.get('slideshow'))}")
    elif slideshow_paths:
        lines.append(f"slideshow-related paths: {', '.join(slideshow_paths)}")
        for path in slideshow_paths:
            parts = path.split(".")[1:]
            node: Any = props
            for p in parts:
                if isinstance(node, dict):
                    node = node.get(p)
                else:
                    node = None
                    break
            lines.append(f"  {path}: {json.dumps(node)}")
    else:
        lines.append(
            "slideshow: (not present on style.properties; inspect instance.properties below. "
            "Typed Style.properties in LumApps discovery is an untyped JSON blob.)"
        )

    extra = [k for k in props.keys() if k not in ("primary", "secondary", "accent", "colors", "top", "mainNav", "search", "footer", "slideshow")]
    if extra:
        extras = {k: props[k] for k in extra}
        lines.append(f"other properties: {json.dumps(extras)}")
    return lines


def _format_style_response(
    style: Dict[str, Any],
    instance: Optional[Dict[str, Any]] = None,
    *,
    full: bool = False,
) -> str:
    """Format style properties, instance head, and stylesheets."""
    lines = [
        "=== LumApps style (API) ===",
        f"Style ID: {style.get('id') or style.get('styleId') or style.get('uid') or '—'}",
        "",
    ]
    lines.extend(_format_theme_properties(style.get("properties")))
    lines.append("")

    if instance:
        lines.append("--- Instance ---")
        lines.append(f"slug: {instance.get('slug') or '—'}")
        lines.append(f"name: {instance.get('name') or '—'}")
        lines.append(f"style: {instance.get('style') or '—'}")
        lines.append(f"head: {instance.get('head') if instance.get('head') is not None else '—'}")
        inst_props = instance.get("properties")
        if inst_props is not None:
            lines.append(f"instance.properties: {json.dumps(inst_props)}")
            inst_paths = find_slideshow_paths(inst_props, prefix="instance.properties")
            if inst_paths:
                lines.append(f"instance slideshow-related paths: {', '.join(inst_paths)}")
        lines.append("")

    sheets = style.get("stylesheets") or []
    if not sheets:
        lines.append("No stylesheets in this style.")
        return "\n".join(lines)
    for i, s in enumerate(sheets):
        kind = s.get("kind") or "—"
        name = s.get("name") or "—"
        url = s.get("url") or ""
        content = (s.get("content") or "").strip()
        if not full and len(content) > MAX_CSS_EXCERPT:
            content = content[:MAX_CSS_EXCERPT] + "\n... (truncated)"
        lines.append(f"--- Stylesheet {i + 1}: kind={kind}, name={name} ---")
        if url:
            lines.append(f"URL: {url}")
        lines.append("Content:")
        lines.append(content or "(empty)")
        lines.append("")
    return "\n".join(lines).strip()


async def _append_widget_block_schemas(
    text: str,
    content: Dict[str, Any],
    layout: Dict[str, Any],
    token: str,
) -> str:
    """Attach get_widget_blocks settings schema for each widgetType on the page."""
    instance = content.get("instance")
    if isinstance(instance, dict):
        site_id = instance.get("uid") or instance.get("id")
    else:
        site_id = instance
    if not site_id:
        return text

    types: List[str] = []
    for item in layout.get("widgets") or []:
        w = item.get("widget") or item
        w_type = (w.get("widgetType") or w.get("body", {}).get("type") or "").strip()
        if w_type and w_type not in types:
            types.append(w_type)
    if not types:
        template_widgets = collect_template_widgets((content.get("template") or {}).get("components") or [])
        for tw in template_widgets:
            w_type = (tw.get("widgetType") or "").strip()
            if w_type and w_type not in types:
                types.append(w_type)

    extra: List[str] = ["", "--- Widget settings schema (get_widget_blocks) ---"]
    for w_type in types:
        try:
            blocks = await lumapps_client.get_widget_blocks(w_type, str(site_id), token=token)
            extra.append(f"widgetType={w_type!r}: {json.dumps(blocks)}")
        except Exception as e:
            extra.append(f"widgetType={w_type!r}: (blocks unavailable: {format_api_error(e)})")
    return text + "\n" + "\n".join(extra)


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    content_id = arguments.get("content_id")
    site_id = arguments.get("site_id")
    user_email = arguments.get("user_email")
    full = bool(arguments.get("full"))

    if not user_email:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "user_email is required. Provide content_id + user_email to inspect a page layout, or site_id + user_email to inspect the site theme.",
                }
            ]
        }

    if content_id:
        logger.info(f"Executing inspect_lumapps_element (layout) content_id={content_id!r}, user_email={user_email!r}")
        try:
            token = await lumapps_auth.get_inspect_token(user_email=user_email)
            layout = await lumapps_client.get_content_layout(content_id, token=token)
            content: Optional[Dict[str, Any]] = None
            try:
                content = await lumapps_client.get_content(content_id, token=token)
            except Exception as e:
                logger.warning("inspect_lumapps_element get_content failed (layout-only fallback): %s", e)
            text = _format_layout_response(layout, content)
            if content:
                try:
                    text = await _append_widget_block_schemas(text, content, layout, token)
                except Exception as e:
                    logger.warning("inspect_lumapps_element get_widget_blocks failed: %s", e)
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
            token = await lumapps_auth.get_inspect_token(user_email=user_email)
            data = await lumapps_client.get_style_by_instance(site_id, token=token)
            style = data.get("style")
            if not style:
                return {
                    "content": [{"type": "text", "text": f"No style found for site_id={site_id!r}. Check the site/instance ID."}]
                }
            instance: Optional[Dict[str, Any]] = None
            try:
                instance = await lumapps_client.get_instance(site_id, token=token)
            except Exception as e:
                logger.warning("inspect_lumapps_element get_instance failed: %s", e)
            text = _format_style_response(style, instance, full=full)
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
                "text": "Provide content_id + user_email to inspect a page layout (widgets, settings, Advanced classes), or site_id + user_email to inspect the site theme.",
            }
        ]
    }
