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

"""Update site theme: palette/nav on style.properties; slideshow on header/save (HAR)."""

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
from app.tools.api_error_utils import format_api_error, is_permission_denied, PERMISSION_DENIED_MESSAGE
from app.tools.widget_template import deep_merge

logger = logging.getLogger(__name__)

TOOL_NAME = "update_site_theme"

# HAR POST header/save (save-style.har): height, properties.wrapperHeight,
# properties.layoutPosition, properties.interval. contentPosition is accepted as
# an alias for layoutPosition (user 0/0/10 == HAR layoutPosition 10).
SLIDESHOW_FIELD_NAMES = ("height", "wrapperHeight", "layoutPosition", "contentPosition", "interval")

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Update a LumApps site theme: palette/nav via style/get → style/save; "
        "slideshow via header/get → header/save (HAR save-style.har). "
        "Never POSTs a style without id. colors[] is replaced only when palette.colors is passed. "
        "Slideshow HAR keys: header.height, header.properties.wrapperHeight, "
        "header.properties.layoutPosition, header.properties.interval. "
        "contentPosition is accepted as an alias for layoutPosition. "
        "Do not write style.properties.slideshow — that path is not in the BO style save. "
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
                    "HAR header/save fields: height, wrapperHeight, layoutPosition, interval. "
                    "contentPosition is an alias for layoutPosition (0/0/10 → height 0, "
                    "wrapperHeight 0, layoutPosition 10)."
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


def apply_slideshow(header: Dict[str, Any], slideshow: Dict[str, Any]) -> List[str]:
    """Merge slideshow into a header resource (HAR header/save keys only)."""
    if not isinstance(header, dict):
        raise ValueError("header/save target is missing.")
    props = header.get("properties")
    if not isinstance(props, dict):
        props = {}
        header["properties"] = props
    notes: List[str] = []
    if "height" in slideshow:
        header["height"] = slideshow["height"]
        notes.append(f"header.height={slideshow['height']!r}")
    if "wrapperHeight" in slideshow:
        props["wrapperHeight"] = slideshow["wrapperHeight"]
        notes.append(f"header.properties.wrapperHeight={slideshow['wrapperHeight']!r}")
    if "layoutPosition" in slideshow:
        props["layoutPosition"] = slideshow["layoutPosition"]
        notes.append(f"header.properties.layoutPosition={slideshow['layoutPosition']!r}")
    elif "contentPosition" in slideshow:
        props["layoutPosition"] = slideshow["contentPosition"]
        notes.append(
            f"header.properties.layoutPosition={slideshow['contentPosition']!r} (alias of contentPosition)"
        )
    if "interval" in slideshow:
        props["interval"] = slideshow["interval"]
        notes.append(f"header.properties.interval={slideshow['interval']!r}")
    if not notes:
        raise ValueError(
            "slideshow must include at least one HAR key: height, wrapperHeight, "
            "layoutPosition (or contentPosition), interval."
        )
    return notes


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    site_id = arguments.get("site_id")
    user_email = arguments.get("user_email")
    if not site_id:
        raise ValueError("Missing 'site_id' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    try:
        palette = _as_object(arguments.get("palette"), "palette")
        header_patch = _as_object(arguments.get("header"), "header")
        slideshow = _as_object(arguments.get("slideshow"), "slideshow")
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return {"content": [{"type": "text", "text": f"Invalid theme payload: {e}"}]}

    if not palette and not header_patch and not slideshow:
        return {
            "content": [
                {"type": "text", "text": "Provide at least one of: palette, header, slideshow."}
            ]
        }

    logger.info("Executing update_site_theme site_id=%s", site_id)

    try:
        token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Could not get token: {format_api_error(e)}."}]}

    notes: List[str] = []
    style_id = None

    if palette or header_patch:
        try:
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
        try:
            if palette:
                notes.extend(apply_palette(properties, palette))
            if header_patch:
                notes.extend(apply_header(properties, header_patch))
        except ValueError as e:
            return {"content": [{"type": "text", "text": str(e)}]}
        try:
            await lumapps_client.save_style(style, token=token)
        except Exception as e:
            logger.exception("update_site_theme save_style failed")
            text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"Could not save style: {format_api_error(e)}."
            return {"content": [{"type": "text", "text": text}]}

    if slideshow:
        try:
            instance = await lumapps_client.get_instance(site_id, token=token)
        except Exception as e:
            logger.exception("update_site_theme get_instance failed")
            return {
                "content": [
                    {"type": "text", "text": f"Could not load instance for header slideshow: {format_api_error(e)}."}
                ]
            }
        header_id = None
        if isinstance(instance, dict):
            header_id = instance.get("defaultHeader") or instance.get("header")
        if not header_id:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Slideshow is header/save (HAR), not style.properties. "
                            "instance.defaultHeader is missing; cannot POST header/save."
                        ),
                    }
                ]
            }
        try:
            header_resource = await lumapps_client.get_header(str(header_id), token=token)
        except Exception as e:
            logger.exception("update_site_theme get_header failed")
            return {
                "content": [{"type": "text", "text": f"Could not load header {header_id}: {format_api_error(e)}."}]
            }
        if not isinstance(header_resource, dict):
            return {"content": [{"type": "text", "text": f"header/get for {header_id} did not return an object."}]}
        try:
            notes.extend(apply_slideshow(header_resource, slideshow))
        except ValueError as e:
            return {"content": [{"type": "text", "text": str(e)}]}
        try:
            await lumapps_client.save_header(header_resource, token=token)
        except Exception as e:
            logger.exception("update_site_theme save_header failed")
            text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"Could not save header slideshow: {format_api_error(e)}."
            return {"content": [{"type": "text", "text": text}]}

    base_url = (settings.SITE_BASE_URL or "").rstrip("/")
    style_bit = f"style id={style_id}. " if style_id else ""
    msg = (
        f"Theme updated for site_id={site_id} ({style_bit}"
        + "; ".join(notes)
        + f"). Verify at: {base_url}. Re-inspect with inspect_lumapps_element (site_id)."
    )
    return {"content": [{"type": "text", "text": msg}]}
