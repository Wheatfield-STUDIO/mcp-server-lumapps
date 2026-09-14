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
from typing import Any, Dict, List, Optional, Tuple

from app.tools.api_error_utils import format_api_error
from app.tools.widget_template import (
    index_widget_parents,
    normalize_widget_type,
    pair_layout_and_template,
    widget_identity_ids,
    widget_type_of,
    writable_template_id,
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
        "One line per widget. 'use this id for writes' is the content.template uuid "
        "(layoutId is also accepted via map). "
        "live CSS is unknown: repo resources do not map Advanced 'Widget classes' to "
        "properties.class vs properties.widgetClass, nor to .widget-- "
        "(lumapps-css-variables only documents product BEM .widget--has-ungrouped-container-block). "
        "cover / thumbnail-in-background / footer link only on content-list (or unset); "
        "footer link also on directory when that field exists. "
        "Empty properties.style is omitted unless verbose=true. "
        "Set full=true for complete custom CSS. Set verbose=true for both component trees "
        "and empty style dumps. "
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
            "verbose": {
                "type": "boolean",
                "description": "If true, print both layout.components and content.template.components trees, and dump empty properties.style. Default: one tree (template if present, else layout); skip empty style.",
            },
        },
        "required": [],
    },
}

MAX_CSS_EXCERPT = 8000

_ADVANCED_CLASS_KEYS = ("class", "widgetClass", "identifier", "classes", "classNames")
_ADVANCED_FIELD_NOTES = {
    "class": "payload field; Advanced UI mapping unknown — not proven as .widget-- hook",
    "widgetClass": "this server treats as Advanced classes; UI \"Widget classes\" mapping unconfirmed",
    "identifier": "Advanced identifier",
    "classes": "extra classes",
    "classNames": "classNames",
}


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


def _linked_directory_id(props: Dict[str, Any], settings: Any) -> Optional[str]:
    """Directory widget's linked directory uid (e.g. 8821612211991448)."""
    bags: List[Dict[str, Any]] = []
    if isinstance(settings, dict):
        bags.append(settings)
    if isinstance(props, dict):
        bags.append(props)
    for bag in bags:
        for key in ("directory", "directoryId", "directoryUid", "directory_id", "directoryUID"):
            val = bag.get(key)
            if isinstance(val, dict):
                val = val.get("uid") or val.get("id") or val.get("directory")
            if val is not None and str(val).strip():
                return str(val).strip()
    return None


def _fmt_or_unset(value: Any) -> str:
    if value is None:
        return "unset"
    if isinstance(value, str) and not value.strip():
        return "unset"
    return json.dumps(value)


def _cover_value(props: Dict[str, Any], settings: Any) -> Any:
    bag = settings if isinstance(settings, dict) else {}
    props = props if isinstance(props, dict) else {}
    for src in (bag, props):
        for key in ("cover", "coverImage"):
            if src.get(key) is not None:
                return src.get(key)
    return None


def _thumbnail_in_background_value(props: Dict[str, Any], settings: Any) -> Any:
    bag = settings if isinstance(settings, dict) else {}
    props = props if isinstance(props, dict) else {}
    for src in (bag, props):
        for key in ("thumbnailBackground", "thumbnail", "backgroundImage"):
            if src.get(key) is not None:
                return src.get(key)
    return None


def _nonempty_class_token(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, str) and not str(value).strip()):
        return None
    return str(value).strip()


def _widget_live_css(props: Dict[str, Any]) -> Optional[str]:
    """
    Do not invent a .widget-- hook. Repo evidence:
    - lumapps-css-variables.md only shows product BEM .widget--has-ungrouped-container-block
    - lumapps-customizations-api.md targets widgets as widget-<id> or widget-<identifier>
    - this server historically listed properties.widgetClass as Advanced classes
    - /bot payloads also have properties.class
    Advanced tab "Widget classes" → which field, and whether the front prefixes .widget--,
    is not documented. Say unknown.
    """
    props = props if isinstance(props, dict) else {}
    klass = _nonempty_class_token(props.get("class"))
    wclass = _nonempty_class_token(props.get("widgetClass"))
    if not klass and not wclass:
        return None
    bits = []
    if klass:
        bits.append(f"class={klass}")
    if wclass:
        bits.append(f"widgetClass={wclass}")
    return (
        "live CSS: unknown — Advanced \"Widget classes\" → class vs widgetClass "
        "is not in repo resources; .widget-- is only documented as product BEM "
        f"(.widget--has-ungrouped-container-block). {'; '.join(bits)} "
        "— do not assume .widget--{class} or .widget--{widgetClass}"
    )


def _is_empty_style(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, dict):
        return all(_is_empty_style(v) for v in value.values()) if value else True
    if isinstance(value, list):
        return all(_is_empty_style(v) for v in value) if value else True
    return False


def _visual_lines(w_type: str, props: Dict[str, Any], settings: Any) -> List[str]:
    """Cover / thumbnail / footer only on content-list. Footer also on directory when present."""
    nt = normalize_widget_type(w_type)
    footer = _extract_footer(props, settings)
    if nt == "content-list":
        return [
            f"      cover: {_fmt_or_unset(_cover_value(props, settings))}",
            f"      thumbnail-in-background: {_fmt_or_unset(_thumbnail_in_background_value(props, settings))}",
            f"      footer link: {_fmt_or_unset(footer)}",
        ]
    if "directory" in nt and footer is not None:
        return [f"      footer link: {_fmt_or_unset(footer)}"]
    return []


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
    layers = [node]
    nested = node.get("widget")
    if isinstance(nested, dict):
        layers.append(nested)
    out: Dict[str, str] = {}
    for layer in layers:
        widget_id = _nonempty_id(layer.get("widgetId"))
        uuid = _nonempty_id(layer.get("uuid"))
        extra = _nonempty_id(layer.get("id"))
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
    """One label: writable template uuid first; layoutId is mapped, not a second widget."""
    write_id = writable_template_id(template_widget)
    layout_ids = [i for i in widget_identity_ids(raw) if i != write_id]
    if write_id:
        parts = [f"use this id for writes: {write_id}"]
        if layout_ids:
            parts.append(f"layoutId: {layout_ids[0]} (also accepted via map)")
        return ", ".join(parts)
    fallback = layout_ids[0] if layout_ids else (_nonempty_id(widget_id) or "—")
    return f"layout-only / readOnly id: {fallback} — not writable via update_widget_settings"


def _format_widget_entry(
    widget_id: str,
    w_type: str,
    raw: Dict[str, Any],
    template_widget: Optional[Dict[str, Any]] = None,
    parent: Optional[Dict[str, Any]] = None,
    *,
    verbose: bool = False,
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

    prop_style = props.get("style")
    if prop_style is not None and (verbose or not _is_empty_style(prop_style)):
        lines.append(f"      properties.style: {json.dumps(prop_style)}")

    settings = props.get("settings")
    if settings is not None:
        lines.append(f"      properties.settings: {json.dumps(settings)}")

    for key in _ADVANCED_CLASS_KEYS:
        if props.get(key) is not None:
            note = _ADVANCED_FIELD_NOTES.get(key, "")
            suffix = f"  [{note}]" if note else ""
            lines.append(f"      properties.{key}: {props.get(key)!r}{suffix}")

    live_css = _widget_live_css(props)
    if live_css:
        lines.append(f"      {live_css}")
    lines.extend(_visual_lines(w_type, props, settings))

    w_type_norm = (w_type or "").strip().lower()
    if "directory" in w_type_norm:
        dir_id = _linked_directory_id(props, settings)
        if dir_id:
            lines.append(f"      linked directory id: {dir_id}")
        else:
            lines.append("      linked directory id: unset")

    if parent:
        bits = [
            f"row={parent.get('row')}",
            f"cell={parent.get('cell')}",
            f"width={parent.get('width')}",
        ]
        if parent.get("rowId"):
            bits.append(f"rowId={parent['rowId']}")
        if parent.get("cellId"):
            bits.append(f"cellId={parent['cellId']}")
        lines.append(f"      parent: {' '.join(bits)}")
    return lines


def _parent_for_widget(
    widget_id: str,
    parents: Dict[str, Dict[str, Any]],
    template_widget: Optional[Dict[str, Any]],
    raw: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    for node in (raw, template_widget):
        for tid in widget_identity_ids(node):
            if tid in parents:
                return parents[tid]
    if widget_id in parents:
        return parents[widget_id]
    return None


def _collect_page_widgets(
    layout: Dict[str, Any],
    content: Optional[Dict[str, Any]],
) -> List[Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]]:
    """One pair per logical widget (template uuid is the write id)."""
    template = (content or {}).get("template") or {}
    return pair_layout_and_template(layout, template)


def _format_layout_response(
    layout: Dict[str, Any],
    content: Optional[Dict[str, Any]] = None,
    *,
    verbose: bool = False,
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

    template = (content or {}).get("template") or {}
    layout_parents = index_widget_parents(layout.get("components") or [])
    template_parents = index_widget_parents(template.get("components") or [])
    parents = {**template_parents, **layout_parents}

    page_widgets = _collect_page_widgets(layout, content)
    if not page_widgets:
        lines.append("No widgets in this layout or content.template.")
        return "\n".join(lines)

    lines.append(
        "--- Widgets (one line per widget; use this id for writes = template uuid) ---"
    )
    for raw, template_widget in page_widgets:
        node = template_widget or raw or {}
        write_id = writable_template_id(template_widget)
        ids = widget_identity_ids(template_widget) or widget_identity_ids(raw)
        w_id = write_id or (ids[0] if ids else "—")
        w_type = widget_type_of(node) or "—"
        parent = _parent_for_widget(w_id, parents, template_widget, raw)
        lines.extend(
            _format_widget_entry(w_id, w_type, raw or {}, template_widget, parent, verbose=verbose)
        )
        lines.append("")

    layout_components = layout.get("components") or []
    template_components = template.get("components") or []
    if verbose:
        if layout_components:
            lines.append("--- Structure (layout.components, full IDs) ---")
            lines.append(_summary_components(layout_components, indent=0))
        if template_components:
            lines.append("")
            lines.append("--- Structure (content.template.components, full IDs) ---")
            lines.append(_summary_components(template_components, indent=0))
    elif template_components:
        lines.append("--- Structure (content.template.components, full IDs) ---")
        lines.append(_summary_components(template_components, indent=0))
    elif layout_components:
        lines.append("--- Structure (layout.components, full IDs) ---")
        lines.append(_summary_components(layout_components, indent=0))
    return "\n".join(lines).strip()


def _summary_components(components: List[Dict], indent: int) -> str:
    """One-line summary of component tree (type, widgetType, width)."""
    prefix = "  " * indent
    out = []
    for c in components:
        t = c.get("type") or "?"
        if t == "widget":
            inner = c.get("widget") if isinstance(c.get("widget"), dict) else {}
            w_type = c.get("widgetType") or inner.get("widgetType") or "?"
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


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    content_id = arguments.get("content_id")
    site_id = arguments.get("site_id")
    user_email = arguments.get("user_email")
    full = bool(arguments.get("full"))
    verbose = bool(arguments.get("verbose"))

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
            text = _format_layout_response(layout, content, verbose=verbose)
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
