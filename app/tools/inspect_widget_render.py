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

"""Inspect the post-save widget render (HAR /widgets/{type}/blocks) and list real class names."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from app.services.html_parser import get_localized_value
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
from app.tools.api_error_utils import format_api_error
from app.tools.widget_template import (
    collect_template_widgets,
    find_template_widget,
    normalize_widget_type,
    widget_identity_ids,
    widget_type_of,
    writable_template_id,
)

logger = logging.getLogger(__name__)

TOOL_NAME = "inspect_widget_render"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Inspect the **rendered widget payload** for CSS targeting. "
        "HAR post-save path (not a write): "
        "POST v2/organizations/{org}/widgets/{widgetType}/blocks?siteId=&forceDisplay=true "
        "with body {ownerResourceInfo, widgetComponent}. "
        "The blocks response is a **JSON block tree** (widget.body.type like BlockTitle / BlockGrid, "
        "widget.cssClass when present) — not DOM HTML. Do not invent .lumx-* selectors. "
        "widget.cssClass is the live CSS skin (from properties.class, e.g. .grok-home-news). "
        "properties.widgetClass does not appear in /blocks — other/legacy, not the skin hook. "
        "Use class names listed from (1) widget.cssClass, (2) class attributes in any HTML string "
        "the API or stored html-widget content actually returned. Do not invent .widget--* or .lumx-*. "
        "html widget properties.content is stored HTML from content/get (HAR did not call /blocks for html). "
        "A row is composed by calling /blocks for each cell widget — there is no row endpoint in the HAR. "
        "There is no page-level HTML endpoint in the HAR. get_content_body is extracted article text, "
        "not rendered page HTML; this tool composes per-widget /blocks plus stored html-widget markup. "
        "Call inspect_lumapps_element first for settings / Advanced fields, then this tool for /blocks, "
        "then inspect_front_html (pasted outerHTML) for .lumx-* / title / span, "
        "then update_global_css. If settings.fields marks a key off but items[].order still "
        "includes that same key, this tool flags that settings.fields did not win / still rendered. "
        "Read-only: no Yes/Confirm required."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "content_id": {
                "type": "string",
                "description": "LumApps content/page ID (ownerResourceId). Required.",
            },
            "user_email": {
                "type": "string",
                "description": "User email for LumApps API token.",
            },
            "widget_id": {
                "type": "string",
                "description": "Template uuid (or layoutId via the same map as inspect). One widget.",
            },
            "widget_type": {
                "type": "string",
                "description": "Template widgetType (e.g. title, content-list, featured-image, directory-entry, html).",
            },
            "row_id": {
                "type": "string",
                "description": "Template row uuid (or cell uuid). Composes /blocks for widgets in that row/cell.",
            },
            "language": {
                "type": "string",
                "description": "Language for localized html-widget content. Default en.",
            },
        },
        "required": ["content_id", "user_email"],
    },
}

# HAR ownerResourceInfo.properties keys (page-save /blocks body).
_OWNER_PROP_KEYS = (
    "instance",
    "id",
    "title",
    "mediaThumbnail",
    "thumbnailAltText",
    "type",
    "externalKey",
)

CSS_HOOKS_LEGEND = (
    "CSS skin = properties.class → /blocks widget.cssClass → .{token} "
    "(e.g. grok-home-news → .grok-home-news). "
    "properties.widgetClass (e.g. grok-news, grok-pills) does not appear in /blocks — "
    "other/legacy, not the skin hook. Do not invent .widget--* or .lumx-*."
)
_STORED_HTML_KEYS = ("content", "html", "text", "body")


def _content_id_of(content: Dict[str, Any]) -> Optional[str]:
    for key in ("id", "uid"):
        val = content.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _instance_id_of(content: Dict[str, Any]) -> Optional[str]:
    instance = content.get("instance")
    if isinstance(instance, dict):
        for key in ("uid", "id"):
            val = instance.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return None
    if isinstance(instance, str) and instance.strip():
        return instance.strip()
    return None


def owner_resource_info(content: Dict[str, Any]) -> Dict[str, Any]:
    """HAR /blocks body.ownerResourceInfo. Keys only; values from content/get."""
    content_id = _content_id_of(content)
    instance_id = _instance_id_of(content)
    props: Dict[str, Any] = {}
    for key in _OWNER_PROP_KEYS:
        if key == "instance":
            props[key] = instance_id
        elif key == "id":
            props[key] = content.get("id") or content.get("uid")
        else:
            props[key] = content.get(key)
    return {
        "ownerResourceId": content_id,
        "ownerResourceType": "content",
        "properties": props,
    }


def widget_component_payload(widget: Dict[str, Any]) -> Dict[str, Any]:
    """Template widget as widgetComponent. Drops Angular $$hashKey from the HAR editor payload."""
    payload = json.loads(json.dumps(widget))
    if isinstance(payload, dict):
        payload.pop("$$hashKey", None)
    return payload


def blocks_request_body(content: Dict[str, Any], widget: Dict[str, Any]) -> Dict[str, Any]:
    """Exact HAR /blocks JSON keys: ownerResourceInfo + widgetComponent."""
    return {
        "ownerResourceInfo": owner_resource_info(content),
        "widgetComponent": widget_component_payload(widget),
    }


def looks_like_html(value: Any) -> bool:
    return isinstance(value, str) and "<" in value and ">" in value


def localized_html_string(raw: Any, language: str) -> Optional[str]:
    if looks_like_html(raw):
        return raw
    if isinstance(raw, dict):
        text = get_localized_value(raw, language)
        if looks_like_html(text):
            return text
    return None


def stored_html_from_widget(widget: Dict[str, Any], language: str) -> List[Tuple[str, str]]:
    """HTML already on the template widget (html widget properties.content)."""
    props = widget.get("properties") if isinstance(widget.get("properties"), dict) else {}
    found: List[Tuple[str, str]] = []
    for key in _STORED_HTML_KEYS:
        html = localized_html_string(props.get(key), language)
        if html:
            found.append((f"properties.{key}", html))
    return found


def walk_html_strings(obj: Any, prefix: str = "") -> List[Tuple[str, str]]:
    """Collect HTML-looking strings from a blocks JSON tree (HAR bodies were structured, not HTML)."""
    found: List[Tuple[str, str]] = []
    if looks_like_html(obj):
        found.append((prefix or "value", obj))
        return found
    if isinstance(obj, dict):
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            found.extend(walk_html_strings(val, path))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            path = f"{prefix}[{i}]" if prefix else f"[{i}]"
            found.extend(walk_html_strings(val, path))
    return found


def extract_html_classes_and_tags(html: str) -> Tuple[List[str], List[str]]:
    """Class attributes and tag names from real HTML. Does not invent .lumx-*."""
    soup = BeautifulSoup(html, "html.parser")
    classes: List[str] = []
    seen_c: set = set()
    tags: List[str] = []
    seen_t: set = set()
    for el in soup.find_all(True):
        name = getattr(el, "name", None)
        if isinstance(name, str) and name and name not in seen_t:
            seen_t.add(name)
            tags.append(name)
        raw = el.get("class") if hasattr(el, "get") else None
        tokens: List[str] = []
        if isinstance(raw, str):
            tokens = raw.split()
        elif isinstance(raw, list):
            tokens = [str(x) for x in raw if x]
        for token in tokens:
            token = token.strip()
            if token and token not in seen_c:
                seen_c.add(token)
                classes.append(token)
    return classes, tags


def css_class_from_blocks(blocks: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(blocks, dict):
        return None
    widget = blocks.get("widget") if isinstance(blocks.get("widget"), dict) else {}
    raw = widget.get("cssClass")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def disabled_field_names(fields: Any) -> List[str]:
    """Names marked off in settings.fields (dict false or {enable:false}) or fields[] enable false."""
    names: List[str] = []
    seen: set = set()

    def add(name: Any) -> None:
        if not isinstance(name, str) or not name.strip() or name.strip() in seen:
            return
        seen.add(name.strip())
        names.append(name.strip())

    if isinstance(fields, dict):
        for key, val in fields.items():
            if val is False:
                add(key)
            elif isinstance(val, dict) and val.get("enable") is False:
                add(key)
    elif isinstance(fields, list):
        for item in fields:
            if isinstance(item, dict) and item.get("enable") is False:
                add(item.get("name"))
    return names


def item_orders_from_blocks(blocks: Optional[Dict[str, Any]]) -> List[List[Any]]:
    """items[].order lists from the /blocks JSON. Empty if that key is absent — do not invent."""
    if not isinstance(blocks, dict):
        return []
    widget = blocks.get("widget") if isinstance(blocks.get("widget"), dict) else {}
    body = widget.get("body") if isinstance(widget.get("body"), dict) else {}
    items = body.get("items")
    if not isinstance(items, list):
        return []
    orders: List[List[Any]] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("order"), list):
            orders.append(item["order"])
    return orders


def fields_vs_render_lines(widget: Dict[str, Any], blocks: Optional[Dict[str, Any]]) -> List[str]:
    """Compare settings.fields (off) to /blocks items[].order. Do not map names that are not in order."""
    orders = item_orders_from_blocks(blocks)
    if not orders:
        return []
    first = orders[0]
    same = all(o == first for o in orders)
    lines = [
        "UI composition used blocks.widget.body.items[].order: " + json.dumps(first if same else orders)
    ]
    props = widget.get("properties") if isinstance(widget.get("properties"), dict) else {}
    settings = props.get("settings") if isinstance(props.get("settings"), dict) else {}
    off = disabled_field_names(settings.get("fields"))
    order_tokens = {str(x) for x in first}
    still = [name for name in off if name in order_tokens]
    if still:
        details = ", ".join(f"settings.fields.{n}=false but order includes {n!r}" for n in still)
        lines.append(f"settings.fields did not win / still rendered: {details}.")
    return lines


def find_template_row_or_cell(
    components: List[Dict[str, Any]], node_id: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Find a row or cell by uuid/id already on the node. Does not invent ids."""
    needle = (node_id or "").strip()
    if not needle:
        return None, None
    found_row: Optional[Dict[str, Any]] = None
    found_cell: Optional[Dict[str, Any]] = None

    def matches(node: Dict[str, Any]) -> bool:
        for key in ("uuid", "id"):
            val = node.get(key)
            if isinstance(val, str) and val.strip() == needle:
                return True
        return False

    def walk(items: List[Dict[str, Any]]) -> None:
        nonlocal found_row, found_cell
        for node in items or []:
            if not isinstance(node, dict):
                continue
            kind = (node.get("type") or "").lower()
            if kind == "row" and matches(node) and found_row is None:
                found_row = node
            if kind == "cell" and matches(node) and found_cell is None:
                found_cell = node
            walk(node.get("components") or [])
            for cell in node.get("cells") or []:
                if isinstance(cell, dict):
                    if matches(cell) and found_cell is None:
                        found_cell = cell
                    walk(cell.get("components") or [])

    walk(components)
    if found_row is not None:
        return found_row, "row"
    if found_cell is not None:
        return found_cell, "cell"
    return None, None


def widgets_in_row_or_cell(node: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    if kind == "row":
        return collect_template_widgets([node])
    return collect_template_widgets(node.get("components") or [])


def select_widgets(
    template: Dict[str, Any],
    *,
    widget_id: Optional[str] = None,
    widget_type: Optional[str] = None,
    row_id: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Pick template widgets. Default (no selector) is every widget on the page."""
    components = (template or {}).get("components") or []
    all_widgets = collect_template_widgets(components)
    if widget_id:
        found = find_template_widget(template, widget_id=widget_id)
        if found is None:
            return [], f"widget {widget_id!r} not found in content.template"
        return [found], "widget"
    if widget_type:
        nt = normalize_widget_type(widget_type)
        raw = (widget_type or "").strip().lower()
        matched = [
            w
            for w in all_widgets
            if normalize_widget_type(widget_type_of(w)) == nt
            or (widget_type_of(w) or "").strip().lower() == raw
        ]
        if not matched:
            return [], f"widgetType {widget_type!r} not found in content.template"
        return matched, "widget_type"
    if row_id:
        node, kind = find_template_row_or_cell(components, row_id)
        if node is None or kind is None:
            return [], f"row/cell {row_id!r} not found in content.template"
        widgets = widgets_in_row_or_cell(node, kind)
        if not widgets:
            return [], f"{kind} {row_id!r} has no widgets"
        return widgets, kind
    return all_widgets, "page"


def _blocks_url_type(widget: Dict[str, Any]) -> str:
    """Path segment as stored on the template (HAR: title, featured-image, content-list, directory-entry)."""
    return (widget.get("widgetType") or widget_type_of(widget) or "").strip()


def format_class_index(entries: List[Dict[str, Any]]) -> List[str]:
    """Deduped class names from cssClass + HTML class attributes only."""
    lines = [
        "=== Class names (from this render only) ===",
    ]
    seen: set = set()
    listed = False
    leftover_widget_class: List[str] = []
    leftover_seen: set = set()
    for entry in entries:
        css = entry.get("cssClass")
        if isinstance(css, str) and css.strip() and css.strip() not in seen:
            seen.add(css.strip())
            lines.append(f"- .{css.strip()}  [widget.cssClass ← properties.class]")
            listed = True
        payload = entry.get("payloadClasses") or {}
        raw_wc = payload.get("widgetClass") if isinstance(payload, dict) else None
        if isinstance(raw_wc, str):
            for token in [t.strip() for t in raw_wc.replace(",", " ").split() if t.strip()]:
                if token not in seen and token not in leftover_seen:
                    leftover_seen.add(token)
                    leftover_widget_class.append(token)
        for html_path, html in entry.get("html") or []:
            classes, tags = extract_html_classes_and_tags(html)
            for cls in classes:
                if cls not in seen:
                    seen.add(cls)
                    lines.append(f"- .{cls}  [HTML class in {html_path}]")
                    listed = True
            if tags and not classes:
                lines.append(
                    f"- (no class attributes in {html_path}; tags: {', '.join(tags)})"
                )
                listed = True
    if leftover_widget_class:
        lines.append(
            "widgetClass tokens not in /blocks (other/legacy, not the skin hook): "
            + ", ".join(f".{t}" for t in leftover_widget_class)
        )
        listed = True
    if not listed:
        lines.append(
            "- (none). /blocks returned a JSON block tree, not DOM HTML. "
            "Live CSS skin is properties.class → widget.cssClass when present."
        )
    return lines


def format_widget_render_entry(entry: Dict[str, Any]) -> List[str]:
    lines = [
        f"--- {entry.get('widgetType') or 'widget'} "
        f"uuid={entry.get('uuid') or '—'} ---",
    ]
    if entry.get("error"):
        lines.append(f"blocks error: {entry['error']}")
    else:
        lines.append(
            f"POST v2/organizations/{{org}}/widgets/{entry.get('urlType')}/blocks"
            f"?siteId={{siteId}}&forceDisplay=true"
        )
        css = entry.get("cssClass")
        skin = entry.get("payloadClasses") or {}
        klass = skin.get("class") if isinstance(skin, dict) else None
        if css:
            note = f"  [CSS skin ← properties.class={klass!r}]" if klass else "  [CSS skin]"
            lines.append(f"widget.cssClass: {css}{note}")
        else:
            lines.append("widget.cssClass: (absent)")
        blocks = entry.get("blocks")
        if isinstance(blocks, dict):
            widget = blocks.get("widget") if isinstance(blocks.get("widget"), dict) else {}
            body = widget.get("body")
            lines.append(f"blocks.widget.body: {json.dumps(body)}")
            extra = {
                k: widget.get(k)
                for k in ("widgetId", "widgetType", "isCollapsed")
                if k in widget
            }
            if extra:
                lines.append(f"blocks.widget (ids): {json.dumps(extra)}")
            more = {k: blocks.get(k) for k in ("more", "paginationType") if k in blocks}
            if more:
                lines.append(f"blocks envelope: {json.dumps(more)}")
            template_widget = entry.get("templateWidget") or {}
            lines.extend(fields_vs_render_lines(template_widget, blocks))
    for html_path, html in entry.get("html") or []:
        classes, tags = extract_html_classes_and_tags(html)
        lines.append(f"HTML ({html_path}):")
        lines.append(html)
        lines.append(f"HTML tags: {', '.join(tags) if tags else '(none)'}")
        lines.append(
            "HTML class attributes: "
            + (", ".join(f".{c}" for c in classes) if classes else "(none)")
        )
    if not entry.get("html") and not entry.get("error"):
        lines.append(
            "No HTML string in this /blocks body or stored properties.content. "
            "The render is the JSON block tree above."
        )
    payload = entry.get("payloadClasses") or {}
    if payload:
        klass = payload.get("class")
        wc = payload.get("widgetClass")
        ident = payload.get("identifier")
        bits = []
        if klass is not None:
            bits.append(f"properties.class={klass!r} [CSS skin]")
        if wc is not None:
            bits.append(f"properties.widgetClass={wc!r} [not in /blocks]")
        if ident is not None:
            bits.append(f"properties.identifier={ident!r}")
        if bits:
            lines.append("template payload: " + "; ".join(bits))
    return lines


def _payload_class_fields(widget: Dict[str, Any]) -> Dict[str, Any]:
    props = widget.get("properties") if isinstance(widget.get("properties"), dict) else {}
    out: Dict[str, Any] = {}
    for key in ("class", "widgetClass", "identifier"):
        if props.get(key) is not None:
            out[key] = props[key]
    return out


async def render_one_widget(
    *,
    content: Dict[str, Any],
    widget: Dict[str, Any],
    token: str,
    language: str,
) -> Dict[str, Any]:
    url_type = _blocks_url_type(widget)
    site_id = _instance_id_of(content) or ""
    html = stored_html_from_widget(widget, language)
    entry: Dict[str, Any] = {
        "uuid": writable_template_id(widget),
        "widgetType": widget.get("widgetType") or widget_type_of(widget),
        "urlType": url_type,
        "html": html,
        "payloadClasses": _payload_class_fields(widget),
        "templateWidget": widget,
        "ids": widget_identity_ids(widget),
    }
    if not url_type:
        entry["error"] = "template widget has no widgetType; cannot call /blocks"
        return entry
    if not site_id:
        entry["error"] = "content.instance missing; /blocks requires siteId"
        return entry
    body = blocks_request_body(content, widget)
    try:
        blocks = await lumapps_client.get_widget_blocks(
            widget_type=url_type,
            site_id=site_id,
            token=token,
            body=body,
        )
        entry["blocks"] = blocks
        entry["requestKeys"] = list(body.keys())
        entry["cssClass"] = css_class_from_blocks(blocks)
        html.extend(walk_html_strings(blocks, "blocks"))
        # de-dupe html paths
        seen = set()
        unique: List[Tuple[str, str]] = []
        for path, snippet in html:
            key = (path, snippet)
            if key not in seen:
                seen.add(key)
                unique.append((path, snippet))
        entry["html"] = unique
    except Exception as exc:
        logger.warning("inspect_widget_render /blocks failed type=%s: %s", url_type, exc)
        entry["error"] = format_api_error(exc)
    return entry


def format_render_report(
    *,
    content_id: str,
    scope: str,
    entries: List[Dict[str, Any]],
) -> str:
    lines = [
        "=== LumApps widget render (HAR /widgets/{type}/blocks) ===",
        f"content_id: {content_id}",
        f"scope: {scope}",
        "This is the post-save render, not content/save. "
        "Response is a JSON block tree unless a field is actual HTML.",
        "No page HTML endpoint was in the HAR. "
        "get_content_body extracts article text from the template; it is not this render.",
        CSS_HOOKS_LEGEND,
        "",
    ]
    lines.extend(format_class_index(entries))
    lines.append("")
    if not entries:
        lines.append("No widgets selected.")
        return "\n".join(lines).strip()
    for entry in entries:
        lines.extend(format_widget_render_entry(entry))
        lines.append("")
    return "\n".join(lines).strip()


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    content_id = (arguments.get("content_id") or "").strip() if isinstance(arguments.get("content_id"), str) else ""
    user_email = (arguments.get("user_email") or "").strip() if isinstance(arguments.get("user_email"), str) else ""
    widget_id = (arguments.get("widget_id") or "").strip() if isinstance(arguments.get("widget_id"), str) else ""
    widget_type = (arguments.get("widget_type") or "").strip() if isinstance(arguments.get("widget_type"), str) else ""
    row_id = (arguments.get("row_id") or "").strip() if isinstance(arguments.get("row_id"), str) else ""
    language = (arguments.get("language") or "en").strip() or "en"

    if not user_email:
        return {
            "content": [
                {"type": "text", "text": "user_email is required."}
            ]
        }
    if not content_id:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "content_id is required. Provide the page id (ownerResourceId) plus "
                    "widget_id / widget_type for one widget, row_id for a row, or neither for the whole page.",
                }
            ]
        }

    logger.info(
        "Executing inspect_widget_render content_id=%r widget_id=%r widget_type=%r row_id=%r",
        content_id,
        widget_id or None,
        widget_type or None,
        row_id or None,
    )
    try:
        token = await lumapps_auth.get_inspect_token(user_email=user_email)
        content = await lumapps_client.get_content(content_id, token=token)
        template = content.get("template") if isinstance(content.get("template"), dict) else {}
        widgets, scope = select_widgets(
            template,
            widget_id=widget_id or None,
            widget_type=widget_type or None,
            row_id=row_id or None,
        )
        if not widgets:
            return {"content": [{"type": "text", "text": scope}]}
        entries: List[Dict[str, Any]] = []
        for widget in widgets:
            entries.append(
                await render_one_widget(
                    content=content,
                    widget=widget,
                    token=token,
                    language=language,
                )
            )
        text = format_render_report(
            content_id=_content_id_of(content) or content_id,
            scope=scope,
            entries=entries,
        )
        return {"content": [{"type": "text", "text": text}]}
    except Exception as exc:
        logger.exception("inspect_widget_render failed")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Widget render inspection failed: {format_api_error(exc)}. "
                    "Check content_id and that ownerResourceInfo can be built from content/get.",
                }
            ]
        }
