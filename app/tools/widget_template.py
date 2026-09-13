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

"""Shared helpers for matching layout widgets to content.template and saving patches."""

from typing import Any, Dict, List, Optional, Tuple

from app.services.lumapps_client import lumapps_client


def deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> None:
    """Merge updates into base in place. Dict values recurse; other values replace."""
    for k, v in updates.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            deep_merge(base[k], v)
        else:
            base[k] = v


def collect_template_widgets(components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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


def index_widget_parents(components: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map widgetId/uuid → parent row/cell index and 12-col width."""
    parents: Dict[str, Dict[str, Any]] = {}
    row_counter = 0

    def walk(
        items: List[Dict[str, Any]],
        row_idx: Optional[int],
        cell_idx: Optional[int],
        width: Any,
    ) -> None:
        nonlocal row_counter
        for c in items or []:
            t = (c.get("type") or "").lower()
            if t == "row":
                r = row_counter
                row_counter += 1
                for i, cell in enumerate(c.get("cells") or []):
                    walk(cell.get("components") or [], r, i, cell.get("width"))
                walk(c.get("components") or [], r, cell_idx, width)
            elif t == "cell":
                walk(c.get("components") or [], row_idx, cell_idx, c.get("width"))
            elif t == "widget":
                for key in ("widgetId", "id", "uuid"):
                    wid = c.get(key)
                    if isinstance(wid, str) and wid.strip():
                        parents[wid] = {"row": row_idx, "cell": cell_idx, "width": width}
            else:
                walk(c.get("components") or [], row_idx, cell_idx, width)
                for i, cell in enumerate(c.get("cells") or []):
                    walk(cell.get("components") or [], row_idx, i, cell.get("width"))

    walk(components, None, None, None)
    return parents


def find_layout_widget(
    layout: Dict[str, Any], widget_id: str
) -> Tuple[Optional[int], Optional[str], Optional[Dict[str, Any]]]:
    """Return (layout_index, widgetType, raw_widget) for widget_id, or (None, None, None)."""
    widgets_layout = layout.get("widgets") or []
    for i, item in enumerate(widgets_layout):
        w = item.get("widget") or item
        if (w.get("widgetId") or w.get("id")) == widget_id:
            w_type = (w.get("widgetType") or w.get("body", {}).get("type") or "").strip()
            return i, w_type or None, w
    return None, None, None


def type_index_for_layout_widget(layout: Dict[str, Any], widget_id: str) -> Tuple[Optional[str], Optional[int]]:
    """Occurrence index of widget_id among layout widgets of the same widgetType."""
    widgets_layout = layout.get("widgets") or []
    idx, w_type, _ = find_layout_widget(layout, widget_id)
    if idx is None or not w_type:
        return None, None
    same_type_indices = [
        i
        for i, item in enumerate(widgets_layout)
        if (item.get("widget") or item).get("widgetType") == w_type
    ]
    try:
        return w_type, same_type_indices.index(idx)
    except ValueError:
        return w_type, 0


def find_template_widget(
    template: Dict[str, Any],
    *,
    widget_id: Optional[str] = None,
    widget_type: Optional[str] = None,
    type_index: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Locate a template widget. Prefer uuid/widgetId match when widget_id is present;
    fall back to widgetType + occurrence index (same order as layout.widgets[]).
    """
    components = (template or {}).get("components") or []
    widgets = collect_template_widgets(components)
    if widget_id:
        for tw in widgets:
            if widget_id in (
                tw.get("uuid"),
                tw.get("widgetId"),
                tw.get("id"),
            ):
                return tw
    if widget_type is not None and type_index is not None:
        by_type = [tw for tw in widgets if (tw.get("widgetType") or "").strip() == widget_type]
        if 0 <= type_index < len(by_type):
            return by_type[type_index]
    return None


def match_template_widget_for_layout_id(
    layout: Dict[str, Any],
    template: Dict[str, Any],
    widget_id: str,
) -> Optional[Dict[str, Any]]:
    """Match a layout widgetId to a content.template widget (uuid first, then type+index)."""
    w_type, type_index = type_index_for_layout_widget(layout, widget_id)
    return find_template_widget(
        template,
        widget_id=widget_id,
        widget_type=w_type,
        type_index=type_index,
    )


def layout_style_updates_to_template(layout_style_updates: Dict[str, Any]) -> Dict[str, Any]:
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


def strip_properties_style(delta: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of delta with properties.style removed (settings writes must not touch style)."""
    if not isinstance(delta, dict):
        return {}
    out = dict(delta)
    props = out.get("properties")
    if isinstance(props, dict):
        props = dict(props)
        props.pop("style", None)
        out["properties"] = props
    return out


def pick_settings_highlights(widget: Dict[str, Any], limit: int = 6) -> Dict[str, Any]:
    """Pick Advanced classes plus a few settings keys for post-save deltas."""
    props = widget.get("properties") if isinstance(widget.get("properties"), dict) else {}
    settings = props.get("settings") if isinstance(props.get("settings"), dict) else {}
    out: Dict[str, Any] = {}
    for key in ("widgetClass", "identifier", "classes", "classNames"):
        if props.get(key) is not None:
            out[key] = props.get(key)
    preferred = (
        "viewMode",
        "display",
        "itemsPerLine",
        "numberOfItemsPerLine",
        "types",
        "contentTypes",
        "maxNumber",
        "count",
        "fields",
        "footer",
        "displayMode",
        "isHighResolution",
    )
    picked = 0
    for key in preferred:
        if key in settings:
            out[f"settings.{key}"] = settings[key]
            picked += 1
            if picked >= limit:
                break
    if picked < limit:
        for key, val in settings.items():
            sk = f"settings.{key}"
            if sk in out:
                continue
            out[sk] = val
            picked += 1
            if picked >= limit:
                break
    return out


async def save_widget_template_patch(
    content_id: str,
    widget_id: str,
    delta: Dict[str, Any],
    token: str,
    layout: Optional[Dict[str, Any]] = None,
    *,
    protect_style: bool = False,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Find widget in layout, match to content.template, deep-merge delta, save_content.
    When protect_style is True, properties.style in delta is discarded.
    Returns (success, message, target_widget_after_merge).
    """
    if layout is None:
        layout = await lumapps_client.get_content_layout(content_id, token=token)

    w_type, type_index = type_index_for_layout_widget(layout, widget_id)
    if not w_type:
        return False, f"Widget {widget_id!r} not found in layout.", None

    content = await lumapps_client.get_content(content_id, token=token)
    template = content.get("template") or {}
    target = find_template_widget(
        template,
        widget_id=widget_id,
        widget_type=w_type,
        type_index=type_index,
    )
    if target is None:
        return (
            False,
            f"Widget type {w_type!r} at index {type_index} not found in content.template.",
            None,
        )

    patch = strip_properties_style(delta) if protect_style else delta
    if patch:
        deep_merge(target, patch)

    await lumapps_client.save_content(token=token, data=content, send_notifications=False)
    return True, "Content saved.", target
