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

"""Update widget properties.settings / Advanced classes via content/save. Does not touch properties.style."""

import json
import logging
from typing import Any, Dict

from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
from app.tools.api_error_utils import format_api_error, is_permission_denied, PERMISSION_DENIED_MESSAGE
from app.tools.widget_template import pick_settings_highlights, save_widget_template_patch

logger = logging.getLogger(__name__)

TOOL_NAME = "update_widget_settings"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Deep-merge widget settings on a LumApps page (content.template) via content/save. "
        "Use for display mode, types, count, Advanced classes, identifier. "
        "Does NOT write properties.style — use update_widget_style for padding/margin/border. "
        "IMPORTANT: Always run inspect_lumapps_element first. Before calling this tool, you MUST present "
        "the modification to the user and wait for their explicit 'Yes' or 'Confirm' in the chat. "
        "Never apply changes silently. "
        "Keys from /bot homepage content/save (HAR 2026-09-14) — not a theoretical spec: "
        "properties.class (single token, e.g. grok-home-news), "
        "properties.widgetClass (comma list, e.g. 'grok-news, grok-pills'), "
        "properties.identifier, "
        "properties.thumbnailPosition (content-list: 'background'), "
        "properties.uncompressedThumbnail (content-list: true), "
        "properties.viewMode (content-list: 'horizontal'; also settings.viewMode), "
        "properties.perLine (content-list: 3), "
        "properties.settings.itemsPerLine / numberOfItemsPerLine / maxNumber, "
        "properties.settings.types / contentTypes (e.g. news), "
        "properties.settings.fields (date/tags/title on; author/excerpt/social off), "
        "properties.settings.isHighResolution, "
        "directory-entry: properties.directory (array of uids), properties.viewMode / viewModeVariant, "
        "properties.settings.displayMode (catalogue), "
        "html: properties.content (locale map) + widgetClass, "
        "featured-image: properties.imageFormat + widgetClass. "
        "No footer link on that /bot save. "
        "CSS skin: skin: .{cssClass} → .widget--{cssClass} "
        "(properties.class / /blocks stays the token; CSS targets the prefix; proven content-list / directory). "
        "Do not pick token vs prefixed at random. "
        "properties.widgetClass is not in /blocks — other/legacy, not the skin hook."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "description": "LumApps content/page ID (e.g. homepage)."},
            "widget_id": {
                "type": "string",
                "description": (
                    "Template uuid from inspect ('use this id for writes'). "
                    "A layout widgetId is also accepted and mapped to the same template widget. "
                    "Prefer the full uuid, not an 8-character prefix."
                ),
            },
            "settings_updates": {
                "type": "string",
                "description": (
                    "JSON object deep-merged into the template widget. Example from /bot content-list: "
                    '{"properties": {"class": "grok-home-news", "widgetClass": "grok-news, grok-pills", '
                    '"identifier": "home-news", "thumbnailPosition": "background", '
                    '"uncompressedThumbnail": true, "viewMode": "horizontal", "perLine": 3, '
                    '"settings": {"viewMode": "horizontal", "itemsPerLine": 3, "types": ["news"]}}}. '
                    "properties.style in this payload is ignored."
                ),
            },
            "user_email": {"type": "string", "description": "User email for LumApps API token."},
        },
        "required": ["content_id", "widget_id", "settings_updates", "user_email"],
    },
}


def parse_settings_updates(raw: Any) -> Dict[str, Any]:
    """Parse settings_updates JSON and drop properties.style so style stays with update_widget_style."""
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = dict(raw)
    if not isinstance(data, dict):
        raise ValueError("settings_updates must be a JSON object.")
    props = data.get("properties")
    if isinstance(props, dict) and "style" in props:
        props = dict(props)
        props.pop("style", None)
        data = dict(data)
        data["properties"] = props
    return data


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    content_id = arguments.get("content_id")
    widget_id = arguments.get("widget_id")
    settings_raw = arguments.get("settings_updates")
    user_email = arguments.get("user_email")

    if not content_id or not widget_id or not user_email:
        return {
            "content": [{"type": "text", "text": "Missing required argument: content_id, widget_id, or user_email."}]
        }
    if not settings_raw:
        return {"content": [{"type": "text", "text": "Missing settings_updates (JSON object)."}]}

    try:
        settings_updates = parse_settings_updates(settings_raw)
    except json.JSONDecodeError as e:
        return {"content": [{"type": "text", "text": f"Invalid settings_updates JSON: {e}"}]}
    except (TypeError, ValueError) as e:
        return {"content": [{"type": "text", "text": str(e)}]}

    logger.info("Executing update_widget_settings content_id=%r, widget_id=%r", content_id, widget_id)

    try:
        token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
    except Exception as e:
        logger.exception("update_widget_settings get_token failed")
        text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"Failed to get admin token: {format_api_error(e)}"
        return {"content": [{"type": "text", "text": text}]}

    layout = None
    try:
        layout = await lumapps_client.get_content_layout(content_id, token=token)
    except Exception as e:
        logger.warning("update_widget_settings get_content_layout skipped (template match still runs): %s", e)

    try:
        ok, msg, target = await save_widget_template_patch(
            content_id,
            widget_id,
            settings_updates,
            token,
            layout=layout,
            protect_style=True,
        )
    except Exception as e:
        logger.exception("update_widget_settings save failed")
        text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"Save failed: {format_api_error(e)}"
        return {"content": [{"type": "text", "text": text}]}

    if not ok:
        return {"content": [{"type": "text", "text": msg}]}

    highlights = pick_settings_highlights(target or {})
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Widget {widget_id!r} settings updated via content/save. "
                    f"properties.style was not written. Applied highlights: {json.dumps(highlights)}. "
                    "Re-inspect with inspect_lumapps_element to confirm classes and settings."
                ),
            }
        ]
    }
