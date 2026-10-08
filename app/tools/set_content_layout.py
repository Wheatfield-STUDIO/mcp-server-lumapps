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

"""Place native content-list widgets into content.template. Not an HTML widget."""

import json
import logging
import uuid
from typing import Any, Dict, List

from app.services.lumapps_auth import lumapps_auth
from app.tools.api_error_utils import format_api_error, is_permission_denied, PERMISSION_DENIED_MESSAGE
from app.tools.widget_template import collect_template_widgets, save_content_template_components

logger = logging.getLogger(__name__)

TOOL_NAME = "set_content_layout"

# Proven on content-list template widgets. Do not invent settings.fields / itemsPerLine / contentTypes.
ALLOWED_PROPERTY_KEYS = (
    "viewMode",
    "perLine",
    "thumbnailPosition",
    "uncompressedThumbnail",
    "customContentType",
    "fields",
    "type",
    "listOrder",
    "listOrderDir",
    "truncate",
    "fullExcerpt",
    "class",
    "style",
)
FORBIDDEN_PROPERTY_KEYS = (
    "settings",
    "itemsPerLine",
    "numberOfItemsPerLine",
    "contentTypes",
    "widgetClass",
    "identifier",
)
FIELD_NAMES = (
    "title",
    "excerpt",
    "author",
    "publication-date",
    "tags",
    "metadata",
    "social",
)
LIST_TYPES = ("pick", "list")
_NODE_TYPE_KEYS = frozenset(
    {"type", "widgetType", "properties", "uuid", "widgetId", "id", "cells", "components", "widgets", "width"}
)

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Write a native LumApps **content-list** grid into `content.template` of an **existing** page. "
        "Does **not** use an HTML widget or `save_content_page` body_widgets (html/title only). "
        "`update_widget_style` / `update_widget_settings` cannot create a missing widget — this tool places them. "
        "mode=update: GET content/get, then one content/save of content.template using the "
        "version / lastRevision just read (so the save is not stale / CONTENT_NOT_UP_TO_DATE). "
        "status defaults to LIVE — useful edits publish in this same save, not a follow-up save_content_page. "
        "rows[] → cells (width) → content-list widgets. Allowed properties only: "
        "viewMode, perLine, thumbnailPosition, uncompressedThumbnail, customContentType (ids), "
        "fields as [{enable, name}] (title, excerpt, author, publication-date, tags, metadata, social), "
        "type (pick|list), listOrder, listOrderDir, truncate, fullExcerpt, class, style. "
        "Do **not** invent settings.fields, itemsPerLine, numberOfItemsPerLine, contentTypes, or HTML text. "
        "Skin is properties.class → .widget--{class}. Style is properties.style, not global CSS. "
        "IMPORTANT: Always run inspect_lumapps_element first. Before calling, you MUST present the layout "
        "to the user and wait for explicit 'Yes' or 'Confirm'. Never apply changes silently."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "content_id": {
                "type": "string",
                "description": "Existing page id. Template components are replaced with the new row tree.",
            },
            "user_email": {
                "type": "string",
                "description": "User email for LumApps API token.",
            },
            "mode": {
                "type": "string",
                "description": "Must be update (existing page). Create is refused.",
            },
            "status": {
                "type": "string",
                "description": (
                    "LIVE (default) or DRAFT. Useful layout edits publish LIVE in this same "
                    "content/save — not a separate DRAFT and not a follow-up save_content_page."
                ),
            },
            "rows": {
                "type": "array",
                "description": (
                    "Row tree. Each row is {cells:[{width, widgets:[content-list, ...]}]} "
                    "or shorthand {width, widgets:[...]}. "
                    "Same-row widgets share one cell. Example Home 2026-Copy: "
                    "row0 cell12 = pick/cover top-news-homepage + list/horizontal perLine 3 other-news-homepage; "
                    "row1 cell12 = list/horizontal perLine 2 announcements-homepage."
                ),
            },
        },
        "required": ["content_id", "user_email", "mode", "rows"],
    },
}


def _new_id() -> str:
    return str(uuid.uuid4())


def _parse_rows(raw: Any) -> List[Any]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list) or not raw:
        raise ValueError("rows must be a non-empty array.")
    return raw


def _as_id_list(value: Any) -> List[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                out.append(text)
        return out
    raise ValueError("customContentType must be an id or a list of ids.")


def _normalize_fields(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("fields must be a non-empty array of {enable, name}.")
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each fields[] item must be {enable, name}.")
        name = item.get("name")
        if not isinstance(name, str) or name.strip() not in FIELD_NAMES:
            raise ValueError(
                f"fields[].name must be one of {', '.join(FIELD_NAMES)} (got {name!r})."
            )
        if "enable" not in item:
            raise ValueError("fields[] items need enable and name.")
        extra = [k for k in item.keys() if k not in ("enable", "name")]
        if extra:
            raise ValueError(f"fields[] only allows enable and name (got {extra}).")
        out.append({"enable": bool(item.get("enable")), "name": name.strip()})
    return out


def sanitize_content_list_properties(raw: Any) -> Dict[str, Any]:
    """Keep the proven content-list bag only. Reject invented settings / HTML keys."""
    if not isinstance(raw, dict):
        raise ValueError("content-list properties must be an object.")
    forbidden = [k for k in FORBIDDEN_PROPERTY_KEYS if k in raw]
    if forbidden:
        raise ValueError(
            "Do not invent "
            + ", ".join(forbidden)
            + ". Use properties.fields[] / customContentType / perLine."
        )
    unknown = [k for k in raw.keys() if k not in ALLOWED_PROPERTY_KEYS]
    if unknown:
        raise ValueError(
            "Unknown content-list properties "
            + ", ".join(unknown)
            + f". Allowed: {', '.join(ALLOWED_PROPERTY_KEYS)}."
        )
    props: Dict[str, Any] = {}
    if "viewMode" in raw:
        if not isinstance(raw["viewMode"], str) or not raw["viewMode"].strip():
            raise ValueError("viewMode must be a string (e.g. cover, horizontal).")
        props["viewMode"] = raw["viewMode"].strip()
    if "perLine" in raw:
        try:
            props["perLine"] = int(raw["perLine"])
        except (TypeError, ValueError) as exc:
            raise ValueError("perLine must be an integer (properties.perLine).") from exc
    if "thumbnailPosition" in raw:
        if not isinstance(raw["thumbnailPosition"], str) or not raw["thumbnailPosition"].strip():
            raise ValueError("thumbnailPosition must be a string (e.g. inline, background).")
        props["thumbnailPosition"] = raw["thumbnailPosition"].strip()
    if "uncompressedThumbnail" in raw:
        props["uncompressedThumbnail"] = bool(raw["uncompressedThumbnail"])
    if "customContentType" in raw:
        props["customContentType"] = _as_id_list(raw["customContentType"])
    if "fields" in raw:
        props["fields"] = _normalize_fields(raw["fields"])
    if "type" in raw:
        kind = str(raw["type"]).strip().lower()
        if kind not in LIST_TYPES:
            raise ValueError("properties.type must be pick or list.")
        props["type"] = kind
    if "listOrder" in raw:
        props["listOrder"] = raw["listOrder"]
    if "listOrderDir" in raw:
        props["listOrderDir"] = raw["listOrderDir"]
    if "truncate" in raw:
        props["truncate"] = raw["truncate"]
    if "fullExcerpt" in raw:
        props["fullExcerpt"] = raw["fullExcerpt"]
    if "class" in raw:
        if not isinstance(raw["class"], str) or not raw["class"].strip():
            raise ValueError("class must be a single token (e.g. top-news-homepage).")
        props["class"] = raw["class"].strip().split()[0]
    if "style" in raw:
        if not isinstance(raw["style"], dict):
            raise ValueError("style must be an object (properties.style).")
        props["style"] = raw["style"]
    return props


def _properties_from_widget(raw: Dict[str, Any]) -> Dict[str, Any]:
    wtype = (raw.get("widgetType") or "").strip().lower()
    node_type = (raw.get("type") or "").strip().lower()
    if wtype in ("html", "title") or node_type in ("html", "title"):
        raise ValueError(
            "set_content_layout only places native content-list widgets. "
            "Do not pass html or title (that is save_content_page body_widgets)."
        )
    if isinstance(raw.get("properties"), dict):
        if wtype and wtype != "content-list":
            raise ValueError(f"widgetType must be content-list (got {wtype!r}).")
        if node_type and node_type not in ("widget", "content-list"):
            raise ValueError(f"type must be content-list or pick/list (got {node_type!r}).")
        return sanitize_content_list_properties(raw["properties"])
    if node_type in ("content-list", "widget") or wtype == "content-list":
        bag = {k: v for k, v in raw.items() if k not in _NODE_TYPE_KEYS}
        return sanitize_content_list_properties(bag)
    if node_type in LIST_TYPES or not node_type:
        return sanitize_content_list_properties(raw)
    raise ValueError(
        "Each widget must be a content-list properties bag "
        "(type pick|list is properties.type, not an HTML widget)."
    )


def _widgets_from_cell(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    widgets = raw.get("widgets") or raw.get("components")
    if not isinstance(widgets, list) or not widgets:
        raise ValueError("Each cell needs a non-empty widgets array of content-list objects.")
    nodes: List[Dict[str, Any]] = []
    for item in widgets:
        if not isinstance(item, dict):
            raise ValueError("Each widget must be an object.")
        props = _properties_from_widget(item)
        nodes.append(
            {
                "type": "widget",
                "widgetType": "content-list",
                "uuid": _new_id(),
                "properties": props,
            }
        )
    return nodes


def _cells_from_row(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(raw.get("cells"), list) and raw["cells"]:
        sources = raw["cells"]
    elif raw.get("widgets") or raw.get("components"):
        sources = [raw]
    else:
        raise ValueError("Each row needs cells[] or width + widgets[].")
    cells: List[Dict[str, Any]] = []
    for cell in sources:
        if not isinstance(cell, dict):
            raise ValueError("Each cell must be an object.")
        width = cell.get("width", 12)
        try:
            width_n = int(width)
        except (TypeError, ValueError) as exc:
            raise ValueError("cell width must be an integer (12-col).") from exc
        cells.append(
            {
                "type": "cell",
                "uuid": _new_id(),
                "width": width_n,
                "components": _widgets_from_cell(cell),
            }
        )
    return cells


def build_template_components(rows: Any) -> List[Dict[str, Any]]:
    """Build content.template.components from rows[] — content-list only."""
    parsed = _parse_rows(rows)
    components: List[Dict[str, Any]] = []
    for row in parsed:
        if not isinstance(row, dict):
            raise ValueError("Each row must be an object.")
        components.append(
            {
                "type": "row",
                "uuid": _new_id(),
                "cells": _cells_from_row(row),
            }
        )
    if not collect_template_widgets(components):
        raise ValueError("rows produced no content-list widgets.")
    return components


_STATUS_MAP = {
    "draft": "DRAFT",
    "live": "LIVE",
    "DRAFT": "DRAFT",
    "LIVE": "LIVE",
}


def normalize_status(raw: Any) -> str:
    """Default LIVE. Useful edits publish in the same save."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return "LIVE"
    if not isinstance(raw, str):
        raise ValueError("status must be LIVE or DRAFT.")
    mapped = _STATUS_MAP.get(raw.strip()) or _STATUS_MAP.get(raw.strip().lower())
    if not mapped:
        raise ValueError("status must be LIVE or DRAFT.")
    return mapped


def _version_of(content: Dict[str, Any]) -> Any:
    """Prefer content.version, then lastRevision (scalar or {version}). Do not invent keys."""
    if not isinstance(content, dict):
        return None
    if content.get("version") is not None:
        return content.get("version")
    last = content.get("lastRevision")
    if isinstance(last, dict) and last.get("version") is not None:
        return last.get("version")
    if last is not None:
        return last
    return None


def _content_id_of(content: Dict[str, Any], fallback: str) -> str:
    for key in ("uid", "id"):
        val = content.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return fallback


def format_layout_result(
    *,
    content_id: str,
    saved: Dict[str, Any],
    components: List[Dict[str, Any]],
) -> str:
    uid = _content_id_of(saved, content_id)
    version = _version_of(saved)
    status = saved.get("status") or "—"
    widgets = collect_template_widgets((saved.get("template") or {}).get("components") or components)
    last_rev = saved.get("lastRevision") if isinstance(saved, dict) else None
    last_bit = f" lastRevision={last_rev}" if last_rev is not None else ""
    lines = [
        f"Content layout updated. content_id={uid} version={version if version is not None else '—'} "
        f"status={status}{last_bit}",
        "Native content-list widgets (not HTML):",
    ]
    for widget in widgets:
        props = widget.get("properties") if isinstance(widget.get("properties"), dict) else {}
        wid = (widget.get("uuid") or widget.get("widgetId") or widget.get("id") or "—")
        klass = props.get("class") or "—"
        view = props.get("viewMode")
        per_line = props.get("perLine")
        bits = [f"uuid={wid}", "widgetType=content-list", f"class={klass}"]
        if view is not None:
            bits.append(f"viewMode={view}")
        if per_line is not None:
            bits.append(f"perLine={per_line}")
        if props.get("type"):
            bits.append(f"type={props['type']}")
        lines.append("- " + " ".join(bits))
        lines.append(f"  skin: .{klass} → .widget--{klass}" if klass != "—" else "  (no class)")
    lines.append("Re-inspect with inspect_lumapps_element to confirm the three (or listed) widgets.")
    return "\n".join(lines)


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    content_id = (arguments.get("content_id") or "").strip() if isinstance(arguments.get("content_id"), str) else ""
    user_email = (arguments.get("user_email") or "").strip() if isinstance(arguments.get("user_email"), str) else ""
    mode = (arguments.get("mode") or "").strip().lower() if isinstance(arguments.get("mode"), str) else ""

    if not content_id or not user_email:
        return {"content": [{"type": "text", "text": "content_id and user_email are required."}]}
    if mode != "update":
        return {
            "content": [
                {
                    "type": "text",
                    "text": "mode must be update (existing page). set_content_layout does not create pages.",
                }
            ]
        }

    try:
        status = normalize_status(arguments.get("status"))
        components = build_template_components(arguments.get("rows"))
    except json.JSONDecodeError as exc:
        return {"content": [{"type": "text", "text": f"Invalid rows JSON: {exc}"}]}
    except ValueError as exc:
        return {"content": [{"type": "text", "text": str(exc)}]}

    logger.info(
        "Executing set_content_layout content_id=%r widgets=%s",
        content_id,
        len(collect_template_widgets(components)),
    )

    try:
        token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
    except Exception as exc:
        logger.exception("set_content_layout get_token failed")
        text = (
            PERMISSION_DENIED_MESSAGE
            if is_permission_denied(exc)
            else f"Failed to get admin token: {format_api_error(exc)}"
        )
        return {"content": [{"type": "text", "text": text}]}

    try:
        saved, _sent = await save_content_template_components(
            content_id, components, token, status=status
        )
    except Exception as exc:
        logger.exception("set_content_layout save failed")
        text = (
            PERMISSION_DENIED_MESSAGE
            if is_permission_denied(exc)
            else f"Save failed: {format_api_error(exc)}"
        )
        return {"content": [{"type": "text", "text": text}]}

    return {
        "content": [
            {
                "type": "text",
                "text": format_layout_result(content_id=content_id, saved=saved, components=components),
            }
        ]
    }
