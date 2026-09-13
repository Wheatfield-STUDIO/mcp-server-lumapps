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

"""Update site theme: palette, header (top/mainNav), and slideshow on style.properties."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
from app.tools.api_error_utils import format_api_error, is_permission_denied, PERMISSION_DENIED_MESSAGE
from app.tools.inspect_lumapps_element import find_slideshow_paths
from app.tools.widget_template import deep_merge

logger = logging.getLogger(__name__)

TOOL_NAME = "update_site_theme"

# Slideshow keys from LumApps style/instance JSON blob (Style.properties is untyped in discovery).
# Sandbox acceptance values: height 0, wrapperHeight 0, contentPosition 10 or 15.
SLIDESHOW_FIELD_NAMES = ("height", "wrapperHeight", "contentPosition", "autoplay", "interval")

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Update a LumApps site theme (style.properties): color palette, header (top / mainNav / search), "
        "and slideshow. GET style/get → merge → style/save. Never POSTs a style without id. "
        "colors[] is replaced only when palette.colors is passed; otherwise the existing palette list is kept. "
        "Slideshow fields (discovered on the style/instance JSON blob; typed Style.properties is a string in "
        f"lumsites discovery): {', '.join(SLIDESHOW_FIELD_NAMES)}. "
        "Merged into style.properties.slideshow when that object exists, else instance.properties.slideshow, "
        "else created under style.properties.slideshow. "
        "IMPORTANT: Always run inspect_lumapps_element with site_id first. Before calling this tool, you MUST "
        "present the modification to the user and wait for their explicit 'Yes' or 'Confirm'. Never apply changes silently."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "LumApps site/instance ID."},
            "user_email": {"type": "string", "description": "User email for LumApps API token."},
            "palette": {
                "type": "object",
                "description": "Theme colors: primary, secondary, accent, and optional colors[] (full replace only if passed).",
            },
            "header": {
                "type": "object",
                "description": (
                    "Header/nav: top.theme, top.background / top.backgroundColor, top.font / top.fontColor, "
                    "top.icons / top.iconColor, mainNav.background, mainNav.font, mainNav.icons, search.*"
                ),
            },
            "slideshow": {
                "type": "object",
                "description": (
                    "Slideshow fields on the style/instance properties blob: "
                    "height, wrapperHeight, contentPosition, autoplay, interval. "
                    "Sandbox reference values: height 0, wrapperHeight 0, contentPosition 10 or 15."
                ),
            },
        },
        "required": ["site_id", "user_email"],
    },
}

_HEADER_ALIAS = {
    "background": "backgroundColor",
    "font": "fontColor",
    "icons": "iconColor",
}


def _as_object(raw: Any, name: str) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        data = json.loads(raw) if raw.strip() else {}
    else:
        data = dict(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a JSON object.")
    return data


def _normalize_header_section(section: Any) -> Dict[str, Any]:
    if not isinstance(section, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in section.items():
        out[_HEADER_ALIAS.get(k, k)] = v
    return out


def apply_palette(properties: Dict[str, Any], palette: Dict[str, Any]) -> List[str]:
    """Merge palette into style.properties. colors[] is wiped only when explicitly passed."""
    notes: List[str] = []
    for key in ("primary", "secondary", "accent"):
        if key in palette and palette[key] is not None:
            properties[key] = palette[key]
            notes.append(f"{key}={palette[key]!r}")
    if "colors" in palette:
        if not isinstance(palette["colors"], list):
            raise ValueError("palette.colors must be an array when passed.")
        properties["colors"] = list(palette["colors"])
        notes.append(f"colors replaced ({len(palette['colors'])} entries)")
    return notes


def apply_header(properties: Dict[str, Any], header: Dict[str, Any]) -> List[str]:
    notes: List[str] = []
    mapping = {
        "top": "top",
        "mainNav": "mainNav",
        "search": "search",
    }
    for src, dest in mapping.items():
        if src not in header:
            continue
        section = _normalize_header_section(header.get(src))
        if not section:
            continue
        existing = properties.get(dest)
        if not isinstance(existing, dict):
            existing = {}
            properties[dest] = existing
        deep_merge(existing, section)
        notes.append(f"{dest}={json.dumps(section)}")
    # Flat keys: top.theme, mainNav.background, ...
    for key, val in header.items():
        if key in mapping or not isinstance(key, str):
            continue
        if "." in key:
            dest, sub = key.split(".", 1)
            dest = {"mainnav": "mainNav"}.get(dest, dest)
            if dest not in ("top", "mainNav", "search"):
                continue
            existing = properties.get(dest)
            if not isinstance(existing, dict):
                existing = {}
                properties[dest] = existing
            existing[_HEADER_ALIAS.get(sub, sub)] = val
            notes.append(f"{dest}.{sub}={val!r}")
    return notes


def _resolve_slideshow_target(
    style_props: Dict[str, Any],
    instance_props: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], str, bool]:
    """
    Pick the object to merge slideshow into.
    Returns (target_dict, path, write_instance).
    """
    if isinstance(style_props.get("slideshow"), dict):
        return style_props["slideshow"], "style.properties.slideshow", False
    style_paths = find_slideshow_paths(style_props)
    if any(p == "properties.slideshow" or p.startswith("properties.slideshow.") for p in style_paths):
        style_props.setdefault("slideshow", {})
        if not isinstance(style_props["slideshow"], dict):
            style_props["slideshow"] = {}
        return style_props["slideshow"], "style.properties.slideshow", False
    if isinstance(instance_props, dict) and isinstance(instance_props.get("slideshow"), dict):
        return instance_props["slideshow"], "instance.properties.slideshow", True
    if isinstance(instance_props, dict):
        inst_paths = find_slideshow_paths(instance_props, prefix="instance.properties")
        if inst_paths:
            instance_props.setdefault("slideshow", {})
            if not isinstance(instance_props["slideshow"], dict):
                instance_props["slideshow"] = {}
            return instance_props["slideshow"], "instance.properties.slideshow", True
    style_props.setdefault("slideshow", {})
    if not isinstance(style_props["slideshow"], dict):
        style_props["slideshow"] = {}
    return style_props["slideshow"], "style.properties.slideshow", False


def apply_slideshow(
    style_props: Dict[str, Any],
    instance_props: Optional[Dict[str, Any]],
    slideshow: Dict[str, Any],
) -> Tuple[List[str], bool]:
    allowed = {k: slideshow[k] for k in SLIDESHOW_FIELD_NAMES if k in slideshow}
    extra = {k: v for k, v in slideshow.items() if k not in SLIDESHOW_FIELD_NAMES}
    # Only merge extra keys that already exist on the target (do not invent new payload keys).
    target, path, write_instance = _resolve_slideshow_target(style_props, instance_props)
    merged = dict(allowed)
    for k, v in extra.items():
        if k in target:
            merged[k] = v
    deep_merge(target, merged)
    notes = [f"{path} += {json.dumps(merged)}"]
    return notes, write_instance


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    site_id = arguments.get("site_id")
    user_email = arguments.get("user_email")
    if not site_id:
        raise ValueError("Missing 'site_id' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    try:
        palette = _as_object(arguments.get("palette"), "palette")
        header = _as_object(arguments.get("header"), "header")
        slideshow = _as_object(arguments.get("slideshow"), "slideshow")
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return {"content": [{"type": "text", "text": f"Invalid theme payload: {e}"}]}

    if not palette and not header and not slideshow:
        return {
            "content": [
                {"type": "text", "text": "Provide at least one of: palette, header, slideshow."}
            ]
        }

    logger.info("Executing update_site_theme site_id=%s", site_id)

    try:
        token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
        data = await lumapps_client.get_style_by_instance(site_id, token=token)
    except Exception as e:
        logger.exception("update_site_theme get_style_by_instance failed")
        return {
            "content": [{"type": "text", "text": f"Could not load site style: {format_api_error(e)}."}]
        }

    style = data.get("style")
    if not style:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "This site has no theme. Create the theme in LumApps admin: Design / Theme → save. Then retry.",
                }
            ]
        }
    style_id = style.get("id") or style.get("uid")
    if not style_id:
        return {"content": [{"type": "text", "text": "Style object has no 'id'. Refusing to POST style/save without id."}]}

    style["id"] = style_id
    properties = style.get("properties")
    if not isinstance(properties, dict):
        properties = {}
        style["properties"] = properties

    instance: Optional[Dict[str, Any]] = None
    instance_props: Optional[Dict[str, Any]] = None
    try:
        instance = await lumapps_client.get_instance(site_id, token=token)
        if isinstance(instance, dict) and isinstance(instance.get("properties"), dict):
            instance_props = instance["properties"]
        elif isinstance(instance, dict):
            instance_props = {}
            instance["properties"] = instance_props
    except Exception as e:
        logger.warning("update_site_theme get_instance failed: %s", e)

    notes: List[str] = []
    write_instance = False
    try:
        if palette:
            notes.extend(apply_palette(properties, palette))
        if header:
            notes.extend(apply_header(properties, header))
        if slideshow:
            slide_notes, slide_on_instance = apply_slideshow(properties, instance_props, slideshow)
            notes.extend(slide_notes)
            write_instance = write_instance or slide_on_instance
    except ValueError as e:
        return {"content": [{"type": "text", "text": str(e)}]}

    try:
        await lumapps_client.save_style(style, token=token)
    except Exception as e:
        logger.exception("update_site_theme save_style failed")
        text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"Could not save style: {format_api_error(e)}."
        return {"content": [{"type": "text", "text": text}]}

    if write_instance and isinstance(instance, dict):
        try:
            await lumapps_client.save_instance(instance, token=token)
        except Exception as e:
            logger.exception("update_site_theme save_instance failed")
            text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"Style saved but instance slideshow failed: {format_api_error(e)}."
            return {"content": [{"type": "text", "text": text}]}

    base_url = (settings.SITE_BASE_URL or "").rstrip("/")
    msg = (
        f"Theme updated for site_id={site_id} (style id={style_id}). "
        + "; ".join(notes)
        + f" Verify at: {base_url}. Re-inspect with inspect_lumapps_element (site_id)."
    )
    return {"content": [{"type": "text", "text": msg}]}
